# 小米 11 Pro / Ultra (star / mars) 深度定制安全内核

[**English Documentation**](README.md) | **中文说明文档**

本项目是专为 **小米 11 Pro / Ultra (`star` / `mars`, 骁龙 888 - SM8350)** 定制的高通通用内核镜像 (QGKI 5.4.274)。
内核深度集成了 **ReSukiSU / BakaSU**、**SuSFS v2.3.0**、**Linux 5.10 Seccomp 高速位图加速**，并在内核底层实现了对 **春秋检测器 (Chunqiu Detector)**、MOMO 等高阶检测机制的硬件级/内核级静默防御。

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

## 🛡️ 内核特性与春秋检测防御机制

### 1. 深度 Root 与隐藏底座
- **ReSukiSU / BakaSU (v4.2.0-rc3)**：基于 KernelSU 深度优化的现代 Root 管理器，内置 SuSFS Inline Hook（零 kprobes 开销）。
- **SuSFS v2.3.0**：高级 VFS 挂载隐藏与重定向系统（`hide_mount`、`sus_su`、`open_redirect`、`kstat` 属性伪装）。
- **Seccomp Cache**：Backport 自 Linux 5.10，位图加速系统调用过滤，大幅降低应用卡顿。

### 2. 针对春秋检测器 (Chunqiu Detector) 的内核级防御
1. **解决 `Tampered kernel` (篡改/非官方内核)**：
   - 固化官方 Android NDK Clang 编译器签名：`Android (7284624, based on r416183b) clang version 12.0.5, LLD 12.0.5`。
   - 固化官方 OTA 构建主机与稳定时间戳：`android-build@c3-miui-ota-bd174.bj`（`Wed May 8 16:00:00 CST 2024`）。
   - 实现 `/proc/version` 与 `uname -r` 三路绝对对齐。
2. **解决 `Suspicious Surroundings (b)` (`/data/local/tmp` 元数据异常)**：
   - 识别 Android `/data` 挂载点根目录 `dentry`，并建立 inode 动态缓存。
   - 非特权应用（UID >= 10000）无论是通过路径还是文件句柄调用 `stat` 扫描 `/data/local/tmp`，内核强制伪装返回出厂标准值：**`ino=156`**、**`uid:gid=2000:2000`** (`shell:shell`)、权限 **`0771`**。
3. **解决 `检测SELinux Policy时发现可疑问题`**：
   - **`status.sequence / policyload`**：非特权进程映射 `/sys/fs/selinux/status` 时，内核返回独立洁净状态页，强制呈现 `sequence=0`、`policyload=0`、`enforcing=1`，彻底切断检测器利用策略重载判定 Root。
   - **屏蔽通用脏规则**：对非特权进程查询掩盖 `system_server execmem`、`zygote adb_data_file search` 与 `system_server` 执行 apk 权限。
   - **伪造决策序号**：将 `avd.seqno` 强制固化为 `1`。

---

## 🚀 升级 KernelSU 和 SuSFS 的快捷方法

当后续上游发布新版本时，按以下极简流程即可完成升级：

### 快捷方法 A：升级 KernelSU / ReSukiSU
KernelSU 在本仓库中作为 Git Submodule 挂载在 `KernelSU/` 目录：
```bash
# 1. 进入 KernelSU 子模块目录
cd /workspace/kernel-research/star-261030/KernelSU

# 2. 拉取最新上游分支或标签
git fetch origin

# 3. 检出目标版本（例如切换到最新的 release tag 或稳定 commit）
git checkout <新Tag或Commit>

# 4. 回到内核根目录，验证并重新编译
cd ..
./build_star.sh
```
> **提示**：若跨大版本升级，请快速核对 `KernelSU/kernel/core_hook.c`，确保其与 SuSFS 的 inline hook 接口定义匹配。

### 快捷方法 B：升级 SuSFS
当 SuSFS 发布新版本协议（如 v2.4.x）时：
```bash
# 1. 替换头文件与核心实现
# 将新版本的 susfs.h 放入 include/linux/susfs.h
# 将新版本的 susfs.c 放入 fs/susfs.c

# 2. 检查 VFS 补丁差异
# 对比 fs/stat.c、fs/open.c、fs/proc/version.c 等文件是否有新增 hook 点

# 3. 同步更新 KernelSU 端的 susfs inline 钩子
# 4. 执行 ./build_star.sh 重新生成 AnyKernel3 刷机包
```

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
