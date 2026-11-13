#!/usr/bin/env bash
# sync_ksu.sh — fast-path updater for the in-kernel KernelSU (ReSukiSU/BakaSU fork)
#
# Upstream updates are almost always Manager/ksud-only; kernel-side code
# (kernel/ inside the submodule) changes rarely. This script checks first
# and skips the whole rebuild when nothing kernel-side changed:
#
#   - no new upstream commits          -> nothing to do
#   - new commits, none touch kernel/  -> install the newest Manager APK only
#   - new commits touch kernel/        -> rebase fork, push it, bump the
#                                         submodule, rebuild, repackage
#
# Usage:
#   ./sync_ksu.sh [--check]
#
#   --check   report status only; never modify anything
#             (exit 0 = no kernel work needed, 10 = kernel-side sync needed)
#
# Environment overrides:
#   KSU_UPSTREAM_URL     default https://github.com/ReSukiSU/ReSukiSU.git
#   KSU_UPSTREAM_REMOTE  remote name holding upstream (default: origin)
#   KSU_FORK_REMOTE      remote name of your fork (default: myfork)
#
# Release-protocol note: only the KernelSU fork is pushed immediately (it is
# upstream main + one public commit). The submodule bump commit made in this
# repository stays LOCAL until device verification passes.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KSU_DIR="$ROOT_DIR/KernelSU"
BRANCH="star-5.4-seccomp-cache"
UPSTREAM_URL="${KSU_UPSTREAM_URL:-https://github.com/ReSukiSU/ReSukiSU.git}"
UPSTREAM_REMOTE="${KSU_UPSTREAM_REMOTE:-origin}"
FORK_REMOTE="${KSU_FORK_REMOTE:-myfork}"

CHECK_ONLY=0
if [[ "${1:-}" == "--check" ]]; then
  CHECK_ONLY=1
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--check]" >&2
  exit 2
fi

cd "$KSU_DIR"

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$CURRENT_BRANCH" != "$BRANCH" ]]; then
  echo "KernelSU is on '$CURRENT_BRANCH', expected '$BRANCH'." >&2
  echo "Fix with: git -C KernelSU checkout $BRANCH" >&2
  exit 1
fi

# Resolve the upstream main tip (works with or without a matching remote).
if git remote | grep -qx "$UPSTREAM_REMOTE"; then
  git fetch "$UPSTREAM_REMOTE" main --quiet
  UPSTREAM="$UPSTREAM_REMOTE/main"
else
  echo "No '$UPSTREAM_REMOTE' remote found; fetching $UPSTREAM_URL directly..."
  git fetch "$UPSTREAM_URL" main --quiet
  UPSTREAM="FETCH_HEAD"
fi

BASE="$(git merge-base HEAD "$UPSTREAM")"
TIP="$(git rev-parse --short "$UPSTREAM")"
NEW_COUNT="$(git rev-list --count "$BASE..$UPSTREAM")"

if [[ "$NEW_COUNT" -eq 0 ]]; then
  echo "Already up to date with upstream main ($TIP). Nothing to do."
  exit 0
fi

echo "Upstream main advanced by $NEW_COUNT commit(s) ($(git rev-parse --short "$BASE")..$TIP):"
git log --oneline "$BASE..$UPSTREAM" | head -15

KERNEL_COUNT="$(git rev-list --count "$BASE..$UPSTREAM" -- kernel/)"
if [[ "$KERNEL_COUNT" -eq 0 ]]; then
  cat <<EOF

None of them touch kernel/ — this is a Manager/ksud-only update.
  -> No kernel rebuild needed.
  -> Install the newest Manager APK (releases or CI; the app's built-in
     update button can lag behind CI and offer a downgrade). ksud
     updates itself once the APK is installed.
EOF
  exit 0
fi

echo
echo "$KERNEL_COUNT commit(s) touch kernel/ — kernel-side sync required."
if [[ "$CHECK_ONLY" -eq 1 ]]; then
  echo "(--check: stopping before any modification)"
  exit 10
fi

echo "Rebasing $BRANCH onto $TIP..."
if ! git rebase "$UPSTREAM"; then
  echo "Rebase hit a conflict. Resolve it, run 'git rebase --continue', then" >&2
  echo "re-run this script." >&2
  exit 1
fi
NEW_FORK_SHA="$(git rev-parse --short HEAD)"

# The fork branch is always "upstream main + one commit", so every sync
# rewrites it: push with a lease instead of expecting a fast-forward.
if git remote | grep -qx "$FORK_REMOTE"; then
  git fetch "$FORK_REMOTE" --quiet
  git push --force-with-lease "$FORK_REMOTE" "$BRANCH"
else
  echo "No '$FORK_REMOTE' remote found; pushing to 'origin' instead."
  git push --force-with-lease origin "$BRANCH"
fi

cd "$ROOT_DIR"
git add KernelSU
git commit -m "build: sync KernelSU submodule with upstream ($TIP)"

echo "Building the kernel (incremental)..."
bash build_star.sh
echo "Packaging AnyKernel3 zip..."
bash anykernel3/build.sh

cat <<EOF

Done: fork pushed at $NEW_FORK_SHA, submodule bumped, kernel built, zip packaged.
Next (staged release protocol):
  1. Upload the zip as a GitHub PRE-RELEASE.
  2. Flash and verify on device.
  3. Only after verification passes, push this repo's commit and tag.
EOF
