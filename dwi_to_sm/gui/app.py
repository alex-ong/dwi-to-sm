"""Tkinter application for asynchronous song-library conversion."""

from __future__ import annotations

import argparse
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .models import Progress, ScanResult, SongEntry
from .operations import execute, operation_count, scan_library


class App:
    def __init__(self, root: tk.Tk, initial_folder: Path | None = None):
        self.root = root
        self.root.title("DWI to SM")
        self.root.geometry("900x620")
        self.events: queue.Queue[object] = queue.Queue()
        self.entries: dict[str, SongEntry] = {}
        self.progress_bars: dict[str, ttk.Progressbar] = {}
        self.selected_iid: str | None = None
        self.action = tk.StringVar(value="none")
        self.status = tk.StringVar(value="Select a song folder to begin.")
        self.total_progress = ttk.Progressbar(root, mode="determinate")
        self._build()
        self.root.after(100, self._poll)
        if initial_folder is not None:
            self._choose(initial_folder)
        else:
            self.root.after(150, self.choose_folder)

    def _build(self) -> None:
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Choose folder", command=self.choose_folder).pack(side="left")
        ttk.Button(toolbar, text="Run selected", command=self.run_selected).pack(
            side="left", padx=8
        )
        ttk.Label(toolbar, textvariable=self.status).pack(side="left", padx=8)

        body = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            body,
            columns=("autoconverted", "progress", "action"),
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="All songs")
        self.tree.heading("autoconverted", text="Autoconverted")
        self.tree.heading("progress", text="Progress")
        self.tree.heading("action", text="Action")
        self.tree.column("#0", width=500)
        self.tree.column("autoconverted", width=120, anchor="center")
        self.tree.column("progress", width=130, anchor="center")
        self.tree.column("action", width=100, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self._scroll_tree)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=self._set_scrollbar)
        self.tree.bind("<<TreeviewSelect>>", self._select_song)
        self.tree.bind("<Configure>", lambda _event: self._place_progress_bars())

        actions = ttk.LabelFrame(self.root, text="Selected song action", padding=8)
        actions.pack(fill="x", padx=8, pady=(0, 8))
        for label, value in (
            ("Convert", "convert"),
            ("Remove conversion", "remove"),
            ("None", "none"),
        ):
            ttk.Radiobutton(
                actions, text=label, value=value, variable=self.action, command=self._set_action
            ).pack(side="left", padx=(0, 16))
        self.total_progress.pack(fill="x", padx=8)
        ttk.Label(self.root, textvariable=self.status, anchor="w").pack(fill="x", padx=8, pady=8)

    def _scroll_tree(self, *args: str) -> None:
        self.tree.yview(*args)
        self._place_progress_bars()

    def _set_scrollbar(self, first: str, last: str) -> None:
        self.tree.master.winfo_children()[-1].set(first, last)
        self._place_progress_bars()

    def _place_progress_bars(self) -> None:
        for iid, bar in self.progress_bars.items():
            box = self.tree.bbox(iid, "#2")
            if not box:
                bar.place_forget()
                continue
            x, y, width, height = box
            bar.place(x=x + 3, y=y + 3, width=max(10, width - 6), height=max(10, height - 6))

    def choose_folder(self) -> None:
        selected = filedialog.askdirectory(title="Choose song library")
        if selected:
            self._choose(Path(selected))

    def _choose(self, folder: Path) -> None:
        self.status.set(f"Scanning {folder}...")
        self._set_enabled(False)
        threading.Thread(target=self._scan_worker, args=(folder,), daemon=True).start()

    def _scan_worker(self, folder: Path) -> None:
        try:
            self.events.put(scan_library(folder))
        except Exception as error:
            self.events.put(error)

    def _populate(self, result: ScanResult) -> None:
        for bar in self.progress_bars.values():
            bar.destroy()
        self.progress_bars.clear()
        self.entries.clear()
        self.tree.delete(*self.tree.get_children())
        root_iid = self.tree.insert("", "end", text=f"All songs ({result.root})", open=True)
        packs: dict[str, str] = {}
        for entry in result.songs:
            pack_iid = packs.setdefault(
                entry.pack, self.tree.insert(root_iid, "end", text=entry.pack, open=True)
            )
            iid = self.tree.insert(
                pack_iid,
                "end",
                text=entry.folder.name,
                values=("yes" if entry.autoconverted else "no", "", entry.action),
            )
            bar = ttk.Progressbar(self.tree, maximum=100, mode="determinate", value=entry.progress)
            self.entries[iid] = entry
            self.progress_bars[iid] = bar
        self.root.after_idle(self._place_progress_bars)
        self.status.set(f"Dry run complete: {len(result.songs)} song folders found.")
        self._set_enabled(True)

    def _select_song(self, _event: object) -> None:
        selection = self.tree.selection()
        self.selected_iid = selection[0] if selection and selection[0] in self.entries else None
        self.action.set(self.entries[self.selected_iid].action if self.selected_iid else "none")

    def _set_action(self) -> None:
        if self.selected_iid is None:
            return
        entry = self.entries[self.selected_iid]
        entry.action = self.action.get()  # type: ignore[assignment]
        self.tree.set(self.selected_iid, "action", entry.action)

    def _refresh_entry(self, entry: SongEntry) -> None:
        for iid, candidate in self.entries.items():
            if candidate is entry:
                self.progress_bars[iid].configure(value=entry.progress)
                self.tree.set(iid, "autoconverted", "yes" if entry.autoconverted else "no")
                return

    def run_selected(self) -> None:
        selected = [entry for entry in self.entries.values() if entry.action != "none"]
        if not selected:
            messagebox.showinfo(
                "Nothing selected", "Choose Convert or Remove conversion for a song."
            )
            return
        self._set_enabled(False)
        self.total_progress.configure(value=0, maximum=operation_count(selected))
        threading.Thread(target=self._run_worker, args=(selected,), daemon=True).start()

    def _run_worker(self, selected: list[SongEntry]) -> None:
        try:
            for event in execute(selected):
                self.events.put(event)
            self.events.put("finished")
        except Exception as error:
            self.events.put(error)

    def _poll(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if isinstance(event, ScanResult):
                    self._populate(event)
                elif isinstance(event, Progress):
                    self.total_progress.configure(value=event.completed)
                    entry = next(
                        entry for entry in self.entries.values() if entry.folder == event.folder
                    )
                    self._refresh_entry(entry)
                    self.status.set(event.message)
                elif event == "finished":
                    self.status.set("Run complete.")
                    self._set_enabled(True)
                elif isinstance(event, Exception):
                    self.status.set(str(event))
                    self._set_enabled(True)
                    messagebox.showerror("Operation failed", str(event))
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for frame in self.root.winfo_children():
            for widget in frame.winfo_children():
                if isinstance(widget, (ttk.Button, ttk.Radiobutton)):
                    widget.configure(state=state)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path)
    args = parser.parse_args()
    root = tk.Tk()
    App(root, args.folder)
    root.mainloop()
