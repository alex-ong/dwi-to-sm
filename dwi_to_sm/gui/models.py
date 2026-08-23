"""Data models for the asynchronous GUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Action = Literal["convert", "remove", "none"]


@dataclass
class SongEntry:
    folder: Path
    pack: str
    dwi_files: list[str]
    sm_files: list[str]
    generated_files: list[Path]
    autoconverted: bool
    action: Action = "none"

    @property
    def progress(self) -> int:
        if not self.dwi_files:
            return 0
        return min(100, round(len(self.sm_files) / len(self.dwi_files) * 100))


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
