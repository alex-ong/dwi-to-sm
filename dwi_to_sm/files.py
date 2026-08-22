"""File-level conversion helpers."""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from .sm import dwi_to_sm

__all__ = ["read_text", "convert_file", "convert_tree"]

_ENCODINGS = ("utf-8-sig", "cp932", "cp1252", "latin-1")


def read_text(path: str) -> str:
    """Read a simfile, trying the encodings DWI files are found in."""
    with open(path, "rb") as handle:
        raw = handle.read()
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def convert_file(dwi_path: str, sm_path: Optional[str] = None,
                 overwrite: bool = False, encoding: str = "utf-8") -> Optional[str]:
    """Convert one .dwi file.

    Returns the path of the written .sm file, or None if it already existed and
    ``overwrite`` is False.
    """
    dwi_path = os.path.abspath(dwi_path)
    if sm_path is None:
        sm_path = os.path.splitext(dwi_path)[0] + ".sm"
    if not overwrite and os.path.exists(sm_path):
        return None

    base_name = os.path.splitext(os.path.basename(dwi_path))[0]
    sm_text = dwi_to_sm(read_text(dwi_path), os.path.dirname(dwi_path), base_name)

    os.makedirs(os.path.dirname(os.path.abspath(sm_path)) or ".", exist_ok=True)
    with open(sm_path, "w", encoding=encoding, newline="\n") as handle:
        handle.write(sm_text)
    return sm_path


def convert_tree(root: str, out_root: Optional[str] = None,
                 overwrite: bool = False) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """Convert every .dwi under ``root``.

    Returns ``(dwi_path, sm_path, error)`` per file. ``sm_path`` is None when the
    target already existed and was left alone; ``error`` is None on success.
    """
    results: List[Tuple[str, Optional[str], Optional[str]]] = []
    for directory, _, files in os.walk(root):
        for name in files:
            if not name.lower().endswith(".dwi"):
                continue
            src = os.path.join(directory, name)
            dst = None
            if out_root is not None:
                rel = os.path.relpath(directory, root)
                dst = os.path.join(out_root, rel, os.path.splitext(name)[0] + ".sm")
            try:
                results.append((src, convert_file(src, dst, overwrite=overwrite), None))
            except Exception as exc:  # keep going through a bulk run
                results.append((src, None, str(exc)))
    return results
