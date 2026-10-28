#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/out-venus-5.4.285}"
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

make "${MAKE_ARGS[@]}" venus_defconfig
"$ROOT_DIR/scripts/config" --file "$OUT_DIR/.config" \
  --enable ZRAM \
  --enable CRYPTO_LZ4 \
  --enable ZRAM_DEF_COMP_LZ4 \
  --disable ZRAM_DEF_COMP_LZORLE \
  --disable ZRAM_DEF_COMP_LZO \
  --disable ZRAM_DEF_COMP_ZSTD \
  --disable ZRAM_DEF_COMP_LZ4HC \
  --disable ZRAM_DEF_COMP_842
make "${MAKE_ARGS[@]}" olddefconfig
grep -q '^CONFIG_ZRAM_DEF_COMP="lz4"$' "$OUT_DIR/.config" || {
  echo "ERROR: ZRAM default compressor is not lz4" >&2
  exit 1
}
make -j"$JOBS" "${MAKE_ARGS[@]}" Image.gz dtbs

echo "Image.gz: $OUT_DIR/arch/arm64/boot/Image.gz"
