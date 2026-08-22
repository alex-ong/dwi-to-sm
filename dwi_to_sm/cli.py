"""Command line entry point."""

from __future__ import annotations

import argparse
import os
from typing import Optional, Sequence

from .files import convert_file, convert_tree
from .folders import AUTOCONVERT_MARKER, autoconvert_tree, clear_autoconversions, test_tree

__all__ = ["main"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dwi-to-sm",
                                     description="Convert DWI simfiles to SM.")
    parser.add_argument("inputs", nargs="+", help=".dwi files or folders to convert")
    parser.add_argument("-o", "--out", help="output file (single input) or output root folder")
    parser.add_argument("-n", "--no-overwrite", action="store_true",
                        help="skip files whose .sm already exists")
    parser.add_argument("--auto", action="store_true",
                        help="only convert song folders that have .dwi and no .sm, "
                             f"marking each with {AUTOCONVERT_MARKER}")
    parser.add_argument("--test", action="store_true",
                        help="for folders that already have an .sm, write "
                             "<name>.sm.converted next to it for diffing")
    parser.add_argument("--clear-autoconversions", action="store_true",
                        help=f"delete .sm files in folders marked by {AUTOCONVERT_MARKER}")
    return parser


def _run_files(args: argparse.Namespace) -> int:
    failures = 0
    for target in args.inputs:
        if os.path.isdir(target):
            for src, dst, error in convert_tree(target, args.out, not args.no_overwrite):
                if error:
                    failures += 1
                    print(f"FAIL {src}: {error}")
                else:
                    print(f"OK   {src} -> {dst}")
        else:
            try:
                dst = convert_file(target, args.out, not args.no_overwrite)
                print(f"OK   {target} -> {dst}")
            except Exception as exc:
                failures += 1
                print(f"FAIL {target}: {exc}")
    return 1 if failures else 0


def _run_folders(args: argparse.Namespace) -> int:
    failures = 0
    for root in args.inputs:
        if args.clear_autoconversions:
            for path in clear_autoconversions(root, dry_run=False):
                print(f"DEL  {path}")
            continue
        runner = autoconvert_tree if args.auto else test_tree
        for folder, written, error in runner(root):
            if error:
                failures += 1
                print(f"FAIL {folder}: {error}")
            else:
                for path in written:
                    print(f"OK   {folder} -> {path}")
    return 1 if failures else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.auto or args.test or args.clear_autoconversions:
        return _run_folders(args)
    return _run_files(args)
