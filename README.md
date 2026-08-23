# dwi-to-sm

Convert StepMania **DWI** simfiles to the **SM** format.

Parsing follows StepMania's own loader from version `5_0`,
[NotesLoaderDWI.cpp](https://github.com/stepmania/stepmania/blob/5_0/src/NotesLoaderDWI.cpp)
and output follows
[NotesWriterSM.cpp](https://github.com/stepmania/stepmania/blob/5_1-new/src/NotesWriterSM.cpp),
so note data round-trips exactly against StepMania's own output.

> [!NOTE]
> Folders with both sm and dwi will be ignored.
> 
> The `5_0` DWI loader is the reference, since `5_1` have a jump-note parsing bug, see
[stepmania#2297](https://github.com/stepmania/stepmania/issues/2297)),


## Running in windows
A precompiled binary is available in [releases](https://github.com/alex-ong/dwi-to-sm/releases) page.
Here is an example of converting 500~ files, with error handling:

https://github.com/user-attachments/assets/4ddae324-ecd5-4254-9689-10cf4674c265

You can also remove converted files, since we create a metadata file marking the conversion.

https://github.com/user-attachments/assets/5bfbe9be-8fd5-488b-99e3-4a2b21b6336c

## Running in Other OS's
Setup the repo then run it. For some OS's you might have to install `tkinter`

## Setup

Needs [uv](https://docs.astral.sh/uv/) and Python 3.14.

```bash
uv sync
```

## Usage

Launch the asynchronous Tkinter interface with:

```bash
uv run python -m dwi_to_sm.gui
```

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
