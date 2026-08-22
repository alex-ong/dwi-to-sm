"""Song-folder level operations: autoconversion and diff testing."""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from .files import convert_file

__all__ = [
    "AUTOCONVERT_MARKER",
    "AUTOCONVERT_TEXT",
    "scan_folder",
    "find_convertible_folders",
    "find_testable_folders",
    "is_autoconverted",
    "autoconvert_folder",
    "autoconvert_tree",
    "test_folder",
    "test_tree",
    "clear_autoconversions",
]

AUTOCONVERT_MARKER = "autoconvert.txt"
AUTOCONVERT_TEXT = "was autoconverted by dwi-to-sm\n"

FolderResult = Tuple[str, List[str], Optional[str]]


def _simfiles(folder: str) -> Tuple[List[str], List[str]]:
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return [], []
    dwi = [e for e in entries if e.lower().endswith(".dwi")]
    sm = [e for e in entries if e.lower().endswith(".sm")]
    return dwi, sm


def scan_folder(folder: str) -> Optional[str]:
    """Return ``folder`` if it holds .dwi files and no .sm, else None."""
    dwi, sm = _simfiles(folder)
    return folder if dwi and not sm else None


def find_convertible_folders(root: str) -> List[str]:
    """Every folder under ``root`` that has .dwi files but no .sm yet."""
    return [d for d, _, _ in os.walk(root) if scan_folder(d)]


def find_testable_folders(root: str) -> List[str]:
    """Folders under ``root`` with a hand-made .sm to diff a fresh conversion against.

    Autoconverted folders are excluded: diffing our output against our own
    output proves nothing.
    """
    return [d for d, _, _ in os.walk(root)
            if all(_simfiles(d)) and not is_autoconverted(d)]


def is_autoconverted(folder: str) -> bool:
    return os.path.isfile(os.path.join(folder, AUTOCONVERT_MARKER))


def autoconvert_folder(folder: str, overwrite: bool = False) -> List[str]:
    """Convert a .dwi-only folder in place and leave the autoconvert marker.

    Returns the written .sm paths; empty if the folder already has an .sm.
    """
    if scan_folder(folder) is None:
        return []
    dwi, _ = _simfiles(folder)
    written = [path for path in
               (convert_file(os.path.join(folder, name), overwrite=overwrite)
                for name in dwi)
               if path is not None]
    if written:
        with open(os.path.join(folder, AUTOCONVERT_MARKER), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write(AUTOCONVERT_TEXT)
    return written


def autoconvert_tree(root: str, overwrite: bool = False) -> List[FolderResult]:
    """Autoconvert every .dwi-only folder under ``root``.

    Returns ``(folder, sm_paths, error)`` per folder; ``error`` is None on success.
    """
    results: List[FolderResult] = []
    for folder in find_convertible_folders(root):
        try:
            results.append((folder, autoconvert_folder(folder, overwrite), None))
        except Exception as exc:
            results.append((folder, [], str(exc)))
    return results


def test_folder(folder: str) -> List[str]:
    """Convert a folder that already has an .sm, writing ``<name>.sm.converted``.

    The real .sm is never touched, so the two can be diffed. Folders we
    autoconverted ourselves are skipped.
    """
    dwi, sm = _simfiles(folder)
    if not (dwi and sm) or is_autoconverted(folder):
        return []
    written = []
    for name in dwi:
        src = os.path.join(folder, name)
        path = convert_file(src, os.path.splitext(src)[0] + ".sm.converted",
                            overwrite=True)
        if path is not None:
            written.append(path)
    return written


def test_tree(root: str) -> List[FolderResult]:
    """Write ``<name>.sm.converted`` beside every hand-made .sm under ``root``."""
    results: List[FolderResult] = []
    for folder in find_testable_folders(root):
        try:
            results.append((folder, test_folder(folder), None))
        except Exception as exc:
            results.append((folder, [], str(exc)))
    return results


# These are simfile-diff helpers, not pytest cases.
test_folder.__test__ = False
test_tree.__test__ = False


def clear_autoconversions(root: str, dry_run: bool = True) -> List[str]:
    """List (or with ``dry_run=False`` delete) every autoconverted .sm and marker.

    Only touches folders carrying the autoconvert marker, so hand-made .sm
    files are never at risk.
    """
    removed: List[str] = []
    for folder, _, _ in os.walk(root):
        if not is_autoconverted(folder):
            continue
        _, sm = _simfiles(folder)
        targets = [os.path.join(folder, n) for n in sm]
        targets.append(os.path.join(folder, AUTOCONVERT_MARKER))
        for path in targets:
            removed.append(path)
            if not dry_run:
                try:
                    os.remove(path)
                except OSError:
                    pass
    return removed
