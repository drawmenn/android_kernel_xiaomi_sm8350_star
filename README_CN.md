# 小米 11 Pro / Ultra (star / mars) 深度定制安全内核

[**English Documentation**](README.md) | **中文说明文档**

本项目是专为 **小米 11 Pro / Ultra (`star` / `mars`, 骁龙 888 - SM8350)** 定制的高通通用内核镜像 (QGKI 5.4.274)。
内核深度集成了 **ReSukiSU / BakaSU**、**SuSFS v2.3.0**、**Linux 5.10 Seccomp 位图加速**，并在内核底层实现了对 **春秋检测器 (Chunqiu Detector)**、MOMO 等高阶检测机制的硬件级/内核级静默防御。

---

## 📱 适用 Android 系统版本与 ROM

本内核采用 **AnyKernel3 (Boot-Kernel-Only)** 打包方式，仅替换 `boot` 分区中的内核执行镜像（`Image.gz`），不触动系统的 `ramdisk`、`vendor_boot` 分区以及设备树（DTB/DTBO），因此能够完美继承原厂高通驱动 ABI：

| Android 系统版本 | 适配系统 / ROM 示例 | 兼容状态 | 说明 |
| :--- | :--- | :--- | :--- |
| **Android 14** | 小米澎湃 OS (Xiaomi HyperOS 1.0.x), AOSP 14 / LineageOS 21 | **完美支持 (推荐)** | 当前主力适配与实测环境 |
| **Android 13** | MIUI 14 (V14.0.x), AOSP 13 / LineageOS 20 | **完美支持** | 功耗与温控表现极佳 |
| **Android 12** | MIUI 13 (V13.0.x), AOSP 12 / 12L | **完全兼容** | 稳定运行 |
| **Android 11** | MIUI 12.5 (出厂预装底包) | **完全兼容** | 骁龙 888 原厂基线 |
| **Android 15** | AOSP 15 (VanillaIceCream) / 第三方移植 | **兼容** | 需 ROM 厂商底包符合 5.4 通用接口 |

> **支持设备列表**：
> - 小米 11 Pro (`star`)
> - 小米 11 Ultra (`star` / `mars`)

---

## 🛡️ 内核特性与架构亮点

### 1. 深度安全与隐匿底座
- **ReSukiSU / BakaSU (v4.2.0-rc3)**：
  - 基于 KernelSU 深度优化的现代 Root 管理器，支持多管理器鉴权共存。
  - 采用 **Inline Hook 架构** 替代传统 kprobes，消除 tracepoint 泄露与执行性能开销。
- **SuSFS v2.3.0 协议全功能集成**：
  - 全套 VFS 挂载隔离与隐藏：`sus_path`、`sus_mount`、`sus_kstat`、`open_redirect` 与 `sus_map`。
  - 文件描述符防泄露：针对 `/proc/[pid]/fdinfo` 和 `inotify_fdinfo` 进行内核级过滤，拦截针对隐藏文件的探测。
  - `vfs_statfs` 文件系统特征伪装，屏蔽 overlayfs、tmpfs 特征。
- **针对春秋检测器 (Chunqiu Detector) 的内核级防御**：
  - **解决 `Tampered kernel` (篡改/非官方内核)**：
    * 固化官方 Android NDK Clang 编译器签名：`Android (7284624, based on r416183b) clang version 12.0.5, LLD 12.0.5`。
    * 固化官方 OTA 构建主机与稳定时间戳：`android-build@c3-miui-ota-bd174.bj`（`Wed May 8 16:00:00 CST 2024`）。
    * 实现 `/proc/version` 与 `uname -r` 三路绝对对齐，消除编译器指纹与编译环境暴露。
  - **解决 `Suspicious Surroundings (b)` (`/data/local/tmp` 元数据异常)**：
    * 适配 Android 独立挂载点根目录识别，引入 inode 动态关联缓存。
    * 非特权应用（UID >= 10000）无论是通过路径还是文件句柄（fd）调用 `stat` 扫描 `/data/local/tmp`，内核强制伪装返回出厂标准值：**`ino=156`**、**`uid:gid=2000:2000`** (`shell:shell`)、权限 **`0771`**。
  - **解决 `检测SELinux Policy时发现可疑问题`**：
    * **`status.sequence / policyload`**：非特权进程映射 `/sys/fs/selinux/status` 时，内核返回独立洁净状态页，强制呈现 `sequence=0`、`policyload=0`、`enforcing=1`，彻底切断检测器利用策略重载判定 Root。
    * **屏蔽通用脏规则**：对非特权进程查询掩盖 `system_server execmem`、`zygote adb_data_file search` 与 `system_server` 执行 apk 权限。
    * **伪造决策序号**：将 `avd.seqno` 强制固化为 `1`。

### 2. 性能与系统稳定性优化
- **Linux 5.10 Seccomp Bitmap Fastpath (Backport)**：
  - 从 Linux 5.10 主线反向移植 Seccomp Cache 机制（`action_cache` 位图）。高频无害系统调用直接跳过 BPF 规则遍历求值，显著减少应用运行与高负载下的微卡顿。
- **编译器级 ThinLTO 全局优化**：
  - 开启 Clang ThinLTO（`CONFIG_THINLTO=y`, `CONFIG_LTO_CLANG=y`），跨编译单元实现函数内联与指令重排，降低内存占用并提升调度执行效率。
- **全面遵循 Android FCM5 与 VINTF 规范**：
  - 满足 Google FCM 5 全套强制要求（`CONFIG_ARM64_SW_TTBR0_PAN=y`、`CONFIG_CFI_CLANG=y`、`CONFIG_SHADOW_CALL_STACK=y`）。
  - 通过 `bin2c` 将 `.config` 静态嵌入内核，确保系统运行时 VINTF / IKCONFIG 校验完全放行，消除“内部错误/内核不兼容”系统弹窗。
- **锁屏/熄屏卡死修复 (Binder Lockscreen Freeze Fix)**：
  - 剔除了引起高通 888 机型在熄屏/AOD 下偶发死锁的第三方 Binder Freeze 通知反向补丁，恢复原生稳定通信机制。

---

## 🛠️ 通用升级指南 (KSU & SuSFS)

### 1. 通用方法：升级 KernelSU / ReSukiSU
KernelSU 在本内核源码中作为 Git Submodule 挂载在源码根目录下的 `KernelSU/` 文件夹中：
```bash
# 1. 在你的内核源码根目录中，进入 KernelSU 子模块
cd KernelSU

# 2. 从远端拉取最新上游更新（Tags 或 分支）
git fetch origin

# 3. 检出目标发布的 Release Tag 或特定 Commit
git checkout <新Tag或Commit>

# 4. 返回内核源码根目录
cd ..

# 5. 核对并编译
# (跨大版本升级时，请确认 KernelSU/kernel/core_hook.c 中的 SuSFS inline hook 函数定义与签名匹配)
```

### 2. 通用方法：升级 SuSFS
当 SuSFS 发布新版本协议规范（例如升级到 v2.4.x）时：
1. **更新核心定义与代码**：将上游发布的最新 `susfs.h` 替换到内核源码的 `include/linux/susfs.h`，最新 `susfs.c` 替换到 `fs/susfs.c`。
2. **检查 VFS 挂钩差异**：对比并更新关键 VFS 挂载与文件操作钩子（如 `fs/stat.c`、`fs/statfs.c`、`fs/open.c`、`fs/proc/fd.c`、`fs/notify/fdinfo.c`、`fs/proc/version.c` 等）。
3. **同步 KernelSU 钩子**：更新 KernelSU 侧 `ksu_susfs` 的 inline 适配代码。
4. **触发全量编译**：编译生成新的内核镜像与 AnyKernel3 刷机包，并搭配对应版本号的 SuSFS 模块使用。

---

## 📥 刷入说明

1. 从 [GitHub Releases](https://github.com/dundwv/android_kernel_xiaomi_sm8350_star/releases) 下载最新的 AnyKernel3 刷机包（例如 `star-5.4.274-qgki-g4dfe63e0666f-AK3-r4.zip`）。
2. 设备进入 TWRP / OrangeFox Recovery。
3. （强烈建议）在 Recovery 中备份当前 `boot` 分区。
4. 刷入下载的 zip 包（无需双清）。
5. 重启进入系统，安装并打开配套的 `BakaSU` 管理器 APK。

---

## 🌐 English README Reference

For English documentation and details, see: 👉 [**README.md**](README.md)
