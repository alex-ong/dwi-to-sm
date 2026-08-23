"""Rendering a parsed DWI song as SM file contents.

Tag order and the ``#NOTES`` block layout follow StepMania's SM writer:
https://github.com/stepmania/stepmania/blob/5_1-new/src/NotesWriterSM.cpp
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from .dwi import ROWS_PER_MEASURE, DwiChart, DwiSong, parse_dwi
from .images import choose_banner_background, list_images

__all__ = ["dwi_to_sm"]

_QUANTIZATIONS = (4, 8, 12, 16, 24, 32, 48, 64, 96, 192)


def _fmt(value: float, places: int = 3) -> str:
    return f"{value:.{places}f}"


def _parse_timestamp(parts: Sequence[str]) -> float:
    """DWI timestamps are ms, seconds, MM:SS.sss or HH:MM:SS.sss.

    Ported from ParseBrokenDWITimestamp() in NotesLoaderDWI.cpp.
    """
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


def _convert_pairs(
    raw: str, scale_beat: float, scale_value: float, value_places: int = 3
) -> list[str]:
    out: list[str] = []
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
        # NotesLoaderDWI.cpp divides CHANGEBPM/FREEZE positions by 4 to get beats.
        bpms.extend(_convert_pairs(change, 0.25, 1.0))

    stops = _convert_pairs(song.tag("FREEZE"), 0.25, 0.001) if song.tag("FREEZE") else []

    banner = song.tag("BANNER")
    background = song.tag("BACKGROUND")
    guessed_banner, guessed_background = choose_banner_background(
        list_images(source_dir),
        (base_name, title, Path(source_dir).name),
        need_banner=not banner,
        need_background=not background,
    )
    banner = banner or guessed_banner
    background = background or guessed_background

    lyric_path = song.tag("LYRICSPATH") or song.tag("LYRICS") or _find_lyrics(
        source_dir, (base_name, title)
    )
    music = song.tag("FILE") or song.tag("MUSIC") or _find_music(
        source_dir, (base_name, title)
    )

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
        f"#LYRICSPATH:{lyric_path};",
        f"#CDTITLE:{song.tag('CDTITLE')};",
        f"#MUSIC:{music};",
        f"#OFFSET:{_fmt(-gap)};",
    ]

    if song.params("SAMPLESTART"):
        lines.append(f"#SAMPLESTART:{_fmt(_parse_timestamp(song.params('SAMPLESTART')))};")
    if song.params("SAMPLELENGTH"):
        length = _parse_timestamp(song.params("SAMPLELENGTH"))
        if 0 < length < 1:  # NotesLoaderDWI.cpp: some files store this in seconds
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


def _find_lyrics(directory: str, bases: Sequence[str]) -> str:
    if not directory or not Path(directory).is_dir():
        return ""
    lyric_extensions = {".lrc", ".lyrics"}
    candidates = sorted(
        path
        for path in Path(directory).iterdir()
        if path.is_file() and path.suffix.lower() in lyric_extensions
    )
    if not candidates:
        return ""
    normalized_bases = {Path(base).stem.casefold() for base in bases if base}
    preferred = [path for path in candidates if path.stem.casefold() in normalized_bases]
    return (preferred or candidates)[0].name


def _find_music(directory: str, bases: Sequence[str]) -> str:
    if not directory or not Path(directory).is_dir():
        return ""
    music_extensions = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav", ".wma"}
    candidates = sorted(
        path
        for path in Path(directory).iterdir()
        if path.is_file() and path.suffix.lower() in music_extensions
    )
    if not candidates:
        return ""
    normalized_bases = {Path(base).stem.casefold() for base in bases if base}
    preferred = [
        path
        for path in candidates
        if path.stem.casefold() in normalized_bases
        or any(base in path.stem.casefold() for base in normalized_bases)
    ]
    return (preferred or candidates)[0].name


def _measure_rows(rows: Sequence[int]) -> int:
    for quant in _QUANTIZATIONS:
        spacing = ROWS_PER_MEASURE // quant
        if all(row % spacing == 0 for row in rows):
            return quant
    return 192


def _chart_body(chart: DwiChart) -> str:
    by_measure: dict[int, dict[int, dict[int, str]]] = {}
    for (row, col), value in chart.notes.items():
        measure = row // ROWS_PER_MEASURE
        by_measure.setdefault(measure, {}).setdefault(row % ROWS_PER_MEASURE, {})[col] = value

    last_measure = max(by_measure) if by_measure else 0
    measures: list[str] = []
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
    # Block layout matches GetSMNotesTag() in NotesWriterSM.cpp.
    return (
        f"\n//---------------{chart.steps_type} - {description}----------------\n"
        "#NOTES:\n"
        f"     {chart.steps_type}:\n"
        f"     {description}:\n"
        f"     {chart.difficulty}:\n"
        f"     {chart.meter}:\n"
        # StepMania recomputes radar values on load.
        "     0.000,0.000,0.000,0.000,0.000:\n"
        f"{_chart_body(chart)}\n;\n\n"
    )


def dwi_to_sm(text: str, source_dir: str = "", base_name: str = "") -> str:
    """Convert the contents of a .dwi file into .sm file contents."""
    song = parse_dwi(text)
    parts = [_build_header(song, source_dir, base_name)]
    parts.extend(_chart_to_sm(chart) for chart in song.charts)
    return "".join(parts)
