"""Data models for the asynchronous GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Action = Literal["convert", "remove", "none"]


@dataclass
class BarCounts:
    """How many of a song's (or pack's) files are in each conversion state."""

    total: int
    passed: int = 0
    no_op: int = 0
    failed: int = 0

    @property
    def not_done(self) -> int:
        return max(0, self.total - self.passed - self.no_op - self.failed)

    def __add__(self, other: BarCounts) -> BarCounts:
        return BarCounts(
            self.total + other.total,
            self.passed + other.passed,
            self.no_op + other.no_op,
            self.failed + other.failed,
        )


@dataclass
class SongEntry:
    folder: Path
    pack: str
    dwi_files: list[str]
    sm_files: list[str]
    generated_files: list[Path]
    autoconverted: bool
    action: Action = "none"
    error: str | None = None
    already_converted: list[str] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)

    @property
    def progress(self) -> int:
        if not self.dwi_files:
            return 0
        return min(100, round(len(self.sm_files) / len(self.dwi_files) * 100))

    @property
    def counts(self) -> BarCounts:
        total = len(self.dwi_files)
        if self.action == "none":
            # Opting out is treated as instantly done, not left pending.
            return BarCounts(total, no_op=total)
        no_op = min(len(self.already_converted), total)
        passed = max(0, min(len(self.sm_files), total) - no_op)
        failed = min(len(self.failed_files), total - no_op - passed)
        return BarCounts(total, passed, no_op, failed)


@dataclass
class TreeNode:
    name: str
    kind: Literal["all", "pack", "song"]
    entry: SongEntry | None = None
    children: list[TreeNode] = field(default_factory=list)
    action: Action = "none"

    @property
    def progress(self) -> int:
        if self.entry is not None:
            return self.entry.progress
        if not self.children:
            return 0
        return round(sum(child.progress for child in self.children) / len(self.children))

    @property
    def counts(self) -> BarCounts:
        if self.entry is not None:
            return self.entry.counts
        if not self.children:
            return BarCounts(total=0)
        total = BarCounts(total=0)
        for child in self.children:
            total += child.counts
        return total

    @property
    def autoconverted(self) -> bool | None:
        if self.entry is not None:
            return self.entry.autoconverted
        statuses = {child.autoconverted for child in self.children}
        return statuses.pop() if len(statuses) == 1 else None



@dataclass
class ScanResult:
    root: Path
    songs: list[SongEntry] = field(default_factory=list)
    tree: TreeNode | None = None


@dataclass
class Progress:
    completed: int
    total: int
    folder: Path
    progress: int
    message: str
    error: str | None = None


@dataclass
class ErrorEntry:
    """One failed song, shown as a row in the error pane."""

    folder: Path
    message: str
