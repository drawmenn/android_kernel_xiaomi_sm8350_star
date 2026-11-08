# UID Path Filter Rules — KSU 模块

[English](README.md)

KernelSU 配套模块，用于管理自定义内核中的按 UID 路径可见性作用域功能。
提供 Material Design 3 风格的 WebUI，管理哪些应用 UID 对指定
`/Android/data/` 目录后缀的访问被作用域限制。

## 前置条件

- 使用 `CONFIG_UID_PATH_FILTER` 编译的内核（本仓库分支
  `5.4.274-qgki-4dfe63e0666f` 的 r6 或更高版本发布）
- KernelSU 或兼容的 Root 管理器（BakaSU / ReSukiSU）
- arm64 SELinux 策略二进制文件（源码中不含，见下文）

## 获取策略二进制

模块在安装时需要 arm64 SELinux 策略二进制文件来授予对 sysfs 配置
节点的写权限。

1. 下载[上游管理器 v31.1 APK](https://github.com/topjohnwu/Magisk/releases)
2. 从 APK 中提取 `lib/arm64-v8a/libmagiskpolicy.so`
3. 重命名为 `magiskpolicy` 并放在本目录下

也可以直接使用
[r6 发布](https://github.com/drawmenn/android_kernel_xiaomi_sm8350_star/releases)
中的预构建 ZIP，其中已包含该二进制文件。

## 打包模块 ZIP

```sh
zip -r uid_path_filter_rules.zip \
  module.prop customize.sh control.sh service.sh \
  sepolicy.rule magiskpolicy appnames.dex webroot
```

将生成的 ZIP 在 Root 管理器中刷入。

## 文件结构

```
├── module.prop         模块元数据
├── customize.sh        安装时权限修复（应对 BakaSU 的 0644 安装权限）
├── control.sh          命令后端（init/status/apps/labels/save/apply/log/update_desc）
├── service.sh          开机自动应用，30 次重试
├── sepolicy.rule       SELinux 授权规则（供支持安装时应用的管理器使用；BakaSU 在开机时注入等效规则）
├── magiskpolicy        arm64 SELinux 策略工具（源码中不含，见上文）
├── appnames.dex        应用显示名称辅助工具（源码中不含——release ZIP 已包含；改自开源 UID- 项目）
└── webroot/
    ├── index.html      WebUI 标记
    ├── style.css       Material Design 3 主题（深色/浅色自适应）
    ├── app.js          WebUI 逻辑（ksu.exec 桥接）
    └── fonts/
        └── material-symbols.woff2  Material Symbols 图标字体（Apache 2.0, Google）
```

## 工作原理

模块向 `/sys/kernel/uid_path_filter/config` 写入规则，格式为
`add <uid> /Android/data/<pkg>`。内核在指定 UID 执行路径查找或目录
枚举时，对匹配的后缀返回 `-ENOENT`。

写入完成后，`control.sh apply` 回读内核表并校验每条规则是否确实落地。
如果任何写入失败或表内条数与预期不符，会报错而非静默成功。

开机时，`service.sh` 以 2 秒间隔重试应用最多 30 次，等待包管理器就绪，
随后将当前状态写入 `module.prop` 的描述字段（如 `✓ 4 rules active`），
使 Root 管理器的模块列表直接反映运行状态。

WebUI 的应用选择器以应用显示名称列出已安装应用（通过内置的
`appnames.dex` 在 `app_process` 下运行，失败时回退为包名），并将
当前已选条目排在列表最上方。

## 配置

编辑 `/data/adb/uid_path_filter_rules/config` 或使用 WebUI：

- `target=<pkg>` — 被作用域限制的应用（一个或多个）
- `pkg=<pkg>` — 要限制的目录后缀（一个或多个）

每个 target × package 对生成一条内核规则。内核表容量 256 条。

## 免责声明

本模块及底层内核功能仅面向技术研究和自有设备的环境定制，在内核层按
UID 作用域限制文件系统可见性。请合规使用，遵守相关服务条款。

---

[English](README.md)
