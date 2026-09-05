# Xiaomi 11 Ultra (`star`) port

This fork keeps the `venus-5.10bpf` base and adds a reproducible `star`
build configuration for the Xiaomi 11 Ultra.

The tested build enables the `star` machine target, kernel module support,
QGKI audio, the Xiaomi battery/thermal drivers, AW8697 haptics, and the
QPNP vibrator LDO. The resulting kernel was tested with `fastboot boot` on
an M2102K1C and registered `lahaina-mtp-snd-card`, `/dev/snd`, and the
vibrator sysfs device.

## Build

Build inside Debian 13 or another Linux environment with the Android kernel
toolchain and the dependencies used by the upstream tree:

```sh
JOBS=$(nproc) ./build_star.sh
```

The kernel image is written to:

```text
out-star-5.4.302/arch/arm64/boot/Image.gz
```

`star_dsl_defconfig` is the corresponding reduced configuration for the
tested image. The `KernelSU` gitlink must be checked out at the revision
recorded by the repository.

This is an experimental third-party kernel port. Use `fastboot boot` for
initial testing and keep a known-good boot image available. No warranty is
provided.
