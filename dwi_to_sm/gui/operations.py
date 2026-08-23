"""Background scanning and filesystem operations for the GUI."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

from ..files import convert_file
from ..folders import AUTOCONVERT_MARKER, _simfiles
from .models import Progress, ScanResult, SongEntry


def iter_song_entries(root: Path) -> Iterator[SongEntry]:
    """Yield song folders below root, grouped by their first directory."""
    for current, _, _ in root.walk():
        dwi, sm = _simfiles(str(current))
        generated = list(current.glob("*.sm.converted"))
        marker = current / AUTOCONVERT_MARKER
        is_new_song = bool(dwi and not sm)
        is_autoconverted_song = bool(sm and marker.is_file())
        if not is_new_song and not is_autoconverted_song:
            continue
        relative = current.relative_to(root)
        pack = relative.parts[0] if len(relative.parts) > 1 else "(root)"
        yield SongEntry(current, pack, dwi, sm, generated, marker.is_file())


def scan_library(root: Path) -> ScanResult:
    return ScanResult(root, list(iter_song_entries(root)))


def operation_count(entries: list[SongEntry]) -> int:
    total = 0
    for entry in entries:
        if entry.action == "convert":
            total += len(entry.dwi_files)
        elif entry.action == "remove":
            total += len(entry.generated_files)
            if entry.autoconverted:
                total += len(entry.sm_files) + 1
    return total


def execute(entries: list[SongEntry]) -> Iterator[Progress]:
    """Yield progress after each conversion or removal operation."""
    operations = []
    for entry in entries:
        if entry.action == "convert":
            operations.extend(
                ("convert", entry, entry.folder / name) for name in entry.dwi_files
            )
        elif entry.action == "remove":
            targets = list(entry.generated_files)
            if entry.autoconverted:
                targets.extend(entry.folder / name for name in entry.sm_files)
                targets.append(entry.folder / AUTOCONVERT_MARKER)
            operations.extend(("remove", entry, path) for path in targets)

    total = len(operations)
    for completed, (operation, entry, path) in enumerate(operations, 1):
        if operation == "convert":
            convert_file(str(path), overwrite=False)
            if path.with_suffix(".sm").name not in entry.sm_files:
                entry.sm_files.append(path.with_suffix(".sm").name)
            message = f"Converted {path.name}"
        else:
            with contextlib.suppress(OSError):
                path.unlink()
            if path.name in entry.sm_files:
                entry.sm_files.remove(path.name)
            if path in entry.generated_files:
                entry.generated_files.remove(path)
            if path.name == AUTOCONVERT_MARKER:
                entry.autoconverted = False
            message = f"Removed {path.name}"
        yield Progress(completed, total, entry.folder, entry.progress, message)
