"""Compile actual port definitions to check ABI, input validation and UID scope."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def extract_function(text, signature):
    start = text.index(signature)
    brace = text.index("{", start)
    depth, end = 1, brace + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


@unittest.skipUnless(shutil.which("clang"), "clang is required")
class PortTests(unittest.TestCase):
    def compile(self, text, target=None, run=False):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = path / "test.c"
            output = path / "test"
            source.write_text(text)
            args = ["clang", "-Werror", "-Wall", "-Wextra", "-I", str(path),
                    str(source), "-o", str(output)]
            if target:
                args += ["--target=" + target, "-ffreestanding", "-nostdinc", "-c"]
            subprocess.run(args, check=True, capture_output=True, text=True)
            if run:
                subprocess.run([str(output)], check=True)

    def abi_source(self):
        header = (ROOT / "include/linux/susfs.h").read_text()
        definitions = (ROOT / "include/linux/susfs_def.h").read_text()
        names = ("st_susfs_sus_path_uid_filter", "st_susfs_priority_uid_filter")
        structures = "\n".join(re.search(
            rf"struct {name}\s*\{{.*?\}};", header, re.S).group() for name in names)
        constants = "\n".join(re.findall(
            r"^#define (?:SUSFS_APP_STR_BUF_SIZE|CMD_SUSFS_SET_SUS_PATH_UID_FILTER|"
            r"CMD_SUSFS_SET_PRIORITY_UID_FILTER)\b[^\n]*", definitions, re.M))
        asserts = "\n".join(
            f'_Static_assert(__builtin_offsetof(struct {name}, err) == 65536, "err ABI");\n'
            f'_Static_assert(sizeof(struct {name}) == 65540, "struct ABI");'
            for name in names)
        return constants + "\n" + structures + "\n" + asserts + """
_Static_assert(CMD_SUSFS_SET_SUS_PATH_UID_FILTER == 0x55554, "path command ABI");
_Static_assert(CMD_SUSFS_SET_PRIORITY_UID_FILTER == 0x60030, "prio command ABI");
int main(void) { return 0; }
"""

    def test_arm64_uid_filter_abi(self):
        self.compile(self.abi_source(), target="aarch64-linux-gnu")

    def test_host_uid_filter_abi(self):
        self.compile(self.abi_source(), run=True)

    def test_package_name_validation(self):
        text = (ROOT / "fs/susfs.c").read_text()
        validators = "\n".join(extract_function(text, "static bool " + name + "(")
                               for name in ("susfs_is_valid_app_name",
                                            "susfs_is_valid_sus_path_app_name"))
        self.compile("""
#include <stdbool.h>
#include <string.h>
#include <assert.h>
""" + validators + """
int main(void) {
    const char *bad[] = {"", ".", "..", "../com.app", "com/app", "com.app;id", "应用"};
    const char *good[] = {"com.example.app", "org.example_app", "app123"};
    unsigned i;
    char boundary[257];
    for (i = 0; i < sizeof(bad) / sizeof(*bad); i++) {
        assert(!susfs_is_valid_app_name(bad[i]));
        assert(!susfs_is_valid_sus_path_app_name(bad[i]));
    }
    for (i = 0; i < sizeof(good) / sizeof(*good); i++) {
        assert(susfs_is_valid_app_name(good[i]));
        assert(susfs_is_valid_sus_path_app_name(good[i]));
    }
    memset(boundary, 'a', 255); boundary[255] = 0;
    assert(susfs_is_valid_app_name(boundary));
    assert(susfs_is_valid_sus_path_app_name(boundary));
    boundary[255] = 'a'; boundary[256] = 0;
    assert(!susfs_is_valid_app_name(boundary));
    assert(!susfs_is_valid_sus_path_app_name(boundary));
    return 0;
}
""", run=True)

    def test_54_fsnotify_final_release_callback(self):
        text = (ROOT / "fs/susfs.c").read_text()
        operations = re.search(r"static const struct fsnotify_ops fsnotify_ops"
                               r"\s*=\s*\{.*?\};", text, re.S).group()
        self.assertRegex(operations, r"\.free_mark\s*=\s*susfs_free_mark")
        release = extract_function(text, "static void susfs_free_mark(")
        self.assertIn("kfree(mark);", release)

    def test_sdcard_watch_drops_creator_reference(self):
        text = (ROOT / "fs/susfs.c").read_text()
        cleanup = extract_function(text, "static void susfs_sdcard_cleanup_fn(")
        self.assertRegex(cleanup, r"xchg\(&g_watch\.mark,\s*NULL\)")
        self.assertIn("fsnotify_put_mark(mark);", cleanup)

    def test_priority_scope_preserves_system_self_and_secondary_users(self):
        header = (ROOT / "include/linux/uid_prio_filter.h").read_text()
        header = re.sub(r"^#include[^\n]*", "", header, flags=re.M)
        self.compile("""
#include <stdbool.h>
#include <assert.h>
#undef __always_inline
#define __always_inline inline
typedef unsigned int uid_t;
typedef struct { uid_t val; } kuid_t;
static uid_t caller_uid;
static unsigned bitmap_calls;
static inline bool uid_valid(kuid_t uid) { return uid.val != ~0U; }
static inline uid_t __kuid_val(kuid_t uid) { return uid.val; }
static inline kuid_t current_uid(void) { return (kuid_t){caller_uid}; }
#define CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER 1
bool susfs_is_priority_uid_filtered(uid_t uid) {
    bitmap_calls++;
    return uid % 100000 == 10001;
}
""" + header + """
int main(void) {
    caller_uid = 1000;
    assert(!uid_prio_filter_hide((kuid_t){10001}));
    caller_uid = 10000;
    assert(!uid_prio_filter_hide((kuid_t){10000}));
    assert(!uid_prio_filter_hide((kuid_t){1000}));
    assert(!uid_prio_filter_hide((kuid_t){~0U}));
    assert(bitmap_calls == 0);
    assert(uid_prio_filter_hide((kuid_t){10001}));
    assert(uid_prio_filter_hide((kuid_t){10002}));
    caller_uid = 110000;
    assert(!uid_prio_filter_hide((kuid_t){10000}));
    assert(!uid_prio_filter_hide((kuid_t){101000}));
    assert(uid_prio_filter_hide((kuid_t){110001}));
    return 0;
}
""", run=True)


if __name__ == "__main__":
    unittest.main()
