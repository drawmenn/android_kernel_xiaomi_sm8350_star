#!/usr/bin/env python3
"""Replace only the managed latest-build prerelease, staging before promotion."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

TAG = "latest-build"
TITLE = "最新自动构建 / Latest automated build (UNVERIFIED)"
MARKER = "rolling-kernel-build:"
ALLOWED = {
    "kernel.zip", "Image.gz", "kernel.config", "System.map", "Module.symvers",
    "dtbs.tar.gz", "modules.tar.gz", "Manager-arm64-v8a.apk",
    "build-info.json", "SHA256SUMS",
}
REQUIRED = {"kernel.zip", "Image.gz", "kernel.config", "System.map",
            "Module.symvers", "build-info.json", "SHA256SUMS"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_bundle(directory, environment):
    files = {path.name: path for path in directory.iterdir()}
    if not REQUIRED <= files.keys() or not files.keys() <= ALLOWED:
        raise ValueError("missing or unexpected bundle assets")
    if any(not p.is_file() or p.is_symlink() for p in files.values()):
        raise ValueError("bundle assets must be regular files")
    checks = {}
    for line in files["SHA256SUMS"].read_text().splitlines():
        value, name = line.split("  ", 1)
        if not re.fullmatch(r"[0-9a-f]{64}", value) or name in checks:
            raise ValueError("invalid checksum manifest")
        checks[name] = value
    if checks.keys() != files.keys() - {"SHA256SUMS"}:
        raise ValueError("checksum manifest does not cover the bundle")
    for name, value in checks.items():
        if sha256(files[name]) != value:
            raise ValueError("checksum mismatch: " + name)
    info = json.loads(files["build-info.json"].read_text())
    if not re.fullmatch(r"[0-9a-f]{40}", info["source_sha"]):
        raise ValueError("invalid source commit")
    for field, key in [
        ("repository", "GITHUB_REPOSITORY"), ("source_sha", "GITHUB_SHA"),
        ("run_id", "GITHUB_RUN_ID"), ("run_attempt", "GITHUB_RUN_ATTEMPT"),
    ]:
        if key in environment and str(info[field]) != environment[key]:
            raise ValueError("bundle belongs to a different run: " + field)
    if int(info["run_id"]) < 1 or int(info["run_attempt"]) < 1:
        raise ValueError("invalid build run")
    return files, info


def read_marker(body):
    match = re.search(r"<!--\s*" + MARKER + r"\s*(\{.*?\})\s*-->", body, re.S)
    if not match:
        raise ValueError("refusing to modify an unmanaged Release")
    return json.loads(match.group(1))


def release_notes(info):
    metadata = {"run_id": info["run_id"], "run_attempt": info["run_attempt"]}
    url = f"https://github.com/{info['repository']}/actions/runs/{info['run_id']}"
    return f"""<!-- {MARKER} {json.dumps(metadata, separators=(',', ':'))} -->
# 最新成功自动构建（未经逐版实机验证）

此预发布页自动替换上一批成功构建产物，不覆盖任何固定正式 Release。
构建或上传校验失败时不清空上一批可用产物。普通构建及 KSU 自动同步构建共用此页。

- 构建：[{info['workflow']}]({url})，attempt {info['run_attempt']}
- 类型：`{info['kind']}`
- 内核源码：`{info['source_sha']}`
- KernelSU 实际源码：`{info['ksu_built_sha']}`（tree `{info['ksu_tree_sha']}`）
- 内核版本：`{info['kernel_release']}`
- 内置 KSU：`{info['ksu_version_name']}` / `{info['ksu_version_code']}`
- 配套 Manager：{'包含 ARM64 APK' if info['manager_available'] else '本次未获取，未保留旧 APK'}

`kernel.zip` 是 AnyKernel3 包；`SHA256SUMS` 与 `build-info.json` 给出校验值和来源。
后续成功构建会替换文件，因此请核对当前 build-info。日常使用优先选择经过实机验证的固定正式版本。
"""


class GitHub:
    def __init__(self, repo):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("invalid repository")
        self.repo = repo

    def api(self, path, method="GET", body=None, missing=False, binary=False):
        args = ["gh", "api", f"repos/{self.repo}/{path}", "--method", method]
        if body is not None:
            args += ["--input", "-"]
        if binary:
            args += ["-H", "Accept: application/octet-stream"]
        result = subprocess.run(args, input=json.dumps(body).encode() if body is not None else None,
                                capture_output=True)
        if result.returncode:
            if missing and b"HTTP 404" in result.stderr:
                return None
            raise RuntimeError(result.stderr.decode(errors="replace").strip())
        return result.stdout if binary else json.loads(result.stdout or b"null")

    def get_release(self):
        return self.api(f"releases/tags/{TAG}", missing=True)

    def create_release(self, source_sha):
        return self.api("releases", "POST", {
            "tag_name": TAG, "target_commitish": source_sha,
            "name": TITLE, "body": f"<!-- {MARKER} {{\"run_id\":0,\"run_attempt\":0}} -->\n等待首次成功构建上传。",
            "prerelease": True, "draft": False, "make_latest": "false",
        })

    def assets(self, release_id):
        # The managed bundle has at most ten assets; allow room for a failed
        # staging/promotion generation as well.
        return self.api(f"releases/{release_id}/assets?per_page=100")

    def upload(self, paths):
        subprocess.run(["gh", "release", "upload", TAG, "--repo", self.repo,
                        "--clobber", *map(str, paths)], check=True)

    def rename(self, asset_id, name):
        return self.api(f"releases/assets/{asset_id}", "PATCH", {"name": name})

    def delete(self, asset_id):
        self.api(f"releases/assets/{asset_id}", "DELETE")

    def download(self, asset_id):
        return self.api(f"releases/assets/{asset_id}", binary=True)

    def tag_sha(self):
        ref = self.api(f"git/ref/tags/{TAG}", missing=True)
        return ref["object"]["sha"] if ref else None

    def set_tag(self, source_sha):
        if self.tag_sha() is None:
            self.api("git/refs", "POST", {"ref": f"refs/tags/{TAG}", "sha": source_sha})
        else:
            self.api(f"git/refs/tags/{TAG}", "PATCH", {"sha": source_sha, "force": True})

    def edit_release(self, release_id, body):
        self.api(f"releases/{release_id}", "PATCH", {
            "name": TITLE, "body": body, "prerelease": True,
            "draft": False, "make_latest": "false",
            "target_commitish": self.tag_sha(),
        })


def check_remote_asset(github, asset, path):
    if asset.get("state") != "uploaded" or asset["size"] != path.stat().st_size:
        raise ValueError("incomplete uploaded asset: " + path.name)
    expected = sha256(path)
    remote = asset.get("digest")
    if remote:
        if remote != "sha256:" + expected:
            raise ValueError("remote checksum mismatch: " + path.name)
    elif hashlib.sha256(github.download(asset["id"])).hexdigest() != expected:
        raise ValueError("downloaded checksum mismatch: " + path.name)


def publish(directory, github, environment):
    files, info = validate_bundle(directory, environment)
    release = github.get_release()
    if release:
        previous = read_marker(release.get("body") or "")
        if not release["prerelease"] or release["draft"]:
            raise ValueError("refusing to modify a fixed or draft Release")
        if (int(info["run_id"]), int(info["run_attempt"])) < (
                int(previous["run_id"]), int(previous["run_attempt"])):
            print("Skipping an older build; the rolling Release already has a newer run.")
            return "skipped"
    else:
        release = github.create_release(info["source_sha"])
    release_id = release["id"]
    old_body = release.get("body") or ""
    old_tag = github.tag_sha()
    suffix = f".incoming-{info['run_id']}-{info['run_attempt']}"
    old_assets = [asset for asset in github.assets(release_id) if asset["name"] in ALLOWED]
    staged = {}
    backups, promoted = [], []
    committed = False
    try:
        # No existing final asset is touched until every new asset is uploaded
        # and its remote digest (or round-trip download) has been checked.
        with tempfile.TemporaryDirectory(prefix="kernel-release-") as temp:
            paths = []
            for name, source in files.items():
                target = Path(temp) / (name + suffix)
                shutil.copyfile(source, target)
                paths.append(target)
            github.upload(paths)
        assets = {asset["name"]: asset for asset in github.assets(release_id)}
        for name, path in files.items():
            asset = assets[name + suffix]
            check_remote_asset(github, asset, path)
            staged[name] = asset
        for asset in old_assets:
            backup_name = f"{asset['name']}.previous-{info['run_id']}-{info['run_attempt']}-{asset['id']}"
            backups.append(asset)
            github.rename(asset["id"], backup_name)
        for name, asset in staged.items():
            promoted.append((name, asset))
            github.rename(asset["id"], name)
        github.set_tag(info["source_sha"])
        github.edit_release(release_id, release_notes(info))
        committed = True
        for asset in backups:
            github.delete(asset["id"])
        # Remove only generated staging/backup leftovers, never arbitrary assets
        # or assets in a different (fixed) Release.
        for asset in github.assets(release_id):
            if any(asset["name"].startswith(name + ".incoming-") or
                   asset["name"].startswith(name + ".previous-") for name in ALLOWED):
                github.delete(asset["id"])
        final = {asset["name"]: asset for asset in github.assets(release_id)}
        for name, path in files.items():
            check_remote_asset(github, final[name], path)
        if set(final) & ALLOWED != set(files):
            raise ValueError("obsolete managed assets remain")
    except Exception:
        if not committed:
            for name, asset in reversed(promoted):
                github.rename(asset["id"], name + suffix)
            for asset in reversed(backups):
                github.rename(asset["id"], asset["name"])
            if old_tag:
                github.set_tag(old_tag)
            github.edit_release(release_id, old_body)
            for asset in github.assets(release_id):
                if asset["name"].endswith(suffix):
                    github.delete(asset["id"])
        raise
    print(f"Replaced {len(files)} assets in {github.repo} / {TAG} with run {info['run_id']}.")
    return "published"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    publish(args.bundle, GitHub(os.environ["GITHUB_REPOSITORY"]), os.environ)


if __name__ == "__main__":
    main()
