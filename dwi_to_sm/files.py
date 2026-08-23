"""File-level conversion helpers."""

from __future__ import annotations

from pathlib import Path

from .sm import dwi_to_sm

__all__ = ["convert_file", "convert_tree", "read_text"]

_ENCODINGS = ("utf-8-sig", "cp932", "cp1252", "latin-1")


def read_text(path: str) -> str:
    """Read a simfile, trying the encodings DWI files are found in."""
    with Path(path).open("rb") as handle:
        raw = handle.read()
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def convert_file(
    dwi_path: str, sm_path: str | None = None, overwrite: bool = False, encoding: str = "utf-8"
) -> str | None:
    """Convert one .dwi file.

    Returns the path of the written .sm file, or None if it already existed and
    ``overwrite`` is False.
    """
    dwi_path = Path(dwi_path).absolute()
    if sm_path is None:
        sm_path = str(dwi_path.with_suffix(".sm"))
    if not overwrite and Path(sm_path).exists():
        return None

    base_name = dwi_path.stem
    sm_text = dwi_to_sm(read_text(dwi_path), str(dwi_path.parent), base_name)

    Path(sm_path).absolute().parent.mkdir(parents=True, exist_ok=True)
    with Path(sm_path).open("w", encoding=encoding, newline="\n") as handle:
        handle.write(sm_text)
    return sm_path


def convert_tree(
    root: str, out_root: str | None = None, overwrite: bool = False, dry_run: bool = False
) -> list[tuple[str, str | None, str | None]]:
    """Convert every .dwi under ``root``.

    Returns ``(dwi_path, sm_path, error)`` per file. ``sm_path`` is None when the
    target already existed and was left alone; ``error`` is None on success.
    """
    results: list[tuple[str, str | None, str | None]] = []
    root_path = Path(root)
    for source_path in root_path.rglob("*"):
        if not source_path.is_file() or source_path.suffix.lower() != ".dwi":
            continue
        src = str(source_path)
        dst = None
        if out_root is not None:
            relative_directory = source_path.parent.relative_to(root_path)
            dst = str(Path(out_root, relative_directory, source_path.with_suffix(".sm").name))
        elif dry_run:
            dst = str(source_path.with_suffix(".sm"))
        try:
            if dry_run:
                target_path = Path(dst) if dst is not None else source_path.with_suffix(".sm")
                path = None if target_path.exists() and not overwrite else str(target_path)
            else:
                path = convert_file(src, dst, overwrite=overwrite)
            results.append((src, path, None))
        except Exception as exc:  # keep going through a bulk run
            results.append((src, None, str(exc)))
    return results
