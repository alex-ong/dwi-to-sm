"""Parsing of the DWI simfile format.

The rules here mirror StepMania's own DWI loader, so timing, jumps, holds and
the 6-panel (solo) character set behave the same way the game does:
https://github.com/stepmania/stepmania/blob/5_0/src/NotesLoaderDWI.cpp

Note: the 5_1/5_1-new branches introduced a bug in the jump-note loop that
silently drops every other note inside a bracket like "<13>" (see
https://github.com/stepmania/stepmania/issues/2297). This module follows the
correct 5_0 read-once-per-iteration loop instead.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction

__all__ = [
    "DIFFICULTIES",
    "DWI_CHARS",
    "MODES",
    "ROWS_PER_BEAT",
    "ROWS_PER_MEASURE",
    "DwiChart",
    "DwiError",
    "DwiSong",
    "parse_dwi",
]

# 192nd notes are the finest supported quantization -> 48 rows per beat.
ROWS_PER_BEAT = 48
ROWS_PER_MEASURE = ROWS_PER_BEAT * 4

# Panel names used as an intermediate, pad-independent representation.
L, D, U, R, UL, UR = "L", "D", "U", "R", "UL", "UR"

# Mirrors DWIcharToNote() in NotesLoaderDWI.cpp.
DWI_CHARS: dict[str, tuple[str, ...]] = {
    "0": (),
    "1": (D, L),
    "2": (D,),
    "3": (D, R),
    "4": (L,),
    "5": (),
    "6": (R,),
    "7": (U, L),
    "8": (U,),
    "9": (U, R),
    "A": (U, D),
    "B": (L, R),
    # 6-panel (solo) extras
    "C": (UL,),
    "D": (UR,),
    "E": (L, UL),
    "F": (UL, D),
    "G": (UL, U),
    "H": (UL, R),
    "I": (L, UR),
    "J": (D, UR),
    "K": (U, UR),
    "L": (UR, R),
    "M": (UL, UR),
}

_SINGLE_COLS = {L: 0, D: 1, U: 2, R: 3}
_SOLO_COLS = {L: 0, UL: 1, D: 2, U: 3, UR: 4, R: 5}

MODES: dict[str, tuple[str, dict[str, int], int, int]] = {
    # dwi tag: (sm steps type, panel->column map, tracks per pad, pads)
    "SINGLE": ("dance-single", _SINGLE_COLS, 4, 1),
    "DOUBLE": ("dance-double", _SINGLE_COLS, 4, 2),
    "COUPLE": ("dance-couple", _SINGLE_COLS, 4, 2),
    "SOLO": ("dance-solo", _SOLO_COLS, 6, 1),
}

# Mirrors DwiCompatibleStringToDifficulty() in NotesLoaderDWI.cpp.
DIFFICULTIES: dict[str, str] = {
    "BEGINNER": "Beginner",
    "EASY": "Easy",
    "BASIC": "Easy",
    "LIGHT": "Easy",
    "MEDIUM": "Medium",
    "ANOTHER": "Medium",
    "TRICK": "Medium",
    "STANDARD": "Medium",
    "DIFFICULT": "Medium",
    "HARD": "Hard",
    "SSR": "Hard",
    "MANIAC": "Hard",
    "HEAVY": "Hard",
    "SMANIAC": "Challenge",
    "CHALLENGE": "Challenge",
    "EXPERT": "Challenge",
    "ONI": "Challenge",
    "EDIT": "Edit",
}

# Step-length (in beats) opened by each bracket character.
_OPENERS = {
    "(": Fraction(1, 4),  # 1/16 notes
    "[": Fraction(1, 6),  # 1/24 notes
    "{": Fraction(1, 16),  # 1/64 notes
    "`": Fraction(1, 48),  # 1/192 notes
}
_CLOSERS = ")]}'>"
_DEFAULT_STEP = Fraction(1, 2)  # 1/8 notes


class DwiError(Exception):
    """Raised when a .dwi file cannot be parsed."""


@dataclass
class DwiChart:
    mode: str
    steps_type: str
    difficulty: str
    meter: int
    num_tracks: int
    # (row, column) -> "1" tap / "2" hold head / "3" hold tail
    notes: dict[tuple[int, int], str] = field(default_factory=dict)


@dataclass
class DwiSong:
    tags: dict[str, list[str]] = field(default_factory=dict)
    charts: list[DwiChart] = field(default_factory=list)

    def tag(self, name: str, default: str = "") -> str:
        """Full raw value of a tag (parameters rejoined with ':')."""
        params = self.tags.get(name)
        return ":".join(params) if params else default

    def params(self, name: str) -> list[str]:
        return list(self.tags.get(name, []))


def _strip_comments(text: str) -> str:
    # Don't eat the "//" of things like "http://" or a path written as ".//x".
    return re.sub(r"(?<!:)//[^\n]*", "", text)


def _parse_msd(text: str) -> list[list[str]]:
    """Split a MSD-style file into ``[tag, param, param, ...]`` lists.

    See MsdFile.cpp:
    https://github.com/stepmania/stepmania/blob/5_1-new/src/MsdFile.cpp
    """
    text = _strip_comments(text)
    values: list[list[str]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "#":
            i += 1
            continue
        i += 1
        params: list[str] = []
        buf: list[str] = []
        while i < n:
            c = text[i]
            if c == ";":
                i += 1
                break
            if c == "#":  # value was never terminated; recover
                break
            if c == ":":
                params.append("".join(buf))
                buf = []
                i += 1
                continue
            buf.append(c)
            i += 1
        params.append("".join(buf))
        values.append(params)
    return values


def _is_192(data: str, pos: int) -> bool:
    """`<...>` means 1/192nds if it contains a '0', otherwise it's a jump.

    Same heuristic as OneLineIs192nd() in NotesLoaderDWI.cpp: DWI originally
    used `<...>` for 192nds and later reused it for jumps.
    """
    for c in data[pos:]:
        if c == ">":
            return False
        if c == "0":
            return True
    return False


def _columns(char: str, colmap: dict[str, int], offset: int) -> list[int]:
    panels = DWI_CHARS.get(char.upper())
    if panels is None:
        return []
    return [colmap[p] + offset for p in panels if p in colmap]


def _parse_step_data(
    data: str, colmap: dict[str, int], offset: int, notes: dict[tuple[int, int], str]
) -> None:
    data = re.sub(r"\s", "", data)
    beat = Fraction(0)
    step = _DEFAULT_STEP
    i, n = 0, len(data)

    while i < n:
        c = data[i]
        i += 1

        if c in _OPENERS:
            step = _OPENERS[c]
            continue
        if c in _CLOSERS:
            step = _DEFAULT_STEP
            continue
        if c == "!":  # stray hold marker
            continue

        jump = False
        if c == "<":
            if _is_192(data, i):
                step = Fraction(1, 48)
                continue
            jump = True
        else:
            i -= 1  # re-read this character as a note below

        row = int(beat * ROWS_PER_BEAT)
        while i < n:
            c = data[i]
            i += 1
            if jump and c == ">":
                break

            for col in _columns(c, colmap, offset):
                notes.setdefault((row, col), "1")

            if i < n and data[i] == "!":
                i += 1
                if i < n:
                    hold_char = data[i]
                    i += 1
                    for col in _columns(hold_char, colmap, offset):
                        notes[(row, col)] = "2"

            if not jump:
                break

        beat += step


def _resolve_holds(notes: dict[tuple[int, int], str], num_tracks: int) -> None:
    """A DWI hold ends at the next note in the same column; that note is eaten."""
    for col in range(num_tracks):
        rows = sorted(r for (r, c) in notes if c == col)
        idx = 0
        while idx < len(rows):
            row = rows[idx]
            if notes.get((row, col)) != "2":
                idx += 1
                continue
            if idx + 1 < len(rows):
                notes[(rows[idx + 1], col)] = "3"
                idx += 2
            else:
                del notes[(row, col)]  # unclosed hold: drop it
                idx += 1


def _parse_chart(params: Sequence[str]) -> DwiChart | None:
    mode = params[0].upper()
    steps_type, colmap, tracks_per_pad, pads = MODES[mode]
    if len(params) < 4:
        return None

    difficulty = DIFFICULTIES.get(params[1].strip().upper(), "Edit")
    try:
        meter = int(float(params[2].strip() or 1))
    except ValueError:
        meter = 1

    num_tracks = tracks_per_pad * pads
    notes: dict[tuple[int, int], str] = {}
    for pad in range(pads):
        index = 3 + pad
        if index >= len(params) or not params[index].strip():
            continue
        _parse_step_data(params[index], colmap, pad * tracks_per_pad, notes)

    _resolve_holds(notes, num_tracks)
    if not notes:
        return None

    return DwiChart(mode, steps_type, difficulty, meter, num_tracks, notes)


def parse_dwi(text: str) -> DwiSong:
    """Parse the contents of a .dwi file."""
    song = DwiSong()
    for params in _parse_msd(text):
        if not params:
            continue
        name = params[0].strip().upper()
        if name in MODES:
            chart = _parse_chart(params)
            if chart is not None:
                song.charts.append(chart)
        else:
            song.tags[name] = [p.strip() for p in params[1:]]
    if not song.tags and not song.charts:
        raise DwiError("no DWI tags found")
    return song
