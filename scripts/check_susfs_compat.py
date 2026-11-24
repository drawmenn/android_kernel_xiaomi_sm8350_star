#!/usr/bin/env python3
"""Fail early when KernelSU calls interfaces absent from this SuSFS port."""
import argparse
from pathlib import Path
import re
import sys


def source(path):
    text = path.read_text()
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


def check(root):
    definitions = source(root / "include/linux/susfs_def.h")
    header = source(root / "include/linux/susfs.h")
    implementation = source(root / "fs/susfs.c")
    dispatch = source(root / "KernelSU/kernel/supercall/dispatch.c")
    defined = set(re.findall(r"^\s*#\s*define\s+(CMD_SUSFS_\w+)", definitions, re.M))
    used = set(re.findall(r"\bCMD_SUSFS_\w+\b", dispatch))
    calls = set(re.findall(r"\b(susfs_\w+)\s*\(", dispatch))
    declared = set(re.findall(r"\b(susfs_\w+)\s*\(", header + definitions))
    implemented = set(re.findall(r"\b(susfs_\w+)\s*\([^;{}]*\)\s*\{",
                                 implementation + header + definitions))
    problems = [f"missing command: {name}" for name in sorted(used - defined)]
    problems += [f"missing declaration: {name}" for name in sorted(calls - declared)]
    problems += [f"missing implementation: {name}" for name in sorted(calls - implemented)]
    return problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        problems = check(args.root)
    except (OSError, UnicodeError) as error:
        problems = [str(error)]
    if problems:
        print("KernelSU/SuSFS incompatibility:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2
    print("KernelSU/SuSFS command, declaration and implementation preflight passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
