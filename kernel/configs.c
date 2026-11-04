// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * kernel/configs.c
 * Echo the kernel .config file used to build the kernel
 *
 * Copyright (C) 2002 Khalid Aziz <khalid_aziz@hp.com>
 * Copyright (C) 2002 Randy Dunlap <rdunlap@xenotime.net>
 * Copyright (C) 2002 Al Stone <ahs3@fc.hp.com>
 * Copyright (C) 2002 Hewlett-Packard Company
 */

#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/init.h>
#include <linux/uaccess.h>

/*
 * "IKCFG_ST" and "IKCFG_ED" are used to extract the config data from
 * a binary kernel image or a module. See scripts/extract-ikconfig.
 */
#define IKCONFIG_MAGIC_SIZE 8
/*
 * Include the actual gzip bytes in this translation unit. Its ThinLTO input
 * then changes when .config changes, while file-operation callbacks retain
 * normal CFI instrumentation instead of compiling configs.o without LTO.
 */
#include "config_data.h"

#ifdef CONFIG_IKCONFIG_PROC

static ssize_t
ikconfig_read_current(struct file *file, char __user *buf,
		      size_t len, loff_t * offset)
{
	return simple_read_from_buffer(buf, len, offset,
				       kernel_config_data + IKCONFIG_MAGIC_SIZE,
				       sizeof(kernel_config_data) - 1 -
				       2 * IKCONFIG_MAGIC_SIZE);
}

static const struct file_operations ikconfig_file_ops = {
	.owner = THIS_MODULE,
	.read = ikconfig_read_current,
	.llseek = default_llseek,
};

static int __init ikconfig_init(void)
{
	struct proc_dir_entry *entry;

	/* create the current config file */
	entry = proc_create("config.gz", S_IFREG | S_IRUGO, NULL,
			    &ikconfig_file_ops);
	if (!entry)
		return -ENOMEM;

	proc_set_size(entry, sizeof(kernel_config_data) - 1 -
			    2 * IKCONFIG_MAGIC_SIZE);

	return 0;
}

static void __exit ikconfig_cleanup(void)
{
	remove_proc_entry("config.gz", NULL);
}

module_init(ikconfig_init);
module_exit(ikconfig_cleanup);

#endif /* CONFIG_IKCONFIG_PROC */

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Randy Dunlap");
MODULE_DESCRIPTION("Echo the kernel .config file used to build the kernel");
