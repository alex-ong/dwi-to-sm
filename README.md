# dwi-to-sm

Convert StepMania **DWI** simfiles to the **SM** format.

Parsing follows StepMania's own loader,
[NotesLoaderDWI.cpp](https://github.com/stepmania/stepmania/blob/5_1-new/src/NotesLoaderDWI.cpp),
and output follows
[NotesWriterSM.cpp](https://github.com/stepmania/stepmania/blob/5_1-new/src/NotesWriterSM.cpp),
so note data round-trips exactly against StepMania's own output.

**Existing `.sm` files are never overwritten** unless you pass `--force`.

## Setup

Needs [uv](https://docs.astral.sh/uv/) and Python 3.14.

```powershell
uv sync
```

## Usage

```powershell
# a song library: converts only folders that have a .dwi and no .sm
uv run python -m dwi_to_sm "C:/Songs"

# a single file -> A.sm beside it
uv run python -m dwi_to_sm "C:/Songs/A/A.dwi"

# write somewhere else instead
uv run python -m dwi_to_sm "C:/Songs" -o "C:/Converted"
```

Each result prints `OK`, `SKIP` or `FAIL`; the exit code is non-zero if anything
failed.

Converted folders get an `autoconvert.txt` marker, which makes two things
possible:

```powershell
# re-run any time; only new songs are converted
uv run python -m dwi_to_sm "C:/Songs"

# found a bug? throw away only what this tool made, then convert again
uv run python -m dwi_to_sm "C:/Songs" --clear-autoconversions
uv run python -m dwi_to_sm "C:/Songs"
```

`--clear-autoconversions` only deletes `.sm` files in marked folders, so
hand-made simfiles are never at risk.

To check the converter against songs that already have a hand-made `.sm`,
`--test` writes `<name>.sm.converted` beside them without touching anything:

```powershell
uv run python -m dwi_to_sm tests/data --test
git diff --no-index tests/data/A/A.sm tests/data/A/A.sm.converted
```

Preview that comparison without writing the converted files:

```powershell
uv run python -m dwi_to_sm "S:/games/deadsync/songs" --test --dry-run
```

This prints how many song folders contain both `.dwi` and `.sm` files without
creating the comparison files. Autoconverted folders are excluded. The full
enumerable plan is also available to callers through `plan_test_tree()`.

## Library

```python
from dwi_to_sm import convert_file, autoconvert_tree, dwi_to_sm

convert_file("A.dwi")  # -> path, or None if A.sm exists
convert_file("A.dwi", overwrite=True)  # -> path, clobbers A.sm
autoconvert_tree("C:/Songs")  # -> [(folder, sm_paths, error), ...]
dwi_to_sm(open("A.dwi").read())  # -> str, no disk access
```

Other helpers: `parse_dwi`, `convert_tree`, `scan_folder`,
`find_convertible_folders`, `find_testable_folders`, `autoconvert_folder`,
`test_folder`, `test_tree`, `plan_test_tree`, `run_planned_actions`,
`is_autoconverted`, `clear_autoconversions`.

## GUI

Launch the asynchronous Tkinter interface with:

```powershell
uv run python -m dwi_to_sm.gui
```

Choose an action on `All songs`, a pack, or an individual song. The choice
propagates to every lower layer; press `Run` once to execute the marked work.

For a two-stage test workflow, enumerate `plan_test_tree()` and set each
`PlannedAction.accepted` to `True` or `False`, then pass the actions to
`run_planned_actions()`. Only explicitly accepted actions run.

## GUI

Launch the basic asynchronous Tkinter interface with:

```powershell
uv run python -m dwi_to_sm.gui
```

It scans the selected library in the background, groups songs as
`All songs -> pack -> song`, and lets you mark each song for conversion,
generated-output cleanup, or no action before running the selected work.

## Notes

- Banner and background are guessed from the images in the song folder, since
  DWI has no tags for them: filename hints first, then image dimensions (a ratio
  of 2.0 or wider is a banner, the largest remaining image is the background).
- Radar values are written as zeros; StepMania recomputes them on load.
- Supported modes: `SINGLE`, `DOUBLE`, `COUPLE`, `SOLO`.
- Input encoding is detected across UTF-8, Shift-JIS, cp1252 and latin-1; output
  is UTF-8 with LF endings.

See [DEVELOPMENT.md](DEVELOPMENT.md) to work on the converter.

## License

[GNU General Public License v3.0 or later](LICENSE).
