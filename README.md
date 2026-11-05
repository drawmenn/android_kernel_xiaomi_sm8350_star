# Android Kernel for Xiaomi Mi 11 Pro / Ultra (star / mars)

[**中文说明文档 (Chinese README)**](README_CN.md) | **English Documentation**

Custom Qualcomm Generic Kernel Image (QGKI 5.4.274) for Xiaomi 11 Pro / Ultra (`star` / `mars`), featuring integrated **ReSukiSU / BakaSU**, **SuSFS v2.3.0**, **Linux 5.10 Seccomp Bitmap Fastpath**, and advanced **kernel-level detection counter-measures (Chunqiu Detector / MOMO / Root detection hardening)**.

---

## 📱 Supported Android Versions & ROMs

Because this kernel is packaged via **AnyKernel3 (boot-kernel-only)** without touching `vendor_boot`, device trees, or vendor partitions, it retains full ABI compatibility with Qualcomm Snapdragon 888 (`SM8350`) vendor drivers.

| Android Version | OS / ROM Examples | Status | Notes |
| :--- | :--- | :--- | :--- |
| **Android 14** | Xiaomi HyperOS 1.0 (OS1.0.x), AOSP 14 / LineageOS 21 | **Fully Supported** | Primary target platform; extensively tested. |
| **Android 13** | MIUI 14 (V14.0.x), AOSP 13 / LineageOS 20 | **Fully Supported** | Excellent battery life and thermal stability. |
| **Android 12** | MIUI 13 (V13.0.x), AOSP 12 / 12L | **Supported** | Fully compatible. |
| **Android 11** | MIUI 12.5 (Factory shipping version) | **Supported** | Factory baseline release. |
| **Android 15** | AOSP 15 (VanillaIceCream) / Custom ROMs | **Compatible** | Dependent on ROM vendor blobs matching SM8350 QGKI 5.4. |

> **Supported Devices**:
> - Xiaomi Mi 11 Pro (`star`)
> - Xiaomi Mi 11 Ultra (`star` / `mars`)

---

## ⚡ Key Kernel Features & Highlights

### 1. Security & Stealth Engine
* **ReSukiSU / BakaSU (v4.2.0-rc3)**: Next-generation KernelSU implementation with modern root capabilities and multi-manager support. Uses an **Inline Hook** architecture instead of kprobes, eliminating performance overhead and tracepoint leaks.
* **SuSFS v2.3.0 Protocol Integration**:
  * Comprehensive VFS hide & mount isolation: `sus_path`, `sus_mount`, `sus_kstat`, `open_redirect`, and `sus_map`.
  * Advanced FD & Notify leak prevention: hooks into `/proc/[pid]/fdinfo` and `inotify_fdinfo` to conceal hidden files.
  * `vfs_statfs` filesystem spoofing to mask overlayfs/tmpfs characteristics.
* **Chunqiu Detector & Advanced Anti-Detection Defense**:
  * **Tampered Kernel Spoofing**: Eliminates custom/Ubuntu compiler signatures by spoofing official `Android (7284624, based on r416183b) clang version 12.0.5, LLD 12.0.5` with OEM build credentials (`android-build@c3-miui-ota-bd174.bj`) and standard OTA timestamp.
  * **Unified Version Tree**: Links SuSFS uname spoofing into `/proc/version` so that `uname -r`, `/proc/version`, and `sys_newuname` return identical data.
  * **`/data/local/tmp` Inode & Mode Concealment**: Automatically masks `/data/local/tmp` queries from unprivileged processes (`UID >= 10000`) into baseline factory attributes (`ino=156`, `uid:gid=2000:2000` shell:shell, `0771`).
  * **SELinux Live Policy Protection**:
    * Clean status mapping (`/sys/fs/selinux/status`) with locked `sequence=0`, `policyload=0`, and `enforcing=1`.
    * Masks DirtySepolicy access probes (`system_server execmem`, `zygote adb_data_file search`, `system_server execute apk_data_file`) and locks `avd.seqno=1`.

### 2. Performance & System Stability
* **Linux 5.10 Seccomp Bitmap Fastpath (Backport)**:
  * Backports the upstream 5.10 Seccomp cache mechanism (`action_cache` bitmap). Bypasses BPF evaluation loops for high-frequency safe syscalls, noticeably reducing micro-stuttering in intensive applications.
* **Compiler-Level ThinLTO & Optimization**:
  * Compiled with Clang ThinLTO (`CONFIG_THINLTO=y`, `CONFIG_LTO_CLANG=y`) for optimized cross-module inlining and cache footprint.
* **Full Android FCM5 & VINTF Compliance**:
  * Meets all Google FCM 5 requirements (`CONFIG_ARM64_SW_TTBR0_PAN=y`, `CONFIG_CFI_CLANG=y`, `CONFIG_SHADOW_CALL_STACK=y`).
  * Embeds `.config` directly via `bin2c` into `configs.o`, ensuring VINTF runtime verification passes cleanly and eliminating system internal warning popups.
* **Binder Lockscreen Freeze Fix**:
  * Resolves the notorious lockscreen/AOD freeze issue on Snapdragon 888 devices by cleanly eliminating improper Binder freeze notification backports.

---

## 🛠️ Build Environment & Prerequisites

Before compiling or upgrading, ensure that your build machine satisfies the following prerequisites:

### 1. Host Dependencies (Debian / Ubuntu)
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential bc bison flex libssl-dev libelf-dev libncurses5-dev \
    git curl wget zip unzip cpio python3 python-is-python3 binutils-aarch64-linux-gnu
```

### 2. Toolchain Setup (LLVM / Clang)
Building this kernel requires an `aarch64`-capable Clang toolchain supporting ThinLTO:
* **Recommended Official Android Clang**: AOSP Clang `r416183b` (Clang 12.0.5) or newer.
* **System Clang**: Alternatively, host system `clang` (>= 12.0.0) with `lld`, `llvm-ar`, `llvm-nm`, `llvm-objcopy`, and `llvm-strip` available in `$PATH`.
* Ensure `clang -v` and `ld.lld -v` operate properly in your terminal.

### 3. Source Tree & Submodules Preparation
Always initialize all nested submodules (notably `KernelSU`):
```bash
# Clone repository
git clone https://github.com/<user>/<repo>.git -b qgki-4dfe63e0666f kernel-star
cd kernel-star

# Sync and pull submodules (KernelSU)
git submodule update --init --recursive
```

---

## 🔄 General Upgrade Guide (KSU & SuSFS)

### 1. Upgrading KernelSU / ReSukiSU
KernelSU is integrated as a git submodule in the kernel source repository:
```bash
# 1. Enter the submodule directory within your local kernel clone
cd KernelSU

# 2. Fetch remote tags and branches
git fetch origin

# 3. Switch to your desired version or tag
git checkout <target_tag_or_branch>

# 4. Return to the root of the kernel tree
cd ..

# 5. Review compatibility and recompile
# Ensure inline hook prototypes in KernelSU/kernel/core_hook.c match SuSFS
```

### 2. Upgrading SuSFS
When upstream SuSFS releases a newer version (e.g., v2.4.x):
1. **Header & Source**: Place updated `susfs.h` in `include/linux/susfs.h` and updated `susfs.c` in `fs/susfs.c`.
2. **Kernel VFS Hooks**: Inspect hook diffs across core VFS files (`fs/stat.c`, `fs/statfs.c`, `fs/open.c`, `fs/proc/fd.c`, `fs/notify/fdinfo.c`, `fs/proc/version.c`).
3. **KSU Integration**: Update `ksu_susfs` inline hooks in KernelSU accordingly.
4. **Build & Package**: Trigger kernel compilation and package a new AnyKernel3 zip.

---

## 🔨 Building the Kernel

To build the kernel image (`Image.gz`):
```bash
# Execute the automated build script (handles defconfig, FCM5 checks, and ThinLTO build)
./build_star.sh
```
The compiled kernel artifact lands in:
`out-star-5.4.274-qgki-g4dfe63e0666f/arch/arm64/boot/Image.gz`

---

## 📦 Flashing Guide

1. Download the AnyKernel3 zip package from [GitHub Releases](https://github.com/dundwv/android_kernel_xiaomi_sm8350_star/releases).
2. Reboot your device into TWRP / OrangeFox recovery.
3. **Backup your current `boot` partition** (recommended).
4. Flash `star-5.4.274-qgki-g4dfe63e0666f-AK3-r*.zip`.
5. Reboot system. Install matching `BakaSU` manager APK.

---

## 🇨🇳 中文说明摘要 (Summary in Chinese)

本内核是针对小米 11 Pro / Ultra (`star` / `mars`, 骁龙 888) 深度定制的 QGKI 5.4.274 纯内核包，适用于 **Android 11 至 Android 14 (包括 MIUI 12.5/13/14 及澎湃 HyperOS 1.0)**。深度集成了 **ReSukiSU / BakaSU** 与 **SuSFS v2.3.0**，并在内核层针对**春秋检测器 (Chunqiu Detector)** 实现了系统级防御。

详细中文使用手册与技术细节请直接参阅：👉 [**README_CN.md**](README_CN.md)
