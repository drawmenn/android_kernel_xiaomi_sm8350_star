# UID Path Filter Rules — KSU Module

[中文说明](README_CN.md)

A KernelSU companion module for the per-UID path visibility scoping
feature in the custom kernel. It provides a Material Design 3 WebUI to
manage which application UIDs have scoped access to specified
`/Android/data/` directory suffixes.

## Prerequisites

- A kernel built with `CONFIG_UID_PATH_FILTER` (release r6 or later on
  branch `5.4.274-qgki-4dfe63e0666f` of this repository)
- KernelSU or a compatible root manager (BakaSU / ReSukiSU)
- An arm64 SELinux live policy binary (not included in source — see below)

## Obtaining the policy binary

The module needs an arm64 live SELinux policy binary at install time to
grant SELinux write access to the sysfs configuration node.

1. Download the [upstream manager v31.1 APK](https://github.com/topjohnwu/Magisk/releases)
2. Extract `lib/arm64-v8a/libmagiskpolicy.so` from the APK
3. Rename it to `magiskpolicy` and place it in this directory

Alternatively, use the prebuilt ZIP from the
[r6 release](https://github.com/drawmenn/android_kernel_xiaomi_sm8350_star/releases)
which already includes the binary.

## Building the module ZIP

```sh
zip -r uid_path_filter_rules.zip \
  module.prop customize.sh control.sh service.sh \
  sepolicy.rule magiskpolicy appnames.dex webroot
```

Flash the resulting ZIP in your root manager.

## File structure

```
├── module.prop         Module metadata
├── customize.sh        Install-time permissions fix (BakaSU 0644 workaround)
├── control.sh          Command backend (init/status/apps/labels/save/apply/log/update_desc)
├── service.sh          Boot-time auto-apply with 30× retry loop
├── sepolicy.rule       SELinux allow rules (applied at install by managers that support them; BakaSU injects the same rules live at boot)
├── magiskpolicy        Arm64 SELinux policy tool (not in source — see above)
├── appnames.dex        App display-name helper for the picker (not in source — the release ZIP includes it; adapted from the open-source UID- project)
└── webroot/
    ├── index.html      WebUI markup
    ├── style.css       Material Design 3 theme (dark/light auto)
    ├── app.js          WebUI logic (ksu.exec bridge)
    └── fonts/
        └── material-symbols.woff2  Material Symbols Outlined (Apache 2.0, Google)
```

## How it works

The module writes rules to `/sys/kernel/uid_path_filter/config` in the
format `add <uid> /Android/data/<pkg>`. The kernel then returns
`-ENOENT` for path lookups and directory enumerations matching those
suffixes when performed by the specified UID.

After writing, `control.sh apply` reads the kernel table back and
verifies every rule landed. If any write fails or the table does not
match the expected count, it reports an error instead of silently
succeeding.

On boot, `service.sh` retries apply up to 30 times (2-second intervals)
to wait for the package manager to come up, then updates the module
description in `module.prop` with the live status (e.g. `✓ 4 rules
active`) so the root manager's module list reflects the current state.

The WebUI picker lists installed apps with their display names (via the
bundled `appnames.dex` helper running under `app_process`, falling back
to package names) and keeps the currently selected entries sorted to the
top of the list.

## Configuration

Edit `/data/adb/uid_path_filter_rules/config` or use the WebUI:

- `target=<pkg>` — apps whose access is scoped (one or more)
- `pkg=<pkg>` — directory suffixes to restrict (one or more)

Each target × package pair becomes one kernel rule. The kernel table
holds 256 entries.

## Disclaimer

This module and the underlying kernel feature are intended for technical
research and environment customization on devices you own. They scope
filesystem visibility per-UID at the kernel level. Use responsibly and
in compliance with applicable terms of service.

---

[中文说明](README_CN.md)
