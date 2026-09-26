#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_DIR="$ROOT_DIR/anykernel3"
IMAGE="${IMAGE:-$ROOT_DIR/out-star-5.4.302/arch/arm64/boot/Image.gz}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/out-star-5.4.302}"
KERNEL_RELEASE_FILE="$OUT_DIR/include/config/kernel.release"

if [ ! -f "$KERNEL_RELEASE_FILE" ]; then
  echo "Kernel release not found: $KERNEL_RELEASE_FILE (build the kernel first)" >&2
  exit 1
fi

KERNEL_RELEASE="$(<"$KERNEL_RELEASE_FILE")"
if [[ ! "$KERNEL_RELEASE" =~ ^[A-Za-z0-9._+-]+$ ]]; then
  echo "Invalid kernel release: $KERNEL_RELEASE" >&2
  exit 1
fi

PACKAGE_NAME="${PACKAGE_NAME:-${KERNEL_RELEASE%+}}"
PACKAGE="$OUT_DIR/$PACKAGE_NAME.zip"

if [ ! -f "$IMAGE" ]; then
  echo "Kernel image not found: $IMAGE" >&2
  exit 1
fi

command -v zip >/dev/null 2>&1 || {
  echo "The zip utility is required." >&2
  exit 1
}

mkdir -p "$OUT_DIR"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

cp -a "$TEMPLATE_DIR/anykernel.sh" "$TEMPLATE_DIR/LICENSE" "$TEMPLATE_DIR/tools" "$TEMPLATE_DIR/META-INF" "$STAGE/"
cp -f "$IMAGE" "$STAGE/Image.gz"
sed -i "s|@KERNEL_RELEASE@|$KERNEL_RELEASE|g" "$STAGE/anykernel.sh"
chmod 755 "$STAGE/META-INF/com/google/android/update-binary" "$STAGE/tools"/*

rm -f "$PACKAGE"
(
  cd "$STAGE"
  zip -qr -9 "$PACKAGE" .
)

echo "Built: $PACKAGE"
sha256sum "$PACKAGE"
