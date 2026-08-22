# Development

## Setup

The project is managed with [uv](https://docs.astral.sh/uv/). Python 3.14 is
pinned in `.python-version`.

```powershell
# install uv (Windows)
winget install --id=astral-sh.uv

uv python install 3.14
uv sync
```

`uv sync` creates `.venv/` and installs the dev dependency group. There are no
runtime dependencies — only the standard library — so nothing is needed to run
the converter itself.

Common uv commands:

```powershell
uv sync                      # match .venv to pyproject.toml + uv.lock
uv add --dev <package>       # add a dev dependency and update the lock
uv lock --upgrade            # refresh uv.lock
uv run <command>             # run inside the project venv without activating it
```

`uv.lock` is committed on purpose; commit it alongside any dependency change.

## Project layout

```
dwi_to_sm/
    dwi.py       parsing the DWI format into DwiSong / DwiChart
    sm.py        rendering a DwiSong as SM file contents
    images.py    banner/background detection from image headers
    files.py     single-file and whole-tree conversion
    folders.py   song-folder autoconversion and diff testing
    cli.py       argument parsing and console output
    __main__.py  python -m dwi_to_sm
tests/
    data/A/      a DWI plus the reference SM StepMania produces for it
```

The package lives at the repository root rather than under `src/`, because
`[tool.uv] package = false` means the project is never built or installed. If
distribution is wanted later, add a build backend and move the package into
`src/`.

## Running the tool

```powershell
uv run python -m dwi_to_sm tests/data/A/A.dwi -o out.sm
uv run python -m dwi_to_sm --help
```

The converter never overwrites an existing `.sm` unless `--force` is passed.
Keep it that way: a bug in this tool must never be able to destroy someone's
hand-authored simfiles. `convert_file()` returns `None` rather than writing when
the target already exists.

## Tests

```powershell
uv run pytest              # whole suite
uv run pytest -q           # quiet
uv run pytest -x           # stop at the first failure
uv run pytest tests/test_conversion.py
uv run pytest -k banner    # by name
```

`pythonpath = ["."]` in `pyproject.toml` is what makes `import dwi_to_sm` work
under pytest without the project being installed.

### What the suite covers

| File | Covers |
| --- | --- |
| `test_conversion.py` | note data and header tags match StepMania's reference `.sm` |
| `test_images.py` | banner/background detection from image headers |
| `test_folders.py` | scanning, autoconversion, and the safety of `clear_autoconversions` |
| `test_cli.py` | argument handling, overwrite protection, and exit codes |

Fixtures live in `tests/conftest.py`:

- `reference_song` — a temp copy of `tests/data/A` (a `.dwi` plus StepMania's
  `.sm` and images)
- `dwi_only_song` — a temp folder holding just a `.dwi`
- `write_png` — writes a header-only PNG of a given size, for the image tests

Every fixture copies into `tmp_path`, so tests never write into `tests/data/`.

### The reference simfile

`tests/data/A/A.sm` was produced by StepMania itself from `A.dwi`. It is the
ground truth for the converter: `test_note_data_matches_stepmania` asserts that
every measure of every chart still comes out identical.

Two fields are deliberately excluded from the comparison:

- **Radar values** — written as zeros, since StepMania recomputes them on load.
- **`#STOPS` line breaks** — StepMania puts the trailing `;` on its own line.

If a change makes note data differ, that is a regression, not a formatting
detail.

### Eyeballing a diff

For a whole song library, `--test` writes `<name>.sm.converted` next to any
hand-made `.sm` without touching it. Folders carrying `autoconvert.txt` are
skipped, since diffing our output against our own output proves nothing.

```powershell
uv run python -m dwi_to_sm tests/data --test
git diff --no-index tests/data/A/A.sm tests/data/A/A.sm.converted
```

`*.sm.converted` is gitignored.

## Adding format support

The DWI side is derived from StepMania's loader; keep it that way when adding
cases, and cite the function you ported from:

- [NotesLoaderDWI.cpp](https://github.com/stepmania/stepmania/blob/5_1-new/src/NotesLoaderDWI.cpp)
- [NotesWriterSM.cpp](https://github.com/stepmania/stepmania/blob/5_1-new/src/NotesWriterSM.cpp)
- [MsdFile.cpp](https://github.com/stepmania/stepmania/blob/5_1-new/src/MsdFile.cpp)

Rough guide to where things go:

- new step characters or pad modes → `dwi.py` (`DWI_CHARS`, `MODES`)
- new SM header tags → `sm.py` (`_build_header`)
- new image heuristics → `images.py`
- new bulk workflows → `folders.py`, then surface them in `cli.py`

Adding a second song to `tests/data/` is the best way to cover a format edge
case: drop in the `.dwi` and the `.sm` StepMania generates from it.
