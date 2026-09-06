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

Override `IMAGE`, `OUT_DIR`, or `PACKAGE_NAME` when needed. The generated
`Image.gz` and ZIP are ignored by this directory's `.gitignore`.
