/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Per-UID path access scoping.
 *
 * Some pathnames disclose information an unprivileged application has no
 * need to obtain about other applications — the external-storage data
 * directory of an installed package answers "is that package installed?".
 * Access to those directories is restricted in userspace, but pathname
 * normalisation variations can slip past a path-string check, so the
 * decision also belongs in the kernel.
 *
 * Each configuration entry pairs a caller UID with a pathname suffix, e.g.
 * "/Android/data/com.example.app".  For a process running as that UID,
 * resolving any pathname that ends in the configured suffix
 * (component-aligned) returns -ENOENT, and directory listings omit the
 * matching entry.  Callers with other UIDs — including the package that
 * owns the directory — are untouched.
 *
 * Suffix matching keeps a rule effective across the mount points that alias
 * the same external-storage tree (/storage/emulated/<user>,
 * /storage/self/primary, /sdcard).  Zero-width characters (U+200B, U+200C,
 * U+200D, U+FEFF) are skipped on both sides of every comparison so they
 * cannot turn one pathname into many.
 */

#ifndef _LINUX_UID_PATH_FILTER_H
#define _LINUX_UID_PATH_FILTER_H

#include <linux/fs.h>

#ifdef CONFIG_UID_PATH_FILTER

#define UID_PATH_FILTER_MAX_ENTRIES	256
#define UID_PATH_FILTER_MAX_LEN		256
#define UID_PATH_FILTER_MAX_WRAP		256

/*
 * Readdir wrapper state.  A stack-allocated instance lives for the duration
 * of one iterate_dir() call; idx[] holds indices into the static entry
 * table so a concurrent configuration change cannot dangle.
 */
struct uid_path_filter_dir {
	struct dir_context ctx;		/* actor = uid_path_filter_filldir */
	struct dir_context *orig;	/* caller's real context */
	int n;
	unsigned short idx[UID_PATH_FILTER_MAX_WRAP];
};

bool uid_path_filter_check_name(const char *name);
bool uid_path_filter_wrap_dir(struct file *file, struct dir_context *orig,
			      struct uid_path_filter_dir *w);

#else /* !CONFIG_UID_PATH_FILTER */

struct uid_path_filter_dir {
	struct dir_context ctx;
};

static inline bool uid_path_filter_check_name(const char *name)
{
	return false;
}

static inline bool uid_path_filter_wrap_dir(struct file *file,
					    struct dir_context *orig,
					    struct uid_path_filter_dir *w)
{
	return false;
}

#endif /* CONFIG_UID_PATH_FILTER */
#endif /* _LINUX_UID_PATH_FILTER_H */
