# dwi-to-sm

Convert StepMania **DWI** simfiles to the **SM** format.

Parsing follows StepMania's own loader,
[NotesLoaderDWI.cpp](https://github.com/stepmania/stepmania/blob/5_1-new/src/NotesLoaderDWI.cpp),
so timing (`BPM`, `CHANGEBPM`, `FREEZE`, `GAP`), jumps, holds, and the 6-panel
solo character set behave the way the game does. Output follows
[NotesWriterSM.cpp](https://github.com/stepmania/stepmania/blob/5_1-new/src/NotesWriterSM.cpp).
Note data round-trips exactly against StepMania's own output.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14.

```powershell
uv python install 3.14
uv sync
```

## Layout

```
dwi_to_sm/
    dwi.py       parsing the DWI format into DwiSong / DwiChart
    sm.py        rendering a DwiSong as SM file contents
    images.py    banner/background detection from image headers
    files.py     single-file and whole-tree conversion
    folders.py   song-folder autoconversion and diff testing
    cli.py       argument parsing and console output
tests/
    data/A/      a DWI plus the reference SM StepMania produces for it
```

## Command line

```powershell
# one file -> A.sm next to it
uv run python -m dwi_to_sm tests/data/A/A.dwi

# explicit output path
uv run python -m dwi_to_sm tests/data/A/A.dwi -o out/A.sm

# bulk: every .dwi under a folder, written next to each source
uv run python -m dwi_to_sm "C:/Songs"

# bulk into a mirrored output tree
uv run python -m dwi_to_sm "C:/Songs" -o "C:/Converted"

# skip songs that already have an .sm
uv run python -m dwi_to_sm "C:/Songs" --no-overwrite
```

Exits non-zero if any file failed; each file prints `OK` or `FAIL`.

## Song-folder modes

These work on song folders rather than individual files.

```powershell
# autoconvert: only folders that have .dwi and NO .sm, marked with autoconvert.txt
uv run python -m dwi_to_sm "C:/Songs" --auto

# test: folders that already have an .sm get a <name>.sm.converted beside it
uv run python -m dwi_to_sm "C:/Songs" --test

# undo every autoconversion (never touches hand-made .sm files)
uv run python -m dwi_to_sm "C:/Songs" --clear-autoconversions
```

`--auto` is safe to re-run: folders already holding an `.sm` are skipped, so only
new songs get converted. If a converter bug is found, run
`--clear-autoconversions` then `--auto` again to regenerate everything that this
tool produced, leaving hand-authored simfiles alone.

`--test` never overwrites the existing `.sm`, so the pair can be diffed:

```powershell
uv run python -m dwi_to_sm tests/data --test
git diff --no-index tests/data/A/A.sm tests/data/A/A.sm.converted
```

## Library

```python
from dwi_to_sm import convert_file, convert_tree, dwi_to_sm, parse_dwi

# single file -> returns the written .sm path
convert_file("tests/data/A/A.dwi")
convert_file("tests/data/A/A.dwi", "out/A.sm", overwrite=False)

# bulk -> list of (dwi_path, sm_path, error); error is None on success
for src, dst, error in convert_tree("C:/Songs", out_root="C:/Converted"):
    if error:
        print("failed:", src, error)

# pure string -> string (no disk access)
sm_text = dwi_to_sm(open("A.dwi", encoding="utf-8").read())

# inspect the parsed simfile without emitting SM
song = parse_dwi(open("A.dwi", encoding="utf-8").read())
print(song.tag("TITLE"), len(song.charts))
```

Folder-level helpers:

```python
from dwi_to_sm import (
    scan_folder, find_convertible_folders, find_testable_folders,
    autoconvert_folder, autoconvert_tree, test_folder, test_tree,
    is_autoconverted, clear_autoconversions,
)

scan_folder("C:/Songs/A")             # the folder if it's .dwi-only, else None
find_convertible_folders("C:/Songs")  # every .dwi-only folder under a root
find_testable_folders("C:/Songs")     # folders with both .dwi and .sm

autoconvert_folder("C:/Songs/A")      # -> written .sm paths, plus autoconvert.txt
autoconvert_tree("C:/Songs")          # -> [(folder, sm_paths, error), ...]

test_folder("tests/data/A")           # -> written .sm.converted paths
test_tree("tests/data")

is_autoconverted("C:/Songs/A")        # True if autoconvert.txt is present
clear_autoconversions("C:/Songs")               # dry run, returns what it would delete
clear_autoconversions("C:/Songs", dry_run=False)
```

`source_dir` and `base_name` are optional arguments to `dwi_to_sm`; pass them if
you want banner/background autodetection, which inspects the images in the song
folder.

## Notes and limitations

- Banner and background are guessed from the images on disk, since DWI has no
  tags for them. Filename hints (`<song>.png`, `<song>-bg.png`, anything named
  `*banner*`/`*background*`) are used first; otherwise the image headers are read
  directly and the widest image with an aspect ratio of 2.0 or more becomes the
  banner, while the largest remaining image becomes the background. `cdtitle`
  and `jacket` images are ignored. If the folder isn't available, both fields
  are emitted empty.
- Radar values are written as zeros; StepMania recomputes them on load.
- Supported modes: `SINGLE`, `DOUBLE`, `COUPLE`, `SOLO`.
- Input encoding is detected across UTF-8, Shift-JIS (cp932), cp1252 and
  latin-1; output is written as UTF-8 with LF line endings.

## Tests

```powershell
uv run pytest
```

`tests/data/A/` holds a DWI plus the reference SM that StepMania produces for
the same song; the suite asserts that every measure of note data still matches
it. `*.sm.converted` is gitignored.
