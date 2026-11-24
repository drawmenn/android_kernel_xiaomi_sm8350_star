#!/usr/bin/env python3
"""Verify a kernel build and collect a fixed-name rolling-release bundle."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(root, out, dest, kind):
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(root / "KernelSU"), *args], text=True).strip()

    release = (out / "include/config/kernel.release").read_text().strip()
    image_path = out / "arch/arm64/boot/Image.gz"
    image = gzip.decompress(image_path.read_bytes())
    if image[56:60] != b"ARMd":
        raise ValueError("not an ARM64 Image")
    count = int(git("rev-list", "--count", "HEAD"))
    version_code = 30700 + count
    version_name = git("describe", "--abbrev=0", "--tags") + "-" + git(
        "rev-parse", "--short=8", "HEAD")
    command = (out / "drivers/kernelsu/core/.init.o.cmd").read_text()
    if f"-DKSU_VERSION={version_code}" not in command:
        raise ValueError("KSU version code does not match the built object")
    if version_name not in command or version_name.encode() not in image:
        raise ValueError("KSU version name is absent from the built Image")
    config_path = out / ".config"
    embedded = subprocess.check_output([
        "bash", str(root / "scripts/extract-ikconfig"), str(image_path)])
    if embedded.strip() != config_path.read_bytes().strip():
        raise ValueError("embedded kernel configuration is stale")
    package = out / (release + ".zip")
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() or archive.read("Image.gz") != image_path.read_bytes():
            raise ValueError("AnyKernel3 package does not match the verified Image")
    if dest.exists() and any(dest.iterdir()):
        raise ValueError("bundle directory must be empty")
    dest.mkdir(parents=True, exist_ok=True)
    for source, name in [
        (package, "kernel.zip"), (image_path, "Image.gz"),
        (config_path, "kernel.config"), (out / "System.map", "System.map"),
        (out / "Module.symvers", "Module.symvers"),
    ]:
        shutil.copyfile(source, dest / name)
    counts = {}
    for pattern, name in [("*.dtb", "dtbs.tar.gz"), ("*.ko", "modules.tar.gz")]:
        files = sorted(out.rglob(pattern))
        counts[name] = len(files)
        if files:
            with tarfile.open(dest / name, "w:gz") as archive:
                for path in files:
                    archive.add(path, arcname=str(path.relative_to(out)), recursive=False)
    managers = sorted((root / "manager").glob("*arm64-v8a*.apk"))
    if len(managers) > 1:
        raise ValueError("ambiguous Manager APKs")
    if managers:
        with zipfile.ZipFile(managers[0]) as archive:
            if archive.testzip():
                raise ValueError("Manager APK integrity check failed")
        shutil.copyfile(managers[0], dest / "Manager-arm64-v8a.apk")
    pinned = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD:KernelSU"], text=True).strip()
    info = {
        "repository": os.environ["GITHUB_REPOSITORY"],
        "source_sha": os.environ["GITHUB_SHA"],
        "run_id": int(os.environ["GITHUB_RUN_ID"]),
        "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
        "workflow": os.environ.get("GITHUB_WORKFLOW", ""),
        "event": os.environ.get("GITHUB_EVENT_NAME", ""),
        "kind": kind, "device_verified": False,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "kernel_release": release, "ksu_pinned_sha": pinned,
        "ksu_built_sha": git("rev-parse", "HEAD"),
        "ksu_tree_sha": git("rev-parse", "HEAD^{tree}"),
        "ksu_version_code": version_code, "ksu_version_name": version_name,
        "manager_available": bool(managers),
        "manager_original_filename": managers[0].name if managers else None,
        "output_counts": counts,
    }
    info["assets"] = {
        path.name: {"sha256": digest(path), "size": path.stat().st_size}
        for path in sorted(dest.iterdir()) if path.is_file()
    }
    (dest / "build-info.json").write_text(json.dumps(info, indent=2) + "\n")
    (dest / "SHA256SUMS").write_text("".join(
        f"{digest(path)}  {path.name}\n" for path in sorted(dest.iterdir())
        if path.is_file() and path.name != "SHA256SUMS"))
    print(json.dumps(info, indent=2))
    return info


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=root / "out-star-5.4.274-qgki-g4dfe63e0666f")
    parser.add_argument("--dist", type=Path, default=root / "dist")
    parser.add_argument("--kind", choices=["pinned", "upstream-sync"], required=True)
    args = parser.parse_args()
    collect(root, args.out.resolve(), args.dist.resolve(), args.kind)


if __name__ == "__main__":
    main()
