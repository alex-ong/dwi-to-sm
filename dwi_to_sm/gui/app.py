"""Tkinter application for asynchronous song-library conversion."""

from __future__ import annotations

import argparse
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .models import Action, Progress, ScanResult, TreeNode
from .operations import execute, operation_count, scan_library, set_action


class App:
    def __init__(self, root: tk.Tk, initial_folder: Path | None = None):
        self.root = root
        self.root.title("DWI to SM")
        self.root.geometry("980x650")
        self.events: queue.Queue[object] = queue.Queue()
        self.nodes: dict[str, TreeNode] = {}
        self.status_bars: dict[str, ttk.Progressbar] = {}
        self.node_iids: dict[int, str] = {}
        self.tree_root: TreeNode | None = None
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
        self.choose_button = ttk.Button(toolbar, text="Choose folder", command=self.choose_folder)
        self.choose_button.pack(side="left")
        self.run_button = ttk.Button(toolbar, text="Run", command=self.run_selected)
        self.run_button.pack(side="left", padx=8)
        ttk.Label(toolbar, textvariable=self.status).pack(side="left", padx=8)

        body = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            body,
            columns=("autoconverted", "action"),
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="All songs / pack / song")
        self.tree.heading("autoconverted", text="Converted")
        self.tree.heading("action", text="Action")
        style = ttk.Style(self.root)
        style.configure("ConvertedGreen.Horizontal.TProgressbar", background="#34a853")
        style.configure("ConvertedRed.Horizontal.TProgressbar", background="#d93025")
        self.tree.column("#0", width=500)
        self.tree.column("autoconverted", width=120, anchor="center")
        self.tree.column("action", width=150, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        self.scrollbar = ttk.Scrollbar(body, orient="vertical", command=self._scroll_tree)
        self.scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=self._set_scrollbar)
        self.tree.bind("<Configure>", lambda _event: self._place_widgets())
        self.tree.bind("<Button-1>", self._cycle_action)

        self.total_progress.pack(fill="x", padx=8)
        ttk.Label(self.root, textvariable=self.status, anchor="w").pack(
            fill="x", padx=8, pady=8
        )

    def _scroll_tree(self, *args: str) -> None:
        self.tree.yview(*args)
        self._place_widgets()

    def _set_scrollbar(self, first: str, last: str) -> None:
        self.scrollbar.set(first, last)
        self._place_widgets()

    def _place_widgets(self) -> None:
        for iid, widget in self.status_bars.items():
            column = "#1"
            box = self.tree.bbox(iid, column)
            if not box:
                widget.place_forget()
                continue
            x, y, width, height = box
            widget.place(x=x + 3, y=y + 2, width=max(10, width - 6), height=max(10, height - 4))

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
        for widget in (
            *self.status_bars.values(),
        ):
            widget.destroy()
        self.status_bars.clear()
        self.nodes.clear()
        self.node_iids.clear()
        self.tree_root = result.tree
        self.tree.delete(*self.tree.get_children())
        if self.tree_root is not None:
            self._insert_node("", self.tree_root)
        self.root.after_idle(self._place_widgets)
        self.status.set(f"Dry run complete: {len(result.songs)} song folders found.")
        self._set_enabled(True)

    def _insert_node(self, parent: str, node: TreeNode) -> None:
        iid = self.tree.insert(
            parent,
            "end",
            text=node.name,
            values=("", self._action_label(node.action)),
            open=True,
        )
        self.nodes[iid] = node
        self.node_iids[id(node)] = iid
        self.status_bars[iid] = ttk.Progressbar(
            self.tree,
            maximum=100,
            mode="determinate",
            value=node.progress,
            style=self._conversion_style(node),
        )
        for child in node.children:
            self._insert_node(iid, child)

    @staticmethod
    def _action_label(action: Action) -> str:
        return {"convert": "Convert", "remove": "Remove conversion", "none": "None"}[action]

    def _cycle_action(self, event: tk.Event) -> str | None:
        if self.tree.identify_column(event.x) != "#2":
            return None
        iid = self.tree.identify_row(event.y)
        node = self.nodes.get(iid)
        if node is None:
            return None
        actions: tuple[Action, ...] = ("none", "convert", "remove")
        set_action(node, actions[(actions.index(node.action) + 1) % len(actions)])
        self._refresh_actions()
        return "break"

    def _refresh_actions(self) -> None:
        for iid, node in self.nodes.items():
            self.tree.set(iid, "action", self._action_label(node.action))

    @staticmethod
    def _conversion_style(node: TreeNode) -> str:
        return (
            "ConvertedGreen.Horizontal.TProgressbar"
            if node.progress == 100
            else "ConvertedRed.Horizontal.TProgressbar"
        )

    def _refresh_progress(self, node: TreeNode) -> None:
        iid = self.node_iids[id(node)]
        self.status_bars[iid].configure(
            style=self._conversion_style(node), value=node.progress
        )
        for child in node.children:
            self._refresh_progress(child)

    def run_selected(self) -> None:
        selected = [
            node.entry
            for node in self.nodes.values()
            if node.kind == "song" and node.entry and node.action != "none"
        ]
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
                    if self.tree_root is not None:
                        self._refresh_progress(self.tree_root)
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
        self.choose_button.configure(state=state)
        self.run_button.configure(state=state)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path)
    args = parser.parse_args()
    root = tk.Tk()
    App(root, args.folder)
    root.mainloop()
