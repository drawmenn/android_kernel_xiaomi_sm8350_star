"""Host-side preflight regression tests; no device or network is needed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "check_susfs_compat.py"
SPEC = importlib.util.spec_from_file_location("susfs_compat", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("include/linux/susfs_def.h", "#define CMD_SUSFS_TEST 0x55554\n")
        self.write("include/linux/susfs.h", "void susfs_test(void **arg);\n")
        self.write("fs/susfs.c", "void susfs_test(void **arg) { }\n")
        self.write("KernelSU/kernel/supercall/dispatch.c",
                   "case CMD_SUSFS_TEST: susfs_test(arg); break;\n")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_compatible(self):
        self.assertEqual(MODULE.check(self.root), [])

    def test_missing_command(self):
        self.write("include/linux/susfs_def.h", "")
        self.assertIn("missing command: CMD_SUSFS_TEST", MODULE.check(self.root))

    def test_missing_declaration(self):
        self.write("include/linux/susfs.h", "")
        self.assertIn("missing declaration: susfs_test", MODULE.check(self.root))

    def test_missing_implementation(self):
        self.write("fs/susfs.c", "void susfs_test(void **arg);\n")
        self.assertIn("missing implementation: susfs_test", MODULE.check(self.root))

    def test_comments_do_not_satisfy_interfaces(self):
        self.write("include/linux/susfs_def.h", "/*\n#define CMD_SUSFS_TEST 0x55554\n*/")
        self.assertIn("missing command: CMD_SUSFS_TEST", MODULE.check(self.root))

    def test_commented_calls_are_ignored(self):
        self.write("KernelSU/kernel/supercall/dispatch.c",
                   "// case CMD_SUSFS_NEW: susfs_new(arg);\n")
        self.assertEqual(MODULE.check(self.root), [])

    def test_inline_definition(self):
        self.write("include/linux/susfs.h", "")
        self.write("fs/susfs.c", "")
        self.write("include/linux/susfs_def.h",
                   "#define CMD_SUSFS_TEST 0x55554\n"
                   "static inline int susfs_test(void **arg) { return 0; }\n")
        self.assertEqual(MODULE.check(self.root), [])

    def test_real_tree(self):
        self.assertEqual(MODULE.check(SCRIPT.parents[1]), [])


if __name__ == "__main__":
    unittest.main()
