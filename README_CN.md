# 小米 11 Pro / Ultra (star / mars) 自编译内核

[**English Documentation**](README.md) | **中文说明文档**

小米 11 Pro / Ultra（`star` / `mars`，骁龙 888 / SM8350）的 QGKI 5.4.274 自编译内核，基于高通开源基线，集成 **ReSukiSU / BakaSU**、**SuSFS v2.3.0**、**Linux 5.10 Seccomp 位图快路径回移**，以及一组面向个人设备使用的**环境一致性兼容**调整。

---

## ⚠️ 使用范围与免责声明（请先阅读）

* **使用范围**：本项目是面向**个人自有设备**的兴趣向自编译内核，发布目的是 **Android 平台层技术研究**——内核构建可复现性、VFS / SELinux 内部机制、系统级性能优化。
* **不得用于规避**：**不得**用于对抗反作弊系统、DRM、银行与支付风控、企业 MDM 或任何访问控制机制，也不得用于欺诈、账号交易，或任何违反适用法律与目标应用条款的行为。
* **无担保**：刷入第三方内核可能导致设备变砖、OTA 失效、保修作废或数据丢失。备份与后果由使用者自行承担。
* **许可**：内核源码以 **GPL-2.0** 分发（见 [`COPYING`](COPYING)）。厂商闭源二进制、固件及第三方组件版权归各自所有者，本仓库**不重新分发**。KernelSU / SuSFS 组件保留其上游许可。
* **不含可滥用材料**：本仓库不含 keybox、不含 attestation 密钥材料、不含预编译 APK、不含厂商专有二进制。

如果你的使用场景与上述不符，请不要使用本项目。

---

## 📱 适用 Android 系统版本与 ROM

本内核采用 **AnyKernel3 纯 boot 镜像**方式打包：只替换现有 `boot` 分区 ramdisk 内的 `Image.gz`，不改动 `vendor_boot`、`dtbo`、`vbmeta` 与 vendor 分区，因此与骁龙 888（SM8350）原厂 vendor 驱动保持 ABI 兼容。

| Android 系统版本 | 适配系统 / ROM 示例 | 兼容状态 | 说明 |
| :--- | :--- | :--- | :--- |
| **Android 14** | 小米澎湃 OS (HyperOS 1.0.x)、AOSP 14 / LineageOS 21 | **完整支持** | 主要测试平台 |
| **Android 13** | MIUI 14 (V14.0.x)、AOSP 13 / LineageOS 20 | **完整支持** | 功耗与温控表现稳定 |
| **Android 12** | MIUI 13 (V13.0.x)、AOSP 12 / 12L | **支持** | — |
| **Android 11** | MIUI 12.5（出厂底包） | **支持** | 原厂基线 |
| **Android 15** | AOSP 15 / 第三方移植 | **兼容** | 需 ROM 的 vendor blobs 匹配 SM8350 QGKI 5.4 |

> **支持设备**：小米 11 Pro（`star`）· 小米 11 Ultra（`star` / `mars`）

---

## ⚡ 内核特性

### 1. Root 与命名空间隔离层

* **ReSukiSU / BakaSU (v4.2.0-rc3)**：持续维护的 KernelSU 分支，采用 **inline hook** 模型而非可选 kprobes，不产生额外的指令陷入开销，也不留下 tracepoint 足迹。
* **SuSFS v2.3.0**：作用域化的文件系统命名空间层：
  * `sus_path`、`sus_mount`、`sus_kstat`、`open_redirect`、`sus_map`：使模块路径不出现在常规路径查询中；
  * `/proc/<pid>/fdinfo` 与 `inotify_fdinfo` 过滤：内部路径不会经由文件描述符自省暴露；
  * `vfs_statfs` 归一化：挂载点上报预期的文件系统类型。

### 2. 环境一致性兼容（技术说明）

部分应用会执行**构建标识与系统状态的一致性校验**，一旦偏离原厂档位即判定为不受支持的环境。以下调整让本地编译的内核上报与原厂镜像**一致的确定性取值**——这也正是可复现构建（reproducible build）本身的要求。

* **确定性的构建标识**：`scripts/mkcompile_h` 支持 `KBUILD_COMPILER_STRING`，`build_star.sh` 固定工具链字符串（`Android (7284624, based on r416183b) clang version 12.0.5, LLD 12.0.5`）、`KBUILD_BUILD_USER` / `KBUILD_BUILD_HOST`、`KBUILD_BUILD_VERSION` 与 `KBUILD_BUILD_TIMESTAMP`。不同主机编译出的 banner 完全一致，不会泄露构建者的发行版与本地时钟。
* **版本字符串单一事实来源**：SuSFS 的 `uname` 处理接入 `fs/proc/version.c`，`uname(2)`、`/proc/version` 与 `/proc/sys/kernel/osrelease` 三者不可能出现不一致。
* **`/data/local/tmp` 属性对齐**：`fs/stat.c` 正确识别 `/data` 挂载点根（其 dentry 父级为 `"/"` 而非 `"data"`），并在首次识别时缓存 inode。非特权调用者（`uid >= 10000`）无论按路径还是按 fd 取 stat，得到的都是与原厂一致的 `ino=156`、`uid:gid=2000:2000`、`0771`。
* **SELinux 查询一致性**：仅对非特权调用者，`security/selinux/selinuxfs.c`：
  * 提供只读状态页，上报 `sequence=0`、`policyload=0`、`enforcing=1`，与从未重载过策略的状态一致；
  * 从 `/sys/fs/selinux/access` 应答中过滤掉仅由厂商/扩展策略引入的权限位（`system_server` 的 `PROCESS__EXECMEM`、`zygote` 对 `adb_data_file` 的 `DIR__SEARCH` / `DIR__READ`、`system_server` 对 `apk_data_file` 的 `FILE__EXECUTE`），并上报 `avd.seqno=1`；
  * 对原厂策略中不存在的 context 名，仍返回 `-EINVAL`。

  特权调用者（`uid < 10000`）完全不受影响——root 授权、`ksud` 与模块守护进程行为与之前一致。
* **UID 级优先级查询作用域限制** — `getpriority(PRIO_USER, …)`、`setpriority(PRIO_USER, …)`、`ioprio_get()` 与 `ioprio_set()` 可对任意 UID 查询"该 UID 是否有活跃进程"。`include/linux/uid_prio_filter.h` 将非特权跨应用 UID 查询限定为仅返回调用者自身 UID 的结果（返回 `-ESRCH`），使应用无法经由这些系统调用枚举其他应用的 UID。系统调用者（`uid < 10000`）与查询自身 UID 不受影响。
* **UID 级路径访问作用域限制**（`CONFIG_UID_PATH_FILTER`）— 路径解析与目录枚举可对任意调用者回答"某路径是否存在"。每条配置（UID， 路径后缀）——经 `/sys/kernel/uid_path_filter/config` 管理——使匹配后缀（组件对齐）的路径对该 UID 解析为 `-ENOENT`，并在目录枚举结果中省略匹配条目。其他调用者（包括路径所属应用自身）不受影响。比较时忽略零宽字符（`U+200B/200C/200D/FEFF`）；后缀匹配对外部存储树的各挂载别名（`/storage/emulated/<user>`、`/storage/self/primary`、`/sdcard`）行为一致。配套的模块 zip（见 release 资产）在开机时注入 SELinux 放行规则并应用配置。

### 3. 性能与稳定性

* **Seccomp 位图快路径（5.10 回移）**：把上游 `action_cache` 位图与 `seccomp_run_filters()` 快路径带到 5.4。高频安全系统调用跳过过滤器程序遍历，可测得地降低系统调用密集场景的微卡顿。
* **ThinLTO**：`CONFIG_THINLTO=y` + `CONFIG_LTO_CLANG=y`，跨编译单元内联，链接阶段开销可控。
* **FCM5 / VINTF 合规**：满足 `CONFIG_MODVERSIONS`、`CONFIG_ARM64_SW_TTBR0_PAN`、`CONFIG_CFI_CLANG`、`CONFIG_SHADOW_CALL_STACK` 与 `# CONFIG_DEBUG_FS is not set`；`.config` 通过 `bin2c` 嵌入内核，运行时 IKCONFIG 校验通过，"内部错误"弹窗不再出现。
* **Binder freeze 通知回退**：移除会在 SM8350 上引起偶发锁屏 / AOD 卡死的 Binder freeze 通知回移补丁。

---

## 🛠️ 编译环境准备

### 1. 基础依赖（Debian / Ubuntu）
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential bc bison flex libssl-dev libelf-dev libncurses5-dev \
    git curl wget zip unzip cpio python3 python-is-python3 binutils-aarch64-linux-gnu
```

### 2. 工具链（LLVM / Clang）
* **首选**：AOSP Clang `r416183b`（Clang 12.0.5）或更新版本——与上面固定的 banner 字符串匹配。
* **备选**：任意 `clang >= 12`，并确保 `lld`、`llvm-ar`、`llvm-nm`、`llvm-objcopy`、`llvm-strip` 在 `$PATH` 中。
* 自检：`clang -v && ld.lld -v`。

### 3. 源码与子模块
```bash
git clone https://github.com/drawmenn/android_kernel_xiaomi_sm8350_star.git -b 5.4.274-qgki-4dfe63e0666f kernel-star
cd kernel-star
git submodule update --init --recursive     # 必须：KernelSU 在此子模块中
```

> **子模块说明**：`.gitmodules` 指向维护者的 KernelSU 分支，其中包含本内核所需的 `seccomp_cache` 提交（上游 ReSukiSU 目前尚未合并）。若该分支不可用，改为指向你自己的副本：
> ```bash
> git submodule set-url KernelSU https://github.com/<你的用户名>/BakaSU.git
> git submodule update --init --recursive
> ```

---

## 🔄 升级 KernelSU / SuSFS

### 1. KernelSU / ReSukiSU

快速路径——上游更新几乎全是 Manager/ksud-only，多数情况下**完全不用动内核**：

```bash
./sync_ksu.sh --check   # 退出码 0 = 只需装 APK，10 = 需要内核侧同步
./sync_ksu.sh           # 全流程：rebase fork、更新子模块、重编、打包
```

* **上游无新提交** → 无事可做。
* **有新提交但都不在 `kernel/` 下** → 只需安装最新的 Manager APK（注意应用内"检查更新"可能落后于 CI、反而提示降级）。装好 APK 后 ksud 会自行更新。
* **有 `kernel/` 下的提交** → 脚本会 rebase fork 分支（`star-5.4-seccomp-cache`）、推送 fork、更新子模块并重编。子模块指针提交保留在本地，直到设备验证通过（分阶段发布协议）。

手动固定到指定版本：

```bash
cd KernelSU
git fetch origin
git checkout <tag-or-commit>     # 固定具体 tag，不要跟随移动的分支
cd ..
git add KernelSU && git commit -m "ksu: bump to <tag>"
```
跨大版本升级时，先核对 `KernelSU/kernel/core_hook.c` 里的 inline hook 原型（以及 `susfs` 胶水层）是否与树内 SuSFS 版本匹配，再开始编译。

### 2. SuSFS
1. 新版 `susfs.h` 覆盖到 `include/linux/susfs.h`，`susfs.c` 覆盖到 `fs/susfs.c`。
2. 比对 VFS 挂接点：`fs/stat.c`、`fs/statfs.c`、`fs/open.c`、`fs/proc/fd.c`、`fs/notify/fdinfo.c`、`fs/proc/version.c`。
3. 同步 KernelSU 子模块内的 `ksu_susfs` 胶水代码。
4. 重新编译，并搭配版本号一致的用户态 SuSFS 模块。

---

## 🔨 编译

```bash
./build_star.sh
```
脚本会应用 `star_dsl_defconfig`，强制校验 FCM5 与 seccomp 门槛（任一缺失即中止），然后构建 `Image.gz`、`dtbs` 与 `modules`。

产物：`out-star-5.4.274-qgki-g4dfe63e0666f/arch/arm64/boot/Image.gz`

可用开关：`JOBS=<n>`、`OUT_DIR=<路径>`、`CONFIG_ONLY=1`（只生成 `.config` 后停止）、`BBR3=1`（改用 BBRv3 + `fq` 替代 CUBIC/pfifo_fast）。

### GitHub Actions（云端编译）

`.github/workflows/build-kernel.yml` 会在 `ubuntu-24.04`（系统 clang 18）上编译本内核，并把 AnyKernel3 刷机包与 config 作为 Actions 产物上传——本地无需编译环境。触发方式：推送到 `ci/**`、推送到默认分支、手动触发（`workflow_dispatch`）。

* `ci/**` 用于不含未验证内核改动的引用（例如 KernelSU 子模块指针更新）：推送后云端编译，直接下载产物刷入。
* CI 不会创建 GitHub Release：正式发布仍由人工在设备验证通过后操作。
* LTO 不具确定性：源码完全相同的 CI 产物与本地产物不是逐字节一致的。要发布哪个 zip，就刷入并验证哪个。

---

## 📥 刷入

1. 从 [Releases](https://github.com/drawmenn/android_kernel_xiaomi_sm8350_star/releases) 下载 AnyKernel3 刷机包。
2. 进入 TWRP / OrangeFox Recovery。
3. **先备份 `boot` 分区**。
4. 刷入 `star-5.4.274-qgki-g4dfe63e0666f-AK3-r*.zip`。
5. 重启，安装版本匹配的 BakaSU 管理器 APK。

---

## 🌐 English README Reference

For English documentation and details, see: 👉 [**README.md**](README.md)
