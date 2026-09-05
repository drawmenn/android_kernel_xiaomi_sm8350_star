#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/out-star-5.4.302}"
JOBS="${JOBS:-$(nproc)}"

export ARCH=arm64
export SUBARCH=arm64
export LLVM=1
export LLVM_IAS=1
export CC=clang
export LD=ld.lld
export AR=llvm-ar
export NM=llvm-nm
export OBJCOPY=llvm-objcopy
export OBJDUMP=llvm-objdump
export STRIP=llvm-strip
export READELF=llvm-readelf

MAKE_ARGS=(
  O="$OUT_DIR"
  ARCH="$ARCH"
  SUBARCH="$SUBARCH"
  LLVM="$LLVM"
  LLVM_IAS="$LLVM_IAS"
  CC="$CC"
  LD="$LD"
  AR="$AR"
  NM="$NM"
  OBJCOPY="$OBJCOPY"
  OBJDUMP="$OBJDUMP"
  STRIP="$STRIP"
  READELF="$READELF"
)

cd "$ROOT_DIR"
mkdir -p "$OUT_DIR"

# This defconfig was derived from the working Mi 11 Ultra vendor kernel
# configuration, then adjusted for the star target and the NekoMake feature set.
make "${MAKE_ARGS[@]}" star_dsl_defconfig

scripts/config --file "$OUT_DIR/.config" \
  --set-str LOCALVERSION "-ikun-NekoMake-star-qgqi" \
  --enable MACH_XIAOMI \
  --enable MACH_XIAOMI_SM8350 \
  --enable MACH_XIAOMI_STAR \
  --enable MODULES \
  --enable INPUT_AW8697_HAPTIC \
  --enable QTI_BATTERY_CHARGER \
  --enable MI_THERMAL_INTERFACE \
  --enable SOUND \
  --enable SND_SOC \
  --enable AUDIO_QGKI \
  --enable LEDS_QPNP_VIBRATOR_LDO \
  --enable ZRAM \
  --enable ZRAM_MULTI_COMP \
  --enable CRYPTO_LZ4 \
  --enable ZRAM_DEF_COMP_LZ4 \
  --enable F2FS_FS_COMPRESSION \
  --enable F2FS_FS_LZO \
  --enable F2FS_FS_LZORLE \
  --enable F2FS_FS_LZ4 \
  --enable F2FS_FS_LZ4HC \
  --enable F2FS_FS_ZSTD \
  --enable F2FS_UNFAIR_RWSEM \
  --enable F2FS_CP_OPT \
  --enable KSU \
  --enable KSU_MULTI_MANAGER_SUPPORT \
  --enable KSU_DISABLE_IN_RECOVERY \
  --disable KSU_TRACEPOINT_HOOK \
  --disable KSU_MANUAL_HOOK \
  --enable KSU_SUSFS \
  --enable KSU_SUSFS_SUS_PATH \
  --enable KSU_SUSFS_SUS_MOUNT \
  --enable KSU_SUSFS_SUS_KSTAT \
  --enable KSU_SUSFS_SPOOF_UNAME \
  --enable KSU_SUSFS_ENABLE_LOG \
  --enable KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS \
  --enable KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG \
  --enable KSU_SUSFS_OPEN_REDIRECT \
  --enable KSU_SUSFS_SUS_MAP \
  --enable KALLSYMS \
  --enable KALLSYMS_ALL \
  --enable BPF_STREAM_PARSER \
  --enable LRU_GEN \
  --disable LRU_GEN_ENABLED \
  --disable LRU_GEN_STATS \
  --enable OPLUS_FEATURE_HANS \
  --enable MILLET \
  --disable KPM

make "${MAKE_ARGS[@]}" olddefconfig
make -j"$JOBS" "${MAKE_ARGS[@]}" Image.gz dtbs modules

echo "Built: $OUT_DIR/arch/arm64/boot/Image.gz"
