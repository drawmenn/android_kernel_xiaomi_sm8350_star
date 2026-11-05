# Android Kernel for Xiaomi Mi 11 Pro / Ultra (star / mars)

[**中文说明文档 (Chinese README)**](README_CN.md) | **English Documentation**

Custom Qualcomm Generic Kernel Image (QGKI 5.4.274) for Xiaomi 11 Pro / Ultra (`star` / `mars`), featuring integrated **ReSukiSU / BakaSU**, **SuSFS v2.3.0**, and advanced **kernel-level detection counter-measures (Chunqiu Detector / MOMO / Root detection hardening)**.

---

## 📱 Supported Android Versions & ROMs

Because this kernel is packaged via **AnyKernel3 (boot-kernel-only)** without touching `vendor_boot`, device trees, or vendor partitions, it retains full ABI compatibility with Qualcomm Snapdragon 888 (`SM8350`) vendor drivers.

| Android Version | OS / ROM Examples | Status | Notes |
| :--- | :--- | :--- | :--- |
| **Android 14** | Xiaomi HyperOS 1.0 (OS1.0.x), AOSP 14 / LineageOS 21 | **Fully Supported** | Primary target platform; extensively tested. |
| **Android 13** | MIUI 14 (V14.0.x), AOSP 13 / LineageOS 20 | **Fully Supported** | Excellent battery life and thermal stability. |
| **Android 12** | MIUI 13 (V13.0.x), AOSP 12 / 12L | **Supported** | Compatible. |
| **Android 11** | MIUI 12.5 (Factory shipping version) | **Supported** | Factory baseline release. |
| **Android 15** | AOSP 15 (VanillaIceCream) / Custom ROMs | **Compatible** | Dependent on ROM vendor blobs matching SM8350 QGKI 5.4. |

> **Supported Devices**:
> - Xiaomi Mi 11 Pro (`star`)
> - Xiaomi Mi 11 Ultra (`star` / `mars`)

---

## ⚡ Key Kernel Features & Hardening

1. **ReSukiSU / BakaSU (v4.2.0-rc3)**:
   - Modern KernelSU fork with full root management and stealth enhancements.
   - Inline SuSFS hook without kprobes overhead.
2. **SuSFS v2.3.0**:
   - Advanced VFS and mount hiding (`hide_mount`, `sus_su`, `open_redirect`, `kstat` spoofing).
   - `/proc/[pid]/fdinfo` and `inotify_fdinfo` leak protection.
   - `vfs_statfs` filesystem signature hiding.
3. **Chunqiu Detector & Advanced Anti-Detection Countermeasures**:
   - **Tampered Kernel Bypassed**: Compiler banner spoofed to official `Android Clang 12.0.5 (r416183b)` with standardized OEM build host and timestamp (`c3-miui-ota-bd174.bj`).
   - **Three-way Uname Spoofing**: `/proc/version` is synchronized with `sys_newuname` under SuSFS.
   - **`/data/local/tmp` Inode & Metadata Spoofing**: Automatically reports official baseline `ino=156`, `uid:gid=2000:2000` (`shell:shell`), and `0771` mode for unprivileged processes (`UID >= 10000`).
   - **SELinux Live Policy Protection**:
     - Status page mapping (`/sys/fs/selinux/status`) returns a sanitized zeroed state (`sequence=0`, `policyload=0`, `enforcing=1`) to isolate apps from detecting policy reloads.
     - Raw access queries (`/sys/fs/selinux/access`) mask DirtySepolicy permissions (`system_server execmem`, `zygote adb_data_file search`) and lock `avd.seqno=1`.

---

## 🛠️ Quick Upgrade Guide (KSU & SuSFS)

### 1. Upgrading KernelSU / ReSukiSU
KernelSU is configured as a git submodule in the `KernelSU` directory:
```bash
cd KernelSU

# Check latest tags or commits
git fetch origin

# Switch to desired tag or branch (e.g. latest BakaSU / ReSukiSU)
git checkout <target_tag_or_branch>

# Return to kernel root and check if inline hooks need updating
cd ..
git status
```
*Tip: If upgrading across major versions, check `KernelSU/kernel/core_hook.c` or `susfs.c` to ensure SuSFS inline hooks remain compatible.*

### 2. Upgrading SuSFS
When new SuSFS versions (e.g. v2.4.x) are released:
1. Replace the patch files in `include/linux/susfs.h` and `fs/susfs.c`.
2. Apply the updated kernel patches (`fs/stat.c`, `fs/open.c`, `fs/proc/version.c`, etc.).
3. Update the matching SuSFS companion module and `ksu_susfs` inline hooks.

---

## 📦 Flashing Guide

1. Download the AnyKernel3 zip package from [GitHub Releases](https://github.com/dundwv/android_kernel_xiaomi_sm8350_star/releases).
2. Reboot your device into TWRP / OrangeFox recovery.
3. **Backup your current `boot` partition** (recommended).
4. Flash `star-5.4.274-qgki-g4dfe63e0666f-AK3-r*.zip`.
5. Reboot system. Install matching `BakaSU` manager APK.

---

## 🇨🇳 中文说明摘要 (Summary in Chinese)

本内核是针对小米 11 Pro / Ultra (`star` / `mars`, 骁龙 888) 深度定制的 QGKI 5.4.274 纯内核包，适用于 **Android 11 至 Android 14 (包括 MIUI 12.5/13/14 及澎湃 HyperOS 1.0)**。深度集成了 **ReSukiSU / BakaSU** 与 **SuSFS v2.3.0**，并在内核层针对**春秋检测器 (Chunqiu Detector)** 实现了系统级防御（彻底解决 Tampered kernel 编译器指纹、SELinux Policy 实时探针、`/data/local/tmp` inode 与权限伪装）。

详细中文使用手册与技术细节请直接参阅：👉 [**README_CN.md**](README_CN.md)
