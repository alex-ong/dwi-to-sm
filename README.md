# dwi-to-sm

Convert StepMania **DWI** simfiles to the **SM** format.

Parsing follows StepMania's `NotesLoaderDWI.cpp`, so timing (`BPM`, `CHANGEBPM`,
`FREEZE`, `GAP`), jumps, holds, and the 6-panel solo character set behave the way
the game does. Note data round-trips exactly against StepMania's own output.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14.

```powershell
uv python install 3.14
uv sync
```

## Command line

```powershell
# one file -> A.sm next to it
uv run python convert.py testdata/A/A.dwi

# explicit output path
uv run python convert.py testdata/A/A.dwi -o out/A.sm

# bulk: every .dwi under a folder, written next to each source
uv run python convert.py "C:/Songs"

# bulk into a mirrored output tree
uv run python convert.py "C:/Songs" -o "C:/Converted"

# skip songs that already have an .sm
uv run python convert.py "C:/Songs" --no-overwrite
```

Exits non-zero if any file failed; each file prints `OK` or `FAIL`.

## Library

```python
from convert import convert_file, convert_tree, dwi_to_sm, parse_dwi

# single file -> returns the written .sm path
convert_file("testdata/A/A.dwi")
convert_file("testdata/A/A.dwi", "out/A.sm", overwrite=False)

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

`source_dir` and `base_name` are optional arguments to `dwi_to_sm`; pass them if
you want banner/background autodetection, which scans the song folder for
`<name>.png` and `<name>-bg.png` style files.

## Notes and limitations

- Banner and background are guessed from files on disk, since DWI has no tags
  for them. If the folder isn't available, both fields are emitted empty.
- Radar values are written as zeros; StepMania recomputes them on load.
- Supported modes: `SINGLE`, `DOUBLE`, `COUPLE`, `SOLO`.
- Input encoding is detected across UTF-8, Shift-JIS (cp932), cp1252 and
  latin-1; output is written as UTF-8 with LF line endings.

## Test data

`testdata/A/` holds a DWI and the reference SM produced by StepMania for the
same song, useful for verifying that changes don't alter note output.
