# Android Kernel for Xiaomi Mi 11 Pro / Ultra (star / mars)

[**中文说明文档 (Chinese README)**](README_CN.md) | **English Documentation**

Custom Qualcomm Generic Kernel Image (QGKI 5.4.274) for Xiaomi Mi 11 Pro / Ultra (`star` / `mars`, SM8350), built from the Qualcomm open-source baseline and integrated with **ReSukiSU / BakaSU**, **SuSFS v2.3.0**, a **Linux 5.10 Seccomp bitmap fastpath backport**, and a set of **environment-integrity compatibility** adjustments for personal-device use.

---

## ⚠️ Compliance & Disclaimer (read first)

* **Scope of use.** This is a personal, hobbyist kernel build for **your own device**, published for **Android platform engineering study** — reproducible kernel builds, VFS/SELinux internals, and system-level performance work.
* **Not for circumvention.** It must **not** be used to defeat anti-cheat systems, DRM, banking or payment risk controls, enterprise MDM, or any other access-control mechanism, and must not be used for fraud, account trading, or anything that violates applicable law or the terms of any application.
* **No warranty.** Flashing a custom kernel may brick the device, break OTA updates, void the warranty, or cause data loss. Backups and consequences are entirely yours.
* **Licensing.** Kernel sources are distributed under **GPL-2.0** (see [`COPYING`](COPYING)). Vendor blobs, firmware, and third-party components remain the property of their owners and are **not** redistributed here. KernelSU / SuSFS components keep their upstream licenses.
* **Nothing to misuse is shipped.** No keybox, no attestation key material, no prebuilt APKs, no proprietary vendor binaries are included.

If that does not match how you intend to use this project, do not use it.

---

## 📱 Supported Android Versions & ROMs

The kernel ships as an **AnyKernel3 boot-image-only** package: it replaces `Image.gz` inside the existing `boot` ramdisk and does **not** touch `vendor_boot`, `dtbo`, `vbmeta`, or vendor partitions, so it stays ABI-compatible with the stock SM8350 vendor drivers.

| Android Version | OS / ROM Examples | Status | Notes |
| :--- | :--- | :--- | :--- |
| **Android 14** | HyperOS 1.0 (OS1.0.x), AOSP 14 / LineageOS 21 | **Fully supported** | Reference platform for testing. |
| **Android 13** | MIUI 14 (V14.0.x), AOSP 13 / LineageOS 20 | **Fully supported** | Good thermals and battery behaviour. |
| **Android 12** | MIUI 13 (V13.0.x), AOSP 12 / 12L | **Supported** | — |
| **Android 11** | MIUI 12.5 (factory image) | **Supported** | Factory baseline. |
| **Android 15** | AOSP 15 / community ports | **Compatible** | Needs a ROM whose vendor blobs match SM8350 QGKI 5.4. |

> **Devices**: Xiaomi Mi 11 Pro (`star`) · Xiaomi Mi 11 Ultra (`star` / `mars`)

---

## ⚡ Kernel Features

### 1. Root & isolation layer

* **ReSukiSU / BakaSU (v4.2.0-rc3)** — a maintained KernelSU fork using the **inline-hook** model instead of optional kprobes, so there is no extra instruction-trap overhead and no tracepoint footprint to account for.
* **SuSFS v2.3.0** — scoped filesystem namespace layer:
  * `sus_path`, `sus_mount`, `sus_kstat`, `open_redirect`, `sus_map` keep module paths out of ordinary path queries;
  * `/proc/<pid>/fdinfo` and `inotify_fdinfo` filtering, so internal paths do not surface through descriptor introspection;
  * `vfs_statfs` normalisation, so mounts report the expected filesystem type.

### 2. Environment-integrity compatibility (technical notes)

Some applications run **build-identity and system-state consistency checks** and treat any deviation from the stock factory profile as an unsupported environment. The changes below make a locally built kernel report the same **deterministic values** a stock image reports — which is also what reproducible-build practice calls for.

* **Deterministic build identity** — `scripts/mkcompile_h` honours `KBUILD_COMPILER_STRING`, and `build_star.sh` pins the toolchain string (`Android (7284624, based on r416183b) clang version 12.0.5, LLD 12.0.5`), `KBUILD_BUILD_USER` / `KBUILD_BUILD_HOST`, `KBUILD_BUILD_VERSION`, and `KBUILD_BUILD_TIMESTAMP`. Two builds from different hosts produce the same banner instead of leaking the builder's distro and wall-clock time.
* **One source of truth for the version string** — SuSFS `uname` handling is wired into `fs/proc/version.c`, so `uname(2)`, `/proc/version`, and `/proc/sys/kernel/osrelease` cannot disagree.
* **`/data/local/tmp` attribute alignment** — `fs/stat.c` recognises the `/data` mountpoint root (its dentry parent is `"/"`, not `"data"`) and caches the inode on first sight. Unprivileged callers (`uid >= 10000`) then receive the factory-consistent tuple `ino=156`, `uid:gid=2000:2000`, mode `0771`, whether they stat by path or by descriptor.
* **SELinux query consistency** — for unprivileged callers only, `security/selinux/selinuxfs.c`:
  * serves a read-only status page reporting `sequence=0`, `policyload=0`, `enforcing=1`, matching a policy that was never reloaded;
  * filters vendor/extension-only permission bits (`PROCESS__EXECMEM` on `system_server`, `DIR__SEARCH` / `DIR__READ` on `adb_data_file` for `zygote`, `FILE__EXECUTE` on `apk_data_file` for `system_server`) out of `/sys/fs/selinux/access` replies and reports `avd.seqno=1`;
  * still returns `-EINVAL` for context names that do not exist in a stock policy.

  Privileged callers (`uid < 10000`) are unaffected — root grants, `ksud`, and module daemons behave exactly as before.
* **Per-UID priority query scoping** — `getpriority(PRIO_USER, …)`, `setpriority(PRIO_USER, …)`, `ioprio_get()`, and `ioprio_set()` answer "does this UID have live processes?" for any UID. `include/linux/uid_prio_filter.h` scopes unprivileged cross-application-UID lookups to the caller's own UID (returns `-ESRCH`), so an application cannot enumerate other applications' UIDs through these syscalls. System callers (`uid < 10000`) and self-lookups are unaffected.
* **Per-UID path access scoping** (`CONFIG_UID_PATH_FILTER`) — pathname resolution and directory listings answer "does this path exist?" for any caller. Each configured (UID, path-suffix) pair — managed at `/sys/kernel/uid_path_filter/config` — makes pathnames ending in that suffix (component-aligned) resolve to `-ENOENT` and omits the matching entries from directory listings, for that UID only. Other callers, including the path's owner, are unaffected. Zero-width characters (`U+200B/200C/200D/FEFF`) are skipped on both sides of every comparison, and suffix matching treats the mount aliases of the external-storage tree (`/storage/emulated/<user>`, `/storage/self/primary`, `/sdcard`) identically. A companion module zip in the release applies the SELinux allow rule and the rules at boot.

### 3. Performance & stability

* **Seccomp bitmap fastpath (5.10 backport)** — brings the upstream `action_cache` bitmap and the `seccomp_run_filters()` fastpath to 5.4. Frequently used safe syscalls skip the filter-program walk, which measurably reduces micro-stutter in syscall-heavy workloads.
* **ThinLTO** — `CONFIG_THINLTO=y` with `CONFIG_LTO_CLANG=y`: cross-TU inlining with a bounded link step.
* **FCM5 / VINTF conformance** — satisfies `CONFIG_MODVERSIONS`, `CONFIG_ARM64_SW_TTBR0_PAN`, `CONFIG_CFI_CLANG`, `CONFIG_SHADOW_CALL_STACK`, and `# CONFIG_DEBUG_FS is not set`; `.config` is embedded through `bin2c` so the runtime IKCONFIG check passes and the "internal problem" dialog does not appear.
* **Binder freeze-notification revert** — drops the Binder freeze-notification backport that caused intermittent lockscreen/AOD hangs on SM8350.

---

## 🛠️ Build Environment & Prerequisites

### 1. Host packages (Debian / Ubuntu)
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential bc bison flex libssl-dev libelf-dev libncurses5-dev \
    git curl wget zip unzip cpio python3 python-is-python3 binutils-aarch64-linux-gnu
```

### 2. Toolchain (LLVM / Clang)
* **Preferred**: AOSP Clang `r416183b` (Clang 12.0.5) or newer — matches the pinned banner string above.
* **Alternative**: any host `clang >= 12` with `lld`, `llvm-ar`, `llvm-nm`, `llvm-objcopy`, `llvm-strip` on `$PATH`.
* Sanity check: `clang -v && ld.lld -v`.

### 3. Source tree and submodules
```bash
git clone https://github.com/drawmenn/android_kernel_xiaomi_sm8350_star.git -b 5.4.274-qgki-4dfe63e0666f kernel-star
cd kernel-star
git submodule update --init --recursive     # required: KernelSU lives here
```

> **Submodule note.** `.gitmodules` points at the maintainer's KernelSU fork, which carries the `seccomp_cache` commit this tree needs (upstream ReSukiSU does not have it yet). If that fork is unavailable, point the submodule at your own copy:
> ```bash
> git submodule set-url KernelSU https://github.com/<you>/BakaSU.git
> git submodule update --init --recursive
> ```

---

## 🔄 Upgrading KernelSU / SuSFS

### 1. KernelSU / ReSukiSU

Fast path — most upstream updates are Manager/ksud-only and need **no kernel work at all**:

```bash
./sync_ksu.sh --check   # exit 0 = APK-only update, 10 = kernel-side sync needed
./sync_ksu.sh           # full sync: rebase fork, bump submodule, rebuild, repackage
```

* **No new upstream commits** → nothing to do.
* **New commits, none under `kernel/`** → install the newest Manager APK only (releases or CI; the app's built-in update button can lag behind CI and offer a downgrade). ksud updates itself once the APK is installed.
* **Commits under `kernel/`** → the script rebases the fork branch (`star-5.4-seccomp-cache`), pushes the fork, bumps the submodule and rebuilds. The submodule bump commit stays local until device verification passes (staged release protocol).

Pinning a specific version manually:

```bash
cd KernelSU
git fetch origin
git checkout <tag-or-commit>     # pin an explicit tag; do not track a moving branch
cd ..
git add KernelSU && git commit -m "ksu: bump to <tag>"
```
Cross-major upgrades: re-check the inline-hook prototypes in `KernelSU/kernel/core_hook.c` (and the `susfs` glue) against the SuSFS version in the tree before building.

### 2. SuSFS
1. Drop the new `susfs.h` into `include/linux/susfs.h` and `susfs.c` into `fs/susfs.c`.
2. Diff the VFS hook sites: `fs/stat.c`, `fs/statfs.c`, `fs/open.c`, `fs/proc/fd.c`, `fs/notify/fdinfo.c`, `fs/proc/version.c`.
3. Update the `ksu_susfs` glue inside the KernelSU submodule.
4. Rebuild and pair with a matching SuSFS userspace module version.

---

## 🔨 Building

```bash
./build_star.sh
```
The script applies `star_dsl_defconfig`, enforces the FCM5 and seccomp gates (it aborts if any requirement is missing), then builds `Image.gz`, `dtbs`, and `modules`.

Output: `out-star-5.4.274-qgki-g4dfe63e0666f/arch/arm64/boot/Image.gz`

Build toggles: `JOBS=<n>`, `OUT_DIR=<path>`, `CONFIG_ONLY=1` (stop after `.config`), `BBR3=1` (opt into BBRv3 + `fq` instead of CUBIC/pfifo_fast).

### GitHub Actions (cloud build)

`.github/workflows/build-kernel.yml` builds this tree on `ubuntu-24.04` (system clang 18) and uploads the AnyKernel3 zip + config as Actions artifacts — no local build machine needed. It triggers on pushes to `ci/**`, pushes to the default branch, and manual runs (`workflow_dispatch`).

* `ci/**` is meant for refs without unverified kernel-side changes (e.g. a KernelSU submodule bump): push the ref, let the cloud build it, download the artifact, flash.
* CI never creates GitHub releases. Releases are cut manually, only after device verification.
* LTO is not deterministic: a CI zip built from identical source is not byte-identical to a local build. Flash and verify the exact zip you intend to release.

---

## 📦 Flashing

1. Download the AnyKernel3 zip from [Releases](https://github.com/drawmenn/android_kernel_xiaomi_sm8350_star/releases).
2. Boot into TWRP / OrangeFox.
3. **Back up the `boot` partition first.**
4. Flash `star-5.4.274-qgki-g4dfe63e0666f-AK3-r*.zip`.
5. Reboot and install the matching BakaSU manager APK.

---

## 🇨🇳 中文说明摘要

本仓库是小米 11 Pro / Ultra（`star` / `mars`，骁龙 888 / SM8350）的 QGKI 5.4.274 自编译内核，集成 ReSukiSU / BakaSU 与 SuSFS v2.3.0，并包含 Seccomp 位图快路径回移、ThinLTO 与 FCM5 合规配置。适用于 Android 11–14（MIUI 12.5 / 13 / 14、HyperOS 1.0）。

**仅限个人设备的技术研究与学习使用**，不得用于规避反作弊、风控、DRM 或任何访问控制机制。完整中文文档见 👉 [**README_CN.md**](README_CN.md)
