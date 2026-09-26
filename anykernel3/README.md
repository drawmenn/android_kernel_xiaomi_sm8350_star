# AnyKernel3 package template

This directory contains the AnyKernel3 packaging template for the Xiaomi 11
Ultra (`star`) port. It is kept separate from the kernel source while remaining
in the same repository so the installer changes are reviewable and reproducible.

The package accepts `star` and `mars`. The installer caches the Recovery-side
device properties before `setup_env` mounts the Android partitions. This avoids
the Xiaomi 11 Ultra Recovery environment being misidentified as `venus` after
the mount step.

## Build

Build the kernel first with `./build_star.sh`, then run:

```sh
./anykernel3/build.sh
```

The default input is:

```text
out-star-5.4.302/arch/arm64/boot/Image.gz
```

`build_star.sh` adds the Asia/Shanghai build date (`yyMMdd`) to the kernel
release, for example `5.4.302-ikun-NekoMake-star-260927-qgqi+`. The package
script reads that release from `OUT_DIR/include/config/kernel.release` and uses
it for the Recovery banner and, without `PACKAGE_NAME`, the ZIP filename (with
the trailing `+` omitted). Build the kernel again before packaging after a
date change.

Override `IMAGE`, `OUT_DIR`, or `PACKAGE_NAME` when needed. Keep `IMAGE` and
`OUT_DIR` from the same build to avoid a mismatched name. The generated
`Image.gz` and ZIP are ignored by this directory's `.gitignore`.
