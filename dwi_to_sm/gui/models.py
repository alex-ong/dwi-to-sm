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
class ScanResult:
    root: Path
    songs: list[SongEntry] = field(default_factory=list)


@dataclass
class Progress:
    completed: int
    total: int
    folder: Path
    progress: int
    message: str
