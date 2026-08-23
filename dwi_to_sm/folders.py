"""Song-folder level operations: autoconversion and diff testing."""

from __future__ import annotations

import contextlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from .files import convert_file

__all__ = [
    "AUTOCONVERT_MARKER",
    "AUTOCONVERT_TEXT",
    "autoconvert_folder",
    "autoconvert_tree",
    "clear_autoconversions",
    "find_convertible_folders",
    "find_testable_folders",
    "is_autoconverted",
    "plan_test_tree",
    "run_planned_actions",
    "scan_folder",
    "test_folder",
    "test_tree",
]

AUTOCONVERT_MARKER = "autoconvert.txt"
AUTOCONVERT_TEXT = "was autoconverted by dwi-to-sm\n"

FolderResult = tuple[str, list[str], str | None]


@dataclass
class PlannedAction:
    """A proposed filesystem operation awaiting an explicit decision."""

    operation: str
    source: str
    destination: str
    accepted: bool | None = None


def _simfiles(folder: str) -> tuple[list[str], list[str]]:
    try:
        entries = sorted(path.name for path in Path(folder).iterdir())
    except OSError:
        return [], []
    dwi = [e for e in entries if e.lower().endswith(".dwi")]
    sm = [e for e in entries if e.lower().endswith(".sm")]
    return dwi, sm


def scan_folder(folder: str) -> str | None:
    """Return ``folder`` if it holds .dwi files and no .sm, else None."""
    dwi, sm = _simfiles(folder)
    return folder if dwi and not sm else None


def find_convertible_folders(root: str) -> list[str]:
    """Every folder under ``root`` that has .dwi files but no .sm yet."""
    return [str(path) for path in _directories(root) if scan_folder(str(path))]


def find_testable_folders(root: str) -> list[str]:
    """Folders under ``root`` with a hand-made .sm to diff a fresh conversion against.

    Autoconverted folders are excluded: diffing our output against our own
    output proves nothing.
    """
    return [
        str(path)
        for path in _directories(root)
        if all(_simfiles(str(path))) and not is_autoconverted(str(path))
    ]


def plan_test_tree(root: str) -> list[PlannedAction]:
    """Return proposed test conversions without writing files."""
    plans = []
    for folder in find_testable_folders(root):
        dwi, _ = _simfiles(folder)
        plans.extend(
            PlannedAction(
                "test",
                str(Path(folder) / name),
                str((Path(folder) / name).with_suffix(".sm.converted")),
            )
            for name in dwi
        )
    return plans


def run_planned_actions(actions: Iterable[PlannedAction]) -> list[str]:
    """Run accepted actions; rejected or undecided actions are skipped."""
    written = []
    for action in actions:
        if action.operation != "test" or action.accepted is not True:
            continue
        path = convert_file(action.source, action.destination, overwrite=True)
        if path is not None:
            written.append(path)
    return written


def is_autoconverted(folder: str) -> bool:
    return (Path(folder) / AUTOCONVERT_MARKER).is_file()


def autoconvert_folder(folder: str, overwrite: bool = False, dry_run: bool = False) -> list[str]:
    """Convert a .dwi-only folder in place and leave the autoconvert marker.

    Returns the written .sm paths; empty if the folder already has an .sm.
    """
    if scan_folder(folder) is None:
        return []
    dwi, _ = _simfiles(folder)
    planned = [
        path
        for path in (
            str(Path(folder) / name).replace(Path(name).suffix, ".sm")
            if dry_run
            else convert_file(str(Path(folder) / name), overwrite=overwrite)
            for name in dwi
        )
        if path is not None
    ]
    if planned and not dry_run:
        with (Path(folder) / AUTOCONVERT_MARKER).open(
            "w", encoding="utf-8", newline="\n"
        ) as handle:
            handle.write(AUTOCONVERT_TEXT)
    return planned


def autoconvert_tree(
    root: str, overwrite: bool = False, dry_run: bool = False
) -> list[FolderResult]:
    """Autoconvert every .dwi-only folder under ``root``.

    Returns ``(folder, sm_paths, error)`` per folder; ``error`` is None on success.
    """
    results: list[FolderResult] = []
    for folder in find_convertible_folders(root):
        try:
            results.append((folder, autoconvert_folder(folder, overwrite, dry_run), None))
        except Exception as exc:
            results.append((folder, [], str(exc)))
    return results


def test_folder(folder: str, dry_run: bool = False) -> list[str]:  # noqa: PT028
    """Convert a folder that already has an .sm, writing ``<name>.sm.converted``.

    The real .sm is never touched, so the two can be diffed. Folders we
    autoconverted ourselves are skipped.
    """
    dwi, sm = _simfiles(folder)
    if not (dwi and sm) or is_autoconverted(folder):
        return []
    written = []
    for name in dwi:
        src = str(Path(folder) / name)
        path = (
            str(Path(src).with_suffix(".sm.converted"))
            if dry_run
            else convert_file(src, str(Path(src).with_suffix(".sm.converted")), overwrite=True)
        )
        if path is not None:
            written.append(path)
    return written


def test_tree(root: str, dry_run: bool = False) -> list[FolderResult]:  # noqa: PT028
    """Write ``<name>.sm.converted`` beside every hand-made .sm under ``root``."""
    results: list[FolderResult] = []
    actions = plan_test_tree(root)
    for folder in find_testable_folders(root):
        folder_actions = [action for action in actions if str(Path(action.source).parent) == folder]
        try:
            if dry_run:
                paths = [action.destination for action in folder_actions]
            else:
                for action in folder_actions:
                    action.accepted = True
                paths = run_planned_actions(iter(folder_actions))
            results.append((folder, paths, None))
        except Exception as exc:
            results.append((folder, [], str(exc)))
    return results


# These are simfile-diff helpers, not pytest cases.
test_folder.__test__ = False
test_tree.__test__ = False


def clear_autoconversions(root: str, dry_run: bool = True) -> list[str]:
    """List (or with ``dry_run=False`` delete) every autoconverted .sm and marker.

    Only touches folders carrying the autoconvert marker, so hand-made .sm
    files are never at risk.
    """
    removed: list[str] = []
    for folder_path in _directories(root):
        folder = str(folder_path)
        if not is_autoconverted(folder):
            continue
        _, sm = _simfiles(folder)
        targets = [str(folder_path / n) for n in sm]
        targets.append(str(folder_path / AUTOCONVERT_MARKER))
        for path in targets:
            removed.append(path)
            if not dry_run:
                with contextlib.suppress(OSError):
                    Path(path).unlink()
    return removed


def _directories(root: str) -> Iterator[Path]:
    root_path = Path(root)
    yield from (current for current, _, _ in root_path.walk())
