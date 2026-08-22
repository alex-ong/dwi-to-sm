"""DWI -> SM simfile converter.

Usable as a library::

    from convert import convert_file, convert_tree, dwi_to_sm

    convert_file("song/A.dwi")                 # writes song/A.sm
    convert_tree("C:/Songs")                   # bulk: every .dwi under a folder
    sm_text = dwi_to_sm(open("A.dwi").read())  # pure string -> string

The parsing rules follow StepMania's NotesLoaderDWI.cpp so timing, jumps,
holds and the 6-panel (solo) character set behave the same way the game does.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "DwiChart",
    "DwiSong",
    "parse_dwi",
    "dwi_to_sm",
    "convert_file",
    "convert_tree",
]

# 192nd notes are the finest supported quantization -> 48 rows per beat.
ROWS_PER_BEAT = 48
ROWS_PER_MEASURE = ROWS_PER_BEAT * 4

# Panel names used as an intermediate, pad-independent representation.
L, D, U, R, UL, UR = "L", "D", "U", "R", "UL", "UR"

DWI_CHARS: Dict[str, Tuple[str, ...]] = {
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

# mode -> (sm steps type, panel->column map per pad, number of tracks)
_SINGLE_COLS = {L: 0, D: 1, U: 2, R: 3}
_SOLO_COLS = {L: 0, UL: 1, D: 2, U: 3, UR: 4, R: 5}

MODES: Dict[str, Tuple[str, Dict[str, int], int, int]] = {
    # dwi tag: (sm type, column map, tracks per pad, pads)
    "SINGLE": ("dance-single", _SINGLE_COLS, 4, 1),
    "DOUBLE": ("dance-double", _SINGLE_COLS, 4, 2),
    "COUPLE": ("dance-couple", _SINGLE_COLS, 4, 2),
    "SOLO": ("dance-solo", _SOLO_COLS, 6, 1),
}

DIFFICULTIES: Dict[str, str] = {
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
    "(": Fraction(1, 4),    # 1/16 notes
    "[": Fraction(1, 6),    # 1/24 notes
    "{": Fraction(1, 16),   # 1/64 notes
    "`": Fraction(1, 48),   # 1/192 notes
}
_CLOSERS = ")]}'>"
_DEFAULT_STEP = Fraction(1, 2)  # 1/8 notes

_QUANTIZATIONS = (4, 8, 12, 16, 24, 32, 48, 64, 96, 192)

_ENCODINGS = ("utf-8-sig", "cp932", "cp1252", "latin-1")


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
    notes: Dict[Tuple[int, int], str] = field(default_factory=dict)


@dataclass
class DwiSong:
    tags: Dict[str, List[str]] = field(default_factory=dict)
    charts: List[DwiChart] = field(default_factory=list)

    def tag(self, name: str, default: str = "") -> str:
        """Full raw value of a tag (parameters rejoined with ':')."""
        params = self.tags.get(name)
        return ":".join(params) if params else default

    def params(self, name: str) -> List[str]:
        return list(self.tags.get(name, []))


# --------------------------------------------------------------------------
# DWI parsing
# --------------------------------------------------------------------------

def _strip_comments(text: str) -> str:
    # Don't eat the "//" of things like "http://" or a path written as ".//x".
    return re.sub(r"(?<!:)//[^\n]*", "", text)


def _parse_msd(text: str) -> List[List[str]]:
    """Split a MSD-style file into ``[tag, param, param, ...]`` lists."""
    text = _strip_comments(text)
    values: List[List[str]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "#":
            i += 1
            continue
        i += 1
        params: List[str] = []
        buf: List[str] = []
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
    """`<...>` means 1/192nds if it contains a '0', otherwise it's a jump."""
    for c in data[pos:]:
        if c == ">":
            return False
        if c == "0":
            return True
    return False


def _columns(char: str, colmap: Dict[str, int], offset: int) -> List[int]:
    panels = DWI_CHARS.get(char.upper())
    if panels is None:
        return []
    return [colmap[p] + offset for p in panels if p in colmap]


def _parse_step_data(data: str, colmap: Dict[str, int], offset: int,
                     notes: Dict[Tuple[int, int], str]) -> None:
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


def _resolve_holds(notes: Dict[Tuple[int, int], str], num_tracks: int) -> None:
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


def _parse_chart(params: Sequence[str]) -> Optional[DwiChart]:
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
    notes: Dict[Tuple[int, int], str] = {}
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


# --------------------------------------------------------------------------
# Header conversion
# --------------------------------------------------------------------------

def _fmt(value: float, places: int = 3) -> str:
    return f"{value:.{places}f}"


def _parse_timestamp(parts: Sequence[str]) -> float:
    """DWI timestamps are ms, seconds, MM:SS.sss or HH:MM:SS.sss."""
    parts = [p for p in parts if p != ""]
    if not parts:
        return 0.0
    if len(parts) == 1:
        value = float(parts[0])
        return value if "." in parts[0] else value / 1000.0
    total = 0.0
    for part in parts:
        total = total * 60.0 + float(part)
    return total


def _convert_pairs(raw: str, scale_beat: float, scale_value: float,
                   value_places: int = 3) -> List[str]:
    out: List[str] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if "=" not in chunk:
            continue
        beat_s, _, value_s = chunk.partition("=")
        try:
            beat = float(beat_s) * scale_beat
            value = float(value_s) * scale_value
        except ValueError:
            continue
        out.append(f"{_fmt(beat)}={_fmt(value, value_places)}")
    return out


def _display_bpm(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if raw == "*":
        return "*"
    match = re.match(r"^\s*([0-9.]+)\.\.([0-9.]+)\s*$", raw)
    if match:
        return f"{_fmt(float(match.group(1)))}:{_fmt(float(match.group(2)))}"
    try:
        return _fmt(float(raw))
    except ValueError:
        return ""


def _find_image(directory: str, base: str, suffixes: Iterable[str]) -> str:
    if not directory or not os.path.isdir(directory):
        return ""
    try:
        entries = os.listdir(directory)
    except OSError:
        return ""
    lowered = {e.lower(): e for e in entries}
    for suffix in suffixes:
        for ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
            candidate = (base + suffix + ext).lower()
            if candidate in lowered:
                return lowered[candidate]
    return ""


def _build_header(song: DwiSong, source_dir: str, base_name: str) -> str:
    title = song.tag("TITLE")
    gap = _parse_timestamp(song.params("GAP")) if song.params("GAP") else 0.0

    bpms = []
    try:
        bpms.append(f"0.000={_fmt(float(song.tag('BPM', '0')))}")
    except ValueError:
        bpms.append("0.000=60.000")
    change = song.tag("CHANGEBPM") or song.tag("BPMCHANGE")
    if change:
        # DWI counts CHANGEBPM/FREEZE positions in quarter-beats.
        bpms.extend(_convert_pairs(change, 0.25, 1.0))

    stops = _convert_pairs(song.tag("FREEZE"), 0.25, 0.001) if song.tag("FREEZE") else []

    banner = song.tag("BANNER") or _find_image(source_dir, base_name, ("",)) \
        or _find_image(source_dir, title, ("",))
    background = song.tag("BACKGROUND") \
        or _find_image(source_dir, base_name, ("-bg", "bg", " bg", "-background")) \
        or _find_image(source_dir, title, ("-bg", "bg", " bg", "-background"))

    lines = [
        f"#TITLE:{title};",
        f"#SUBTITLE:{song.tag('SUBTITLE')};",
        f"#ARTIST:{song.tag('ARTIST')};",
        f"#TITLETRANSLIT:{song.tag('DISPLAYTITLE')};",
        "#SUBTITLETRANSLIT:;",
        f"#ARTISTTRANSLIT:{song.tag('DISPLAYARTIST')};",
        f"#GENRE:{song.tag('GENRE')};",
        f"#CREDIT:{song.tag('CREDIT')};",
        f"#BANNER:{banner};",
        f"#BACKGROUND:{background};",
        "#LYRICSPATH:;",
        f"#CDTITLE:{song.tag('CDTITLE')};",
        f"#MUSIC:{song.tag('FILE')};",
        f"#OFFSET:{_fmt(-gap)};",
    ]

    if song.params("SAMPLESTART"):
        lines.append(f"#SAMPLESTART:{_fmt(_parse_timestamp(song.params('SAMPLESTART')))};")
    if song.params("SAMPLELENGTH"):
        length = _parse_timestamp(song.params("SAMPLELENGTH"))
        if 0 < length < 1:  # some files store this in seconds-as-ms
            length *= 1000
        lines.append(f"#SAMPLELENGTH:{_fmt(length)};")

    lines.append("#SELECTABLE:YES;")

    display = _display_bpm(song.tag("DISPLAYBPM"))
    if display:
        lines.append(f"#DISPLAYBPM:{display};")

    lines.append(f"#BPMS:{','.join(bpms)};")
    lines.append(f"#STOPS:{','.join(stops)};")
    lines.append("#BGCHANGES:;")
    lines.append("#KEYSOUNDS:;")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Note data output
# --------------------------------------------------------------------------

def _measure_rows(rows: Sequence[int]) -> int:
    for quant in _QUANTIZATIONS:
        spacing = ROWS_PER_MEASURE // quant
        if all(row % spacing == 0 for row in rows):
            return quant
    return 192


def _chart_body(chart: DwiChart) -> str:
    by_measure: Dict[int, Dict[int, Dict[int, str]]] = {}
    for (row, col), value in chart.notes.items():
        measure = row // ROWS_PER_MEASURE
        by_measure.setdefault(measure, {}).setdefault(row % ROWS_PER_MEASURE, {})[col] = value

    last_measure = max(by_measure) if by_measure else 0
    measures: List[str] = []
    for measure in range(last_measure + 1):
        rows = by_measure.get(measure, {})
        quant = _measure_rows(sorted(rows)) if rows else 4
        spacing = ROWS_PER_MEASURE // quant
        lines = []
        for index in range(quant):
            cols = rows.get(index * spacing, {})
            lines.append("".join(cols.get(c, "0") for c in range(chart.num_tracks)))
        measures.append("\n".join(lines))
    return "\n,\n".join(measures)


def _chart_to_sm(chart: DwiChart, description: str = "") -> str:
    return (
        f"\n//---------------{chart.steps_type} - {description}----------------\n"
        "#NOTES:\n"
        f"     {chart.steps_type}:\n"
        f"     {description}:\n"
        f"     {chart.difficulty}:\n"
        f"     {chart.meter}:\n"
        "     0.000,0.000,0.000,0.000,0.000:\n"
        f"{_chart_body(chart)}\n;\n\n"
    )


def dwi_to_sm(text: str, source_dir: str = "", base_name: str = "") -> str:
    """Convert the contents of a .dwi file into .sm file contents."""
    song = parse_dwi(text)
    parts = [_build_header(song, source_dir, base_name)]
    parts.extend(_chart_to_sm(chart) for chart in song.charts)
    return "".join(parts)


# --------------------------------------------------------------------------
# File / bulk helpers
# --------------------------------------------------------------------------

def _read_text(path: str) -> str:
    with open(path, "rb") as handle:
        raw = handle.read()
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def convert_file(dwi_path: str, sm_path: Optional[str] = None,
                 overwrite: bool = True, encoding: str = "utf-8") -> str:
    """Convert one .dwi file. Returns the path of the written .sm file."""
    dwi_path = os.path.abspath(dwi_path)
    if sm_path is None:
        sm_path = os.path.splitext(dwi_path)[0] + ".sm"
    if not overwrite and os.path.exists(sm_path):
        return sm_path

    base_name = os.path.splitext(os.path.basename(dwi_path))[0]
    sm_text = dwi_to_sm(_read_text(dwi_path), os.path.dirname(dwi_path), base_name)

    os.makedirs(os.path.dirname(os.path.abspath(sm_path)) or ".", exist_ok=True)
    with open(sm_path, "w", encoding=encoding, newline="\n") as handle:
        handle.write(sm_text)
    return sm_path


def convert_tree(root: str, out_root: Optional[str] = None,
                 overwrite: bool = True) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """Convert every .dwi under ``root``.

    Returns ``(dwi_path, sm_path, error)`` per file; ``error`` is None on success.
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Convert DWI simfiles to SM.")
    parser.add_argument("inputs", nargs="+", help=".dwi files or folders to convert")
    parser.add_argument("-o", "--out", help="output file (single input) or output root folder")
    parser.add_argument("-n", "--no-overwrite", action="store_true",
                        help="skip files whose .sm already exists")
    args = parser.parse_args(argv)

    failures = 0
    for target in args.inputs:
        if os.path.isdir(target):
            for src, dst, error in convert_tree(target, args.out, not args.no_overwrite):
                if error:
                    failures += 1
                    print(f"FAIL {src}: {error}")
                else:
                    print(f"OK   {src} -> {dst}")
        else:
            try:
                dst = convert_file(target, args.out, not args.no_overwrite)
                print(f"OK   {target} -> {dst}")
            except Exception as exc:
                failures += 1
                print(f"FAIL {target}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
