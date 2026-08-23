"""Command line entry point.

Existing .sm files are never overwritten unless --force is passed.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .files import convert_file, convert_tree
from .folders import AUTOCONVERT_MARKER, autoconvert_tree, clear_autoconversions, test_tree

__all__ = ["main"]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dwi-to-sm",
        description="Convert DWI simfiles to SM. Existing .sm files are left alone.",
    )
    parser.add_argument("inputs", nargs="+", help=".dwi files or song folders")
    parser.add_argument("-o", "--out", help="output file (single .dwi) or output root folder")
    parser.add_argument(
        "-f", "--force", action="store_true", help="overwrite existing .sm files (off by default)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="write <name>.sm.converted beside each hand-made .sm "
        "instead of converting, so the two can be diffed",
    )
    parser.add_argument(
        "--clear-autoconversions",
        action="store_true",
        help=f"delete .sm files in folders marked by {AUTOCONVERT_MARKER}",
    )
    return parser


def _report(source: str, path: str | None, error: str | None) -> bool:
    """Print one result line; returns True if it was a failure."""
    if error:
        print(f"FAIL {source}: {error}")
        return True
    if path is None:
        print(f"SKIP {source}: .sm already exists")
    else:
        print(f"OK   {source} -> {path}")
    return False


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    failures = 0

    for target in args.inputs:
        if args.clear_autoconversions:
            for path in clear_autoconversions(target, dry_run=False):
                print(f"DEL  {path}")
        elif args.test:
            for folder, written, error in test_tree(target):
                if error:
                    failures += _report(folder, None, error)
                for path in written:
                    failures += _report(folder, path, None)
        elif not Path(target).is_dir():
            try:
                failures += _report(
                    target, convert_file(target, args.out, overwrite=args.force), None
                )
            except Exception as exc:
                failures += _report(target, None, str(exc))
        elif args.out or args.force:
            # An explicit destination (or --force) means whole-tree conversion.
            for src, path, error in convert_tree(target, args.out, overwrite=args.force):
                failures += _report(src, path, error)
        else:
            # Default: only touch song folders that have a .dwi and no .sm at all.
            for folder, written, error in autoconvert_tree(target):
                if error:
                    failures += _report(folder, None, error)
                for path in written:
                    failures += _report(folder, path, None)

    return 1 if failures else 0
