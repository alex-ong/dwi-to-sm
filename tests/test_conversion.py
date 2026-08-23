"""The converter must reproduce StepMania's own SM output for the reference song."""

import re

from dwi_to_sm import convert_file, dwi_to_sm, parse_dwi, read_text

# StepMania recomputes these on load, so they are not compared.
RADAR_LINE = re.compile(r"^\s*[\d.]+(,[\d.]+){4}:\s*$")


def parse_sm(text):
    """-> (tags dict, [(steps_type, difficulty, meter, note_lines), ...])"""
    tags, charts = {}, []
    blocks = text.split("#NOTES:")

    for line in blocks[0].splitlines():
        match = re.match(r"^#([A-Z]+):(.*)$", line.strip())
        if match:
            tags[match.group(1)] = match.group(2).rstrip(";")

    for block in blocks[1:]:
        body = block.split(";")[0]
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        lines = [line for line in lines if not RADAR_LINE.match(line + ":")]
        header = [line.rstrip(":") for line in lines[:4]]
        notes = [line for line in lines[4:] if not RADAR_LINE.match(line)]
        charts.append((header[0], header[2], header[3], notes))
    return tags, charts


def test_note_data_matches_stepmania(reference_song):
    reference = parse_sm((reference_song / "A.sm").read_text(encoding="utf-8"))[1]
    generated = parse_sm(
        read_text(convert_file(str(reference_song / "A.dwi"), str(reference_song / "out.sm")))
    )[1]

    assert len(generated) == len(reference) == 9
    for got, want in zip(generated, reference, strict=True):
        assert got == want


def test_header_matches_stepmania(reference_song):
    want = parse_sm((reference_song / "A.sm").read_text(encoding="utf-8"))[0]
    got = parse_sm(
        read_text(convert_file(str(reference_song / "A.dwi"), str(reference_song / "out.sm")))
    )[0]

    for tag in (
        "TITLE",
        "ARTIST",
        "MUSIC",
        "OFFSET",
        "BPMS",
        "SAMPLESTART",
        "SAMPLELENGTH",
        "DISPLAYBPM",
        "CDTITLE",
        "BANNER",
        "BACKGROUND",
    ):
        assert got[tag] == want[tag], tag
    assert got["STOPS"].strip() == want["STOPS"].strip()


def test_parse_dwi_reads_tags_and_charts(reference_song):
    song = parse_dwi(read_text(str(reference_song / "A.dwi")))
    assert song.tag("TITLE") == "A"
    assert len(song.charts) == 9
    assert {c.steps_type for c in song.charts} == {"dance-single", "dance-double"}


def test_dwi_to_sm_needs_no_disk_access():
    sm = dwi_to_sm("#TITLE:X;\n#BPM:120;\n#SINGLE:BASIC:3:0246;\n")
    assert "#TITLE:X;" in sm
    assert "#BPMS:0.000=120.000;" in sm
    assert "     Easy:" in sm
    assert "#BANNER:;" in sm


def test_conversion_prefers_explicit_images_and_finds_lyrics(tmp_path):
    (tmp_path / "Song-bg.png").write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        + (640).to_bytes(4, "big")
        + (480).to_bytes(4, "big")
    )
    (tmp_path / "Song.lrc").write_text("[00:01.00] lyrics")
    text = "#TITLE:Song;\n#BANNER:custom.png;\n#BPM:120;\n"

    output = dwi_to_sm(text, str(tmp_path), "Song")

    assert "#BANNER:custom.png;" in output
    assert "#BACKGROUND:Song-bg.png;" in output
    assert "#LYRICSPATH:Song.lrc;" in output


def test_conversion_ignores_text_files_when_finding_lyrics(tmp_path):
    (tmp_path / "converted.txt").write_text("not lyrics")
    text = "#TITLE:Song;\n#BPM:120;\n"

    output = dwi_to_sm(text, str(tmp_path), "Song")

    assert "#LYRICSPATH:;" in output


def test_conversion_finds_title_matching_music_file(tmp_path):
    (tmp_path / "Song (Full Mix).mp3").write_bytes(b"audio")
    text = "#TITLE:Song;\n#BPM:120;\n"

    output = dwi_to_sm(text, str(tmp_path), "Song")

    assert "#MUSIC:Song (Full Mix).mp3;" in output


def test_conversion_prefers_explicit_music_tag(tmp_path):
    (tmp_path / "fallback.ogg").write_bytes(b"audio")
    text = "#TITLE:Song;\n#FILE:explicit.mp3;\n#BPM:120;\n"

    output = dwi_to_sm(text, str(tmp_path), "Song")

    assert "#MUSIC:explicit.mp3;" in output


def test_convert_file_refuses_to_clobber_by_default(reference_song):
    before = (reference_song / "A.sm").read_bytes()

    assert convert_file(str(reference_song / "A.dwi")) is None
    assert (reference_song / "A.sm").read_bytes() == before

    assert convert_file(str(reference_song / "A.dwi"), overwrite=True) is not None
    assert (reference_song / "A.sm").read_bytes() != before
