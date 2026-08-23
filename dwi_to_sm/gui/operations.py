"""Background scanning and filesystem operations for the GUI."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

from ..files import convert_file
from ..folders import (
    AUTOCONVERT_MARKER,
    AUTOCONVERT_TEXT,
    _simfiles,
    clear_autoconversions,
)
from .models import Action, Progress, ScanResult, SongEntry, TreeNode


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
        yield SongEntry(
            current, pack, dwi, sm, generated, marker.is_file(), already_converted=list(sm)
        )


def scan_library(root: Path) -> ScanResult:
    songs = list(iter_song_entries(root))
    all_songs = TreeNode(root.name or str(root), "all")
    packs: dict[str, TreeNode] = {}
    for entry in songs:
        pack = packs.get(entry.pack)
        if pack is None:
            pack = TreeNode(entry.pack, "pack")
            packs[entry.pack] = pack
            all_songs.children.append(pack)
        pack.children.append(TreeNode(entry.folder.name, "song", entry))
    return ScanResult(root, songs, all_songs)


def set_action(node: TreeNode, action: Action) -> None:
    """Set a node's action and propagate it through all descendants."""
    node.action = action
    if node.entry is not None:
        node.entry.action = action
    for child in node.children:
        set_action(child, action)


def operation_count(entries: list[SongEntry]) -> int:
    total = 0
    for entry in entries:
        if entry.action == "convert":
            pending = [
                name
                for name in entry.dwi_files
                if Path(name).with_suffix(".sm").name not in entry.sm_files
            ]
            total += len(pending)
            if pending and not entry.autoconverted:
                total += 1
        elif entry.action == "remove":
            total += len(entry.generated_files)
            if entry.autoconverted:
                total += 1
    return total


def execute(entries: list[SongEntry]) -> Iterator[Progress]:
    """Yield progress after each conversion or removal operation."""
    operations = []
    for entry in entries:
        if entry.action == "convert":
            pending = [
                name
                for name in entry.dwi_files
                if Path(name).with_suffix(".sm").name not in entry.sm_files
            ]
            operations.extend(
                ("convert", entry, entry.folder / name)
                for name in pending
            )
            if pending and not entry.autoconverted:
                operations.append(("mark", entry, entry.folder / AUTOCONVERT_MARKER))
        elif entry.action == "remove":
            targets = list(entry.generated_files)
            operations.extend(("remove", entry, path) for path in targets)
            if entry.autoconverted:
                operations.append(("clear", entry, entry.folder))

    total = len(operations)
    for completed, (operation, entry, path) in enumerate(operations, 1):
        error = None
        try:
            if operation == "convert":
                convert_file(str(path), overwrite=False)
                if path.with_suffix(".sm").name not in entry.sm_files:
                    entry.sm_files.append(path.with_suffix(".sm").name)
                message = f"Converted {path.name}"
            elif operation == "mark":
                if entry.error is not None:
                    message = f"Skipped marking {entry.folder.name} (conversion failed)"
                else:
                    path.write_text(AUTOCONVERT_TEXT, encoding="utf-8", newline="\n")
                    entry.autoconverted = True
                    message = f"Marked {entry.folder.name} as autoconverted"
            elif operation == "clear":
                clear_autoconversions(str(path), dry_run=False)
                entry.sm_files.clear()
                entry.generated_files.clear()
                entry.autoconverted = False
                entry.already_converted.clear()
                entry.failed_files.clear()
                message = f"Cleared conversion for {entry.folder.name}"
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
        except Exception as exc:  # one bad song must not abort the whole run
            error = str(exc)
            entry.error = error
            if operation == "convert":
                entry.failed_files.append(path.name)
            message = f"FAILED {path.name}: {error}"
        yield Progress(completed, total, entry.folder, entry.progress, message, error)
