"""Offline tests of bundle verification and rolling-Release transactions."""
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PUBLISH = load("publish_rolling_release")
COLLECT = load("collect_build_release")


class FakeGitHub:
    repo = "owner/kernel"

    def __init__(self):
        self.release = {
            "id": 1, "prerelease": True, "draft": False,
            "body": '<!-- rolling-kernel-build: {"run_id":10,"run_attempt":1} -->',
        }
        self.tag = "b" * 40
        self.data = {}
        self.next_id = 1
        self.events = []
        self.corrupt_upload = False
        self.fail_promotion_once = False
        self.fail_after_rename = False
        for name in ["kernel.zip", "Image.gz", "Manager-arm64-v8a.apk"]:
            self.add(name, b"old-" + name.encode())

    def add(self, name, content):
        number = self.next_id
        self.next_id += 1
        self.data[number] = {
            "id": number, "name": name, "content": content, "state": "uploaded",
            "size": len(content),
            "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
        }

    def get_release(self):
        return copy.deepcopy(self.release)

    def create_release(self, source_sha):
        self.events.append(("create",))
        self.tag = source_sha
        self.release = {
            "id": 1, "prerelease": True, "draft": False,
            "body": '<!-- rolling-kernel-build: {"run_id":0,"run_attempt":0} -->',
        }
        return copy.deepcopy(self.release)

    def assets(self, release_id):
        return copy.deepcopy(list(self.data.values()))

    def upload(self, paths):
        self.events.append(("upload",))
        for path in paths:
            self.add(path.name, path.read_bytes())
        if self.corrupt_upload:
            self.data[self.next_id - 1]["digest"] = "sha256:" + "0" * 64

    def rename(self, number, name):
        self.events.append(("rename", number, name))
        fail = self.fail_promotion_once and name == "Image.gz"
        if fail:
            self.fail_promotion_once = False
            if not self.fail_after_rename:
                raise RuntimeError("injected promotion failure")
        if any(a["name"] == name and a["id"] != number for a in self.data.values()):
            raise RuntimeError("asset name collision")
        self.data[number]["name"] = name
        if fail:
            raise RuntimeError("request succeeded but its response was lost")

    def delete(self, number):
        self.events.append(("delete", number))
        del self.data[number]

    def download(self, number):
        return self.data[number]["content"]

    def tag_sha(self):
        return self.tag

    def set_tag(self, sha):
        self.events.append(("tag", sha))
        self.tag = sha

    def edit_release(self, release_id, body):
        self.events.append(("body",))
        self.release["body"] = body

    def canonical(self):
        return {a["name"]: a["content"] for a in self.data.values()
                if a["name"] in PUBLISH.ALLOWED}


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.info = {
            "repository": "owner/kernel", "source_sha": "a" * 40,
            "run_id": 20, "run_attempt": 1, "workflow": "test",
            "kind": "pinned", "ksu_built_sha": "c" * 40, "ksu_tree_sha": "d" * 40,
            "kernel_release": "5.4.274", "ksu_version_name": "v4.2.0-test",
            "ksu_version_code": 35286, "manager_available": False,
        }
        for name in sorted(PUBLISH.REQUIRED - {"SHA256SUMS", "build-info.json"}):
            (self.directory / name).write_bytes(b"new-" + name.encode())
        self.refresh()
        self.github = FakeGitHub()
        self.original = self.github.canonical()
        self.original_ids = set(self.github.data)
        self.environment = {
            "GITHUB_REPOSITORY": "owner/kernel", "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "20", "GITHUB_RUN_ATTEMPT": "1",
        }

    def refresh(self):
        (self.directory / "build-info.json").write_text(json.dumps(self.info))
        (self.directory / "SHA256SUMS").write_text("".join(
            f"{PUBLISH.sha256(p)}  {p.name}\n" for p in sorted(self.directory.iterdir())
            if p.name != "SHA256SUMS"))

    def publish(self):
        return PUBLISH.publish(self.directory, self.github, self.environment)

    def test_replaces_entire_generation_and_removes_old_manager(self):
        self.assertEqual(self.publish(), "published")
        self.assertEqual(set(self.github.canonical()), set(PUBLISH.REQUIRED))
        self.assertFalse(self.original_ids & set(self.github.data))
        self.assertEqual(self.github.tag, "a" * 40)
        self.assertTrue(self.github.release["prerelease"])

    def test_second_build_replaces_asset_ids_and_content(self):
        self.publish()
        first_ids = set(self.github.data)
        self.info["run_id"] = 21
        self.environment["GITHUB_RUN_ID"] = "21"
        (self.directory / "kernel.zip").write_bytes(b"second kernel")
        self.refresh()
        self.publish()
        self.assertFalse(first_ids & set(self.github.data))
        self.assertEqual(self.github.canonical()["kernel.zip"], b"second kernel")
        self.assertEqual(PUBLISH.read_marker(self.github.release["body"])["run_id"], 21)

    def test_older_run_does_not_write_anything(self):
        self.github.release["body"] = (
            '<!-- rolling-kernel-build: {"run_id":30,"run_attempt":1} -->')
        self.assertEqual(self.publish(), "skipped")
        self.assertEqual(self.github.events, [])

    def test_rerun_attempt_can_replace_same_run(self):
        self.publish()
        self.info["run_attempt"] = 2
        self.environment["GITHUB_RUN_ATTEMPT"] = "2"
        self.refresh()
        self.assertEqual(self.publish(), "published")

    def test_local_corruption_never_writes_remote(self):
        (self.directory / "kernel.zip").write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.github.events, [])

    def test_missing_asset_never_writes_remote(self):
        (self.directory / "Image.gz").unlink()
        self.refresh()
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.github.events, [])

    def test_wrong_run_never_writes_remote(self):
        self.environment["GITHUB_RUN_ID"] = "999"
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.github.events, [])

    def test_unmanaged_release_is_protected(self):
        self.github.release["body"] = "Hand-maintained release"
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.github.events, [])

    def test_fixed_release_is_protected_even_with_marker(self):
        self.github.release["prerelease"] = False
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.github.events, [])

    def test_bad_uploaded_digest_preserves_previous_generation(self):
        self.github.corrupt_upload = True
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(self.github.canonical(), self.original)
        self.assertTrue(self.original_ids <= set(self.github.data))

    def test_promotion_failure_rolls_back_names_tag_and_body(self):
        old_body = self.github.release["body"]
        self.github.fail_promotion_once = True
        with self.assertRaises(RuntimeError):
            self.publish()
        self.assertEqual(self.github.canonical(), self.original)
        self.assertEqual(self.github.tag, "b" * 40)
        self.assertEqual(self.github.release["body"], old_body)
        self.assertEqual(set(self.github.data), self.original_ids)

    def test_lost_response_after_rename_also_rolls_back(self):
        self.github.fail_promotion_once = True
        self.github.fail_after_rename = True
        with self.assertRaises(RuntimeError):
            self.publish()
        self.assertEqual(self.github.canonical(), self.original)

    def test_remote_without_digest_uses_download_verification(self):
        original_assets = self.github.assets
        self.github.assets = lambda release_id: [
            {**a, "digest": None} for a in original_assets(release_id)]
        self.assertEqual(self.publish(), "published")

    def test_first_build_creates_only_rolling_prerelease(self):
        self.github.release = None
        self.github.data = {}
        self.github.tag = None
        self.assertEqual(self.publish(), "published")
        self.assertTrue(self.github.release["prerelease"])
        self.assertEqual(set(self.github.canonical()), PUBLISH.REQUIRED)


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "out"
        self.dest = self.root / "dist"
        self.config = b"CONFIG_KSU=y\n"
        self.version = "v4.2.0-aaaaaaaa"
        image = bytearray(64)
        image[56:60] = b"ARMd"
        image.extend(self.version.encode())
        self.image = gzip.compress(image)
        for name, contents in {
            "include/config/kernel.release": b"5.4.274",
            "arch/arm64/boot/Image.gz": self.image,
            "drivers/kernelsu/core/.init.o.cmd": b"-DKSU_VERSION=30710 " + self.version.encode(),
            ".config": self.config, "System.map": b"symbols", "Module.symvers": b"versions",
        }.items():
            path = self.out / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        with zipfile.ZipFile(self.out / "5.4.274.zip", "w") as archive:
            archive.writestr("Image.gz", self.image)
        self.environment = {
            "GITHUB_REPOSITORY": "owner/kernel", "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "20", "GITHUB_RUN_ATTEMPT": "1",
        }

    def command(self, args, **kwargs):
        if args[0] == "bash":
            return self.config
        if "rev-list" in args:
            return "10\n"
        if "describe" in args:
            return "v4.2.0\n"
        if "--short=8" in args:
            return "aaaaaaaa\n"
        if args[-1] == "HEAD^{tree}":
            return "d" * 40
        return "a" * 40

    def collect(self):
        with patch.dict(os.environ, self.environment), patch.object(
                COLLECT.subprocess, "check_output", side_effect=self.command):
            return COLLECT.collect(self.root, self.out, self.dest, "pinned")

    def test_verified_bundle_is_accepted_by_publisher(self):
        self.collect()
        files, info = PUBLISH.validate_bundle(self.dest, self.environment)
        self.assertTrue(PUBLISH.REQUIRED <= files.keys())
        self.assertEqual(info["ksu_version_code"], 30710)

    def test_wrong_image_architecture_fails_before_collection(self):
        (self.out / "arch/arm64/boot/Image.gz").write_bytes(gzip.compress(b"not arm64"))
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse(self.dest.exists())

    def test_nonempty_destination_is_not_deleted(self):
        self.dest.mkdir()
        (self.dest / "keep").write_bytes(b"keep")
        with self.assertRaises(ValueError):
            self.collect()
        self.assertEqual((self.dest / "keep").read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
