/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Per-UID priority query scoping.
 *
 * getpriority(PRIO_USER, uid), setpriority(PRIO_USER, uid), ioprio_get() and
 * ioprio_set() answer "does this UID have live processes?" for arbitrary UIDs,
 * including ones the caller does not own.  An unprivileged application can
 * sweep the application-UID range to enumerate which UIDs have running
 * threads — information it has no need to obtain about other applications.
 *
 * This scopes those syscalls to the caller's own UID: an unprivileged
 * cross-UID lookup is answered as if the target had no processes (-ESRCH),
 * so the syscall only reports on UIDs the caller already belongs to.
 * Lookups from system callers (uid < 10000) and lookups of the caller's own
 * UID are untouched.
 */

#ifndef _LINUX_UID_PRIO_FILTER_H
#define _LINUX_UID_PRIO_FILTER_H

#include <linux/cred.h>
#include <linux/sched.h>
#include <linux/uidgid.h>

/* First UID handed out to applications by the Android framework. */
#define UID_PRIO_FILTER_MIN_APP_UID	10000
/* Offset of the per-secondary-user UID range (AID_USER_OFFSET). */
#define UID_PRIO_FILTER_AID_USER	100000

/**
 * uid_prio_filter_hide - scope an unprivileged cross-UID lookup to self
 * @uid: target UID, already mapped into the caller's user namespace
 *
 * Returns %true when both the caller and the target are application UIDs and
 * they do not belong to the same application.
 */
static __always_inline bool uid_prio_filter_hide(kuid_t uid)
{
	uid_t caller, target;

	if (!uid_valid(uid))
		return false;

	caller = __kuid_val(current_uid());
	target = __kuid_val(uid);

	if (caller < UID_PRIO_FILTER_MIN_APP_UID ||
	    target < UID_PRIO_FILTER_MIN_APP_UID)
		return false;

	/* Fold secondary-user ranges back onto the primary one. */
	if (caller >= UID_PRIO_FILTER_AID_USER)
		caller %= UID_PRIO_FILTER_AID_USER;
	if (target >= UID_PRIO_FILTER_AID_USER)
		target %= UID_PRIO_FILTER_AID_USER;

	return caller != target;
}

#endif /* _LINUX_UID_PRIO_FILTER_H */
