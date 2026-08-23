"""Tkinter application for asynchronous song-library conversion."""

from __future__ import annotations

import argparse
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .models import Progress, ScanResult
from .operations import execute, operation_count, scan_library
from .widgets import SongTree


class App:
    def __init__(self, root: tk.Tk, initial_folder: Path | None = None):
        self.root = root
        self.root.title("DWI to SM")
        self.root.geometry("980x650")
        self.events: queue.Queue[object] = queue.Queue()
        self.status = tk.StringVar(value="Select a Songs folder to begin.")
        self._build()
        self.root.after(100, self._poll)
        if initial_folder is not None:
            self._choose(initial_folder)
        else:
            self.root.after(150, self.choose_folder)

    def _build(self) -> None:
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill="x")
        self.choose_button = ttk.Button(
            toolbar, text="Choose Songs folder", command=self.choose_folder
        )
        self.choose_button.pack(side="left")
        self.toggle_folders_button = ttk.Button(
            toolbar, text="Expand all folders", command=self._toggle_all_folders
        )
        self.toggle_folders_button.pack(side="left", padx=8)
        self.run_button = ttk.Button(toolbar, text="Run", command=self.run_selected)
        self.run_button.configure(state="disabled")
        self.run_button.pack(side="left")
        ttk.Label(toolbar, textvariable=self.status).pack(side="left", padx=8)

        self.song_tree = SongTree(self.root)
        self.song_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.total_progress = ttk.Progressbar(self.root, mode="determinate")
        self.total_progress.pack(fill="x", padx=8)
        ttk.Label(self.root, textvariable=self.status, anchor="w").pack(
            fill="x", padx=8, pady=8
        )

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
        self.song_tree.populate(result)
        self.status.set(f"Dry run complete: {len(result.songs)} song folders found.")
        self._set_enabled(True)
        self._update_run_state()
        if self.song_tree.root_node is not None:
            self.root.after(250, self.song_tree.flash_root_action)

    def _toggle_all_folders(self) -> None:
        self.song_tree.toggle_all_folders()
        self.toggle_folders_button.configure(
            text=(
                "Close all folders"
                if self.song_tree.folders_expanded
                else "Expand all folders"
            )
        )

    def run_selected(self) -> None:
        selected = self.song_tree.selected_entries()
        if not selected:
            messagebox.showinfo("Nothing selected", "Choose an action in the tree first.")
            return
        self._set_enabled(False)
        self.total_progress.configure(value=0, maximum=operation_count(selected))
        threading.Thread(target=self._run_worker, args=(selected,), daemon=True).start()

    def _run_worker(self, selected: list) -> None:
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
                    self.song_tree.refresh_progress(event.folder)
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

    def _update_run_state(self) -> None:
        if self.choose_button.instate(["disabled"]):
            return
        self.run_button.configure(
            state="normal" if self.song_tree.selected_entries() else "disabled"
        )

    def _set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.choose_button.configure(state=state)
        self.run_button.configure(state=state)
        self.toggle_folders_button.configure(state=state)
        self.song_tree.set_enabled(enabled)
        if enabled:
            self._update_run_state()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path)
    args = parser.parse_args()
    root = tk.Tk()
    App(root, args.folder)
    root.mainloop()
