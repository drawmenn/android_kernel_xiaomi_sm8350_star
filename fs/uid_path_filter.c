// SPDX-License-Identifier: GPL-2.0
/*
 * Per-UID path access scoping.
 *
 * See include/linux/uid_path_filter.h for the behaviour description.
 */

#include <linux/cred.h>
#include <linux/dcache.h>
#include <linux/errno.h>
#include <linux/fs.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/mm.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/sysfs.h>
#include <linux/uid_path_filter.h>

struct uid_path_filter_entry {
	bool used;
	uid_t uid;
	char suffix[UID_PATH_FILTER_MAX_LEN];
};

static struct uid_path_filter_entry entries[UID_PATH_FILTER_MAX_ENTRIES];
static DEFINE_RWLOCK(entries_lock);

static struct kobject *uid_path_filter_kobj;

/* ---------------- zero-width-aware comparison ---------------- */

/*
 * Zero-width characters used to disguise path components. UTF-8 sequences:
 * U+200B E2 80 8B, U+200C E2 80 8C, U+200D E2 80 8D, U+FEFF EF BB BF.
 * The guards keep the 3-byte reads inside the region terminated by NUL
 * (for @q strings) or by @plen (for @p buffers).
 */
static bool uid_path_filter_is_zw(const unsigned char *s)
{
	if (!s[0] || !s[1] || !s[2])
		return false;
	if (s[0] == 0xe2 && s[1] == 0x80 &&
	    (s[2] == 0x8b || s[2] == 0x8c || s[2] == 0x8d))
		return true;
	return s[0] == 0xef && s[1] == 0xbb && s[2] == 0xbf;
}

/*
 * Compare @plen bytes of @p (not necessarily NUL-terminated) with the
 * NUL-terminated @q, skipping zero-width characters on both sides.
 */
static bool uid_path_filter_eq(const unsigned char *p, size_t plen,
			       const char *q)
{
	const unsigned char *s = (const unsigned char *)q;
	size_t i = 0;

	while (i < plen && *s) {
		if (plen - i >= 3 && uid_path_filter_is_zw(p + i)) {
			i += 3;
			continue;
		}
		if (uid_path_filter_is_zw(s)) {
			s += 3;
			continue;
		}
		if (p[i] != *s)
			return false;
		i++;
		s++;
	}
	while (plen - i >= 3 && uid_path_filter_is_zw(p + i))
		i += 3;
	while (*s && uid_path_filter_is_zw(s))
		s += 3;

	return i == plen && *s == '\0';
}

/*
 * Does the zero-width-normalised @path end with the normalised @suffix at
 * a component boundary?  @suffix must start with '/'.
 */
static bool uid_path_filter_suffix_match(const char *path, const char *suffix)
{
	size_t plen = strlen(path);
	size_t i;

	if (suffix[0] != '/')
		return false;

	for (i = 0; i < plen; i++) {
		if (path[i] == '/' &&
		    uid_path_filter_eq((const unsigned char *)path + i,
				       plen - i, suffix))
			return true;
	}
	return false;
}

/*
 * Directory part of a suffix: everything before the final '/'.
 * "/a/b" -> "/a", "/x" -> "/".
 */
static bool uid_path_filter_dirname(const char *suffix, char *buf, size_t size)
{
	const char *slash = strrchr(suffix, '/');

	if (slash == suffix) {
		if (size < 2)
			return false;
		buf[0] = '/';
		buf[1] = '\0';
		return true;
	}
	if ((size_t)(slash - suffix) >= size)
		return false;
	memcpy(buf, suffix, slash - suffix);
	buf[slash - suffix] = '\0';
	return true;
}

/* Final component of a suffix: after the last '/'. */
static const char *uid_path_filter_basename(const char *suffix)
{
	const char *slash = strrchr(suffix, '/');

	return slash ? slash + 1 : suffix;
}

/* ---------------- pathname resolution check ---------------- */

bool uid_path_filter_check_name(const char *name)
{
	uid_t caller = __kuid_val(current_uid());
	int i;
	bool hit = false;

	if (!name)
		return false;

	read_lock(&entries_lock);
	for (i = 0; i < UID_PATH_FILTER_MAX_ENTRIES; i++) {
		if (entries[i].used && entries[i].uid == caller &&
		    uid_path_filter_suffix_match(name, entries[i].suffix)) {
			hit = true;
			break;
		}
	}
	read_unlock(&entries_lock);

	return hit;
}

/* ---------------- readdir filtering ---------------- */

static int uid_path_filter_filldir(struct dir_context *ctx, const char *name,
				  int namelen, loff_t offset, u64 ino,
				  unsigned int d_type)
{
	struct uid_path_filter_dir *w =
		container_of(ctx, struct uid_path_filter_dir, ctx);
	bool swallow = false;
	int i;

	read_lock(&entries_lock);
	for (i = 0; i < w->n; i++) {
		int e = w->idx[i];
		const char *base;

		if (!entries[e].used)
			continue;
		base = uid_path_filter_basename(entries[e].suffix);
		if (uid_path_filter_eq((const unsigned char *)name, namelen,
				       base)) {
			swallow = true;
			break;
		}
	}
	read_unlock(&entries_lock);

	if (swallow)
		return 0;	/* report success, emit nothing */

	return w->orig->actor(w->orig, name, namelen, offset, ino, d_type);
}

/*
 * Decide whether the directory being listed needs entry filtering for the
 * current caller.  Fills @w and returns true if so; the caller then passes
 * &w->ctx to the filesystem's iterate() instead of its own context.
 */
bool uid_path_filter_wrap_dir(struct file *file, struct dir_context *orig,
			      struct uid_path_filter_dir *w)
{
	uid_t caller = __kuid_val(current_uid());
	char dirname[UID_PATH_FILTER_MAX_LEN];
	char *page_buf;
	char *dpath;
	bool have_any = false;
	bool wrapped = false;
	int i;

	w->n = 0;

	if (caller == 0)
		return false;

	read_lock(&entries_lock);
	for (i = 0; i < UID_PATH_FILTER_MAX_ENTRIES; i++) {
		if (entries[i].used && entries[i].uid == caller) {
			have_any = true;
			break;
		}
	}
	read_unlock(&entries_lock);

	if (!have_any)
		return false;

	page_buf = (char *)__get_free_page(GFP_KERNEL);
	if (!page_buf)
		return false;	/* fail open on memory pressure */

	dpath = d_path(&file->f_path, page_buf, PAGE_SIZE);
	if (IS_ERR(dpath))
		goto out;

	read_lock(&entries_lock);
	for (i = 0; i < UID_PATH_FILTER_MAX_ENTRIES &&
		    w->n < UID_PATH_FILTER_MAX_WRAP; i++) {
		if (!entries[i].used || entries[i].uid != caller)
			continue;
		if (!uid_path_filter_dirname(entries[i].suffix, dirname,
					     sizeof(dirname)))
			continue;
		if (uid_path_filter_suffix_match(dpath, dirname)) {
			w->idx[w->n] = i;
			w->n++;
		}
	}
	read_unlock(&entries_lock);

	if (w->n > 0) {
		w->ctx.actor = uid_path_filter_filldir;
		w->ctx.pos = 0;
		w->orig = orig;
		wrapped = true;
	}
out:
	free_page((unsigned long)page_buf);
	return wrapped;
}

/* ---------------- configuration interface ---------------- */

static int uid_path_filter_add(uid_t uid, const char *suffix)
{
	int i, free_slot = -1;

	if (suffix[0] != '/' || suffix[1] == '\0' ||
	    strlen(suffix) >= UID_PATH_FILTER_MAX_LEN)
		return -EINVAL;
	if (strstr(suffix, ".."))
		return -EINVAL;

	write_lock(&entries_lock);
	for (i = 0; i < UID_PATH_FILTER_MAX_ENTRIES; i++) {
		if (!entries[i].used) {
			if (free_slot < 0)
				free_slot = i;
			continue;
		}
		if (entries[i].uid == uid &&
		    !strcmp(entries[i].suffix, suffix)) {
			write_unlock(&entries_lock);
			return 0;	/* already configured */
		}
	}
	if (free_slot < 0) {
		write_unlock(&entries_lock);
		return -ENOSPC;
	}
	entries[free_slot].uid = uid;
	strlcpy(entries[free_slot].suffix, suffix, UID_PATH_FILTER_MAX_LEN);
	entries[free_slot].used = true;
	write_unlock(&entries_lock);
	return 0;
}

static int uid_path_filter_remove(uid_t uid, const char *suffix)
{
	int i;

	write_lock(&entries_lock);
	for (i = 0; i < UID_PATH_FILTER_MAX_ENTRIES; i++) {
		if (entries[i].used && entries[i].uid == uid &&
		    !strcmp(entries[i].suffix, suffix))
			entries[i].used = false;
	}
	write_unlock(&entries_lock);
	return 0;
}

static void uid_path_filter_clear(void)
{
	int i;

	write_lock(&entries_lock);
	for (i = 0; i < UID_PATH_FILTER_MAX_ENTRIES; i++)
		entries[i].used = false;
	write_unlock(&entries_lock);
}

static ssize_t uid_path_filter_config_show(struct kobject *kobj,
					   struct kobj_attribute *attr,
					   char *buf)
{
	int i, at = 0;

	read_lock(&entries_lock);
	for (i = 0; i < UID_PATH_FILTER_MAX_ENTRIES; i++) {
		if (!entries[i].used)
			continue;
		at += scnprintf(buf + at, PAGE_SIZE - at, "%u %s\n",
				entries[i].uid, entries[i].suffix);
	}
	read_unlock(&entries_lock);
	return at;
}

/*
 * Accepts one or more lines of:
 *   add <uid> <suffix>     make <suffix> resolve to -ENOENT for <uid>
 *   remove <uid> <suffix>   drop one rule
 *   clear                   drop every rule
 */
static ssize_t uid_path_filter_config_store(struct kobject *kobj,
					    struct kobj_attribute *attr,
					    const char *buf, size_t count)
{
	char *p, *remain, *line;
	int ret = 0;

	p = kstrdup(buf, GFP_KERNEL);
	if (!p)
		return -ENOMEM;

	remain = p;
	while (ret == 0 && (line = strsep(&remain, "\n")) != NULL) {
		char *cmd, *uid_s, *suffix;

		while (*line == ' ' || *line == '	')
			line++;
		if (*line == '\0')
			continue;

		cmd = strsep(&line, " \t");
		if (!strcmp(cmd, "clear")) {
			uid_path_filter_clear();
			continue;
		}

		uid_s = strsep(&line, " \t");
		suffix = strsep(&line, " \t");
		if (!uid_s || !suffix) {
			ret = -EINVAL;
			break;
		}

		{
			unsigned long uid;

			if (kstrtoul(uid_s, 10, &uid) ||
			    uid >= (1UL << 31)) {
				ret = -EINVAL;
				break;
			}
			if (!strcmp(cmd, "add")) {
				ret = uid_path_filter_add((uid_t)uid, suffix);
			} else if (!strcmp(cmd, "remove")) {
				ret = uid_path_filter_remove((uid_t)uid,
							      suffix);
			} else {
				ret = -EINVAL;
			}
		}
	}
	kfree(p);
	return ret ? ret : count;
}

static struct kobj_attribute uid_path_filter_config_attr =
	__ATTR(config, 0600, uid_path_filter_config_show,
	       uid_path_filter_config_store);

static int __init uid_path_filter_init(void)
{
	int ret;

	uid_path_filter_kobj =
		kobject_create_and_add("uid_path_filter", kernel_kobj);
	if (!uid_path_filter_kobj)
		return -ENOMEM;

	ret = sysfs_create_file(uid_path_filter_kobj,
				&uid_path_filter_config_attr.attr);
	if (ret) {
		kobject_put(uid_path_filter_kobj);
		uid_path_filter_kobj = NULL;
	}
	return ret;
}
late_initcall(uid_path_filter_init);
