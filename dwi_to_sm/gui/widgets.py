"""Reusable Tkinter widgets for the song-library GUI."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from typing import ClassVar

from .models import Action, BarCounts, ErrorEntry, ScanResult, TreeNode
from .operations import set_action


class Tooltip:
    """Small popup showing text from ``text_provider`` while hovering ``widget``.

    ``text_provider`` receives the triggering mouse event so bars can vary the
    message depending on which segment is under the cursor.
    """

    def __init__(self, widget: tk.Widget, text_provider: Callable[[tk.Event], str]):
        self.widget = widget
        self.text_provider = text_provider
        self.tip: tk.Toplevel | None = None
        self.label: ttk.Label | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Motion>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event: tk.Event) -> None:
        text = self.text_provider(event)
        if not text:
            self._hide(event)
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        if self.tip is None:
            self.tip = tk.Toplevel(self.widget)
            self.tip.wm_overrideredirect(True)
            self.label = ttk.Label(
                self.tip,
                background="#ffffe0",
                relief="solid",
                borderwidth=1,
                padding=4,
                justify="left",
            )
            self.label.pack()
        self.tip.wm_geometry(f"+{x}+{y}")
        self.label.configure(text=text)

    def _hide(self, _event: tk.Event) -> None:
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None
            self.label = None


class TriStateButton(ttk.Button):
    """Button cycling through None, Convert, and Remove conversion."""

    LABELS: ClassVar[dict[Action, str]] = {
        "convert": "Convert",
        "remove": "Remove conversion",
        "none": "None",
    }
    STYLES: ClassVar[dict[Action, str]] = {
        "convert": "ActionConvert.TButton",
        "remove": "ActionRemove.TButton",
        "none": "ActionNone.TButton",
    }

    def __init__(self, master: tk.Misc, node: TreeNode, changed: Callable[[], None]):
        self.node = node
        self.changed = changed
        super().__init__(
            master,
            text=self.LABELS[node.action],
            style=self.STYLES[node.action],
            command=self.cycle,
        )

    def cycle(self) -> None:
        actions: tuple[Action, ...] = ("none", "convert", "remove")
        set_action(self.node, actions[(actions.index(self.node.action) + 1) % len(actions)])
        self.changed()

    def refresh(self) -> None:
        self.configure(text=self.LABELS[self.node.action], style=self.STYLES[self.node.action])


class MultiSegmentBar(tk.Canvas):
    """Canvas bar showing not-done/no-op/pass/fail counts as proportional segments.

    Drawn on a plain Canvas instead of a ttk.Progressbar because Windows' default
    ttk theme ignores style colors for progress bars.
    """

    NOT_DONE = "#e0e0e0"
    PASS = "#34a853"
    NO_OP = "#a5d6a7"
    FAIL = "#d93025"

    def __init__(self, master: tk.Misc, counts_provider: Callable[[], BarCounts]):
        self.counts_provider = counts_provider
        super().__init__(master, height=16, highlightthickness=0, background=self.NOT_DONE)
        self.bind("<Configure>", lambda _event: self._draw())
        self._draw()

    def _draw(self) -> None:
        self.delete("segment")
        counts = self.counts_provider()
        width, height = self.winfo_width(), self.winfo_height()
        if width <= 1 or counts.total <= 0:
            return
        x = 0
        for count, color in (
            (counts.passed, self.PASS),
            (counts.no_op, self.NO_OP),
            (counts.failed, self.FAIL),
        ):
            if count <= 0:
                continue
            segment_width = round(width * count / counts.total)
            if segment_width > 0:
                self.create_rectangle(
                    x, 0, x + segment_width, height, fill=color, width=0, tags="segment"
                )
                x += segment_width

    def refresh(self) -> None:
        self._draw()


def segment_tooltip(counts: BarCounts, x: int, width: int) -> str:
    """Label for whichever colored segment covers pixel ``x`` of a ``width``-wide bar."""
    if counts.total <= 0 or width <= 0:
        return ""
    offset = 0
    for count, label in (
        (counts.passed, "Converted"),
        (counts.no_op, "No conversion required"),
        (counts.failed, "Conversion attempt failed"),
    ):
        segment_width = round(width * count / counts.total)
        if segment_width and offset <= x < offset + segment_width:
            return label
        offset += segment_width
    return "Not converted yet"


def summary_tooltip(counts: BarCounts) -> str:
    """Breakdown of a folder/root bar's counts, for songs that share it."""
    return (
        f"Converted: {counts.passed}\n"
        f"No conversion required: {counts.no_op}\n"
        f"Failed: {counts.failed}"
    )


class ConversionProgress(MultiSegmentBar):
    """MultiSegmentBar bound to a TreeNode's conversion counts."""

    def __init__(self, master: tk.Misc, node: TreeNode):
        self.node = node
        super().__init__(master, counts_provider=lambda: node.counts)
        Tooltip(self, self._tooltip_text)

    def _tooltip_text(self, event: tk.Event) -> str:
        if self.node.entry is not None:
            return segment_tooltip(self.node.counts, event.x, self.winfo_width())
        return summary_tooltip(self.node.counts)


class SongTree(ttk.Frame):
    """Treeview that owns song nodes, action buttons, and conversion bars."""

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.nodes: dict[str, TreeNode] = {}
        self.progress_bars: dict[str, ConversionProgress] = {}
        self.action_buttons: dict[str, TriStateButton] = {}
        self.node_iids: dict[int, str] = {}
        self.song_nodes: dict[Path, TreeNode] = {}
        self.root_node: TreeNode | None = None
        self.folders_expanded = False
        self._build()

    def _build(self) -> None:
        self.tree = ttk.Treeview(
            self,
            columns=("converted", "action"),
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="All songs / pack / song")
        self.tree.heading("converted", text="Converted")
        self.tree.heading("action", text="Action")
        style = ttk.Style(self)
        style.configure("Treeview", rowheight=28)
        self._configure_action_style(style, "ActionConvert.TButton", "#34a853", "#2d9248")
        self._configure_action_style(style, "ActionRemove.TButton", "#d93025", "#bb2419")
        self._configure_action_style(style, "ActionNone.TButton", "#80868b", "#6f7478")
        style.configure("ActionFlash.TButton", background="#fbbc04", foreground="black")
        self.tree.column("#0", width=500)
        self.tree.column("converted", width=120, anchor="center")
        self.tree.column("action", width=150, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._scroll)
        self.scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=self._set_scrollbar)
        self.tree.bind("<Configure>", lambda _event: self._place_widgets())
        self.tree.bind("<Button-1>", self._action_cell_click)

    def populate(self, result: ScanResult) -> None:
        for widget in (*self.progress_bars.values(), *self.action_buttons.values()):
            widget.destroy()
        self.nodes.clear()
        self.progress_bars.clear()
        self.action_buttons.clear()
        self.node_iids.clear()
        self.song_nodes.clear()
        self.root_node = result.tree
        self.folders_expanded = False
        self.tree.delete(*self.tree.get_children())
        if self.root_node is not None:
            set_action(self.root_node, "convert")
            self._insert_node("", self.root_node, None)
        self.after_idle(self._place_widgets)

    def _insert_node(self, parent: str, node: TreeNode, parent_node: TreeNode | None) -> None:
        iid = self.tree.insert(
            parent,
            "end",
            text=node.name,
            values=("", TriStateButton.LABELS[node.action]),
            open=node.kind == "all",
        )
        self.nodes[iid] = node
        self.node_iids[id(node)] = iid
        if node.entry is not None:
            self.song_nodes[node.entry.folder] = node
        self.progress_bars[iid] = ConversionProgress(self.tree, node)
        self.action_buttons[iid] = TriStateButton(self.tree, node, self.refresh_actions)
        for child in node.children:
            self._insert_node(iid, child, node)

    def _place_widgets(self) -> None:
        for iid, widget in self.progress_bars.items():
            self._place_widget(iid, widget, "#1")
        for iid, widget in self.action_buttons.items():
            self._place_widget(iid, widget, "#2")

    def _place_widget(self, iid: str, widget: ttk.Widget, column: str) -> None:
        box = self.tree.bbox(iid, column)
        if not box:
            widget.place_forget()
            return
        x, y, width, height = box
        widget.place(x=x + 3, y=y + 3, width=max(10, width - 6), height=max(10, height - 6))

    def _scroll(self, *args: str) -> None:
        self.tree.yview(*args)
        self._place_widgets()

    def _set_scrollbar(self, first: str, last: str) -> None:
        self.scrollbar.set(first, last)
        self._place_widgets()

    def _action_cell_click(self, event: tk.Event) -> str | None:
        if self.tree.identify_column(event.x) != "#2":
            return None
        iid = self.tree.identify_row(event.y)
        button = self.action_buttons.get(iid)
        if button is not None:
            button.invoke()
            return "break"
        return None

    def refresh_actions(self) -> None:
        for iid, node in self.nodes.items():
            self.tree.set(iid, "action", TriStateButton.LABELS[node.action])
            self.action_buttons[iid].refresh()
            self.progress_bars[iid].refresh()

    def flash_root_action(self, remaining: int = 11) -> None:
        if self.root_node is None or remaining <= 0:
            return
        iid = self.node_iids[id(self.root_node)]
        self.action_buttons[iid].configure(
            style="ActionFlash.TButton" if remaining % 2 else "ActionConvert.TButton"
        )
        self.after(120, self.flash_root_action, remaining - 1)

    def refresh_progress(self, folder: Path) -> None:
        node = self.song_nodes[folder]
        current: TreeNode | None = node
        while current is not None:
            self.progress_bars[self.node_iids[id(current)]].refresh()
            current = self._parent(current)

    def _parent(self, node: TreeNode) -> TreeNode | None:
        iid = self.node_iids[id(node)]
        parent_iid = self.tree.parent(iid)
        return self.nodes.get(parent_iid)

    def selected_entries(self) -> list:
        return [
            node.entry
            for node in self.nodes.values()
            if node.kind == "song" and node.entry is not None and node.action != "none"
        ]

    def toggle_all_folders(self) -> None:
        self.folders_expanded = not self.folders_expanded
        if self.root_node is None:
            return
        root_iid = self.node_iids[id(self.root_node)]
        for child_iid in self.tree.get_children(root_iid):
            self._set_subtree_open(child_iid, self.folders_expanded)

    def _set_subtree_open(self, iid: str, open_state: bool) -> None:
        self.tree.item(iid, open=open_state)
        for child_iid in self.tree.get_children(iid):
            if self.nodes[child_iid].children:
                self._set_subtree_open(child_iid, open_state)

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self.action_buttons.values():
            button.configure(state=state)

    @staticmethod
    def _configure_action_style(
        style: ttk.Style, name: str, background: str, active_background: str
    ) -> None:
        style.configure(name, background=background, foreground="black")
        style.map(
            name,
            background=[
                ("pressed", active_background),
                ("active", active_background),
                ("disabled", "#c4c7c5"),
            ],
            foreground=[("disabled", "#6b6f6d"), ("!disabled", "black")],
        )


class ErrorPane(ttk.Frame):
    """List of failed songs; each row is the error message plus a '?' button.

    Hidden by default and only packed into ``master`` while there are errors.
    """

    def __init__(self, master: tk.Misc, on_open_folder: Callable[[Path], None]):
        super().__init__(master, padding=8)
        self.on_open_folder = on_open_folder
        self.entries: list[ErrorEntry] = []
        self.rows: dict[Path, ttk.Frame] = {}
        ttk.Label(self, text="Errors").pack(anchor="w")
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(canvas_frame, height=140, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.list_frame = ttk.Frame(self.canvas)
        self.list_window = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind(
            "<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfigure(self.list_window, width=e.width)
        )

    def clear(self) -> None:
        for row in self.rows.values():
            row.destroy()
        self.rows.clear()
        self.entries.clear()
        self.pack_forget()

    def add_error(self, folder: Path, message: str) -> None:
        if folder in self.rows:
            self.rows[folder].destroy()
            self.entries = [entry for entry in self.entries if entry.folder != folder]
        self.entries.append(ErrorEntry(folder, message))
        row = ttk.Frame(self.list_frame)
        row.pack(fill="x", pady=1)
        ttk.Label(row, text=f"{folder.name}: {message}", anchor="w").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(row, text="?", width=2, command=lambda: self.on_open_folder(folder)).pack(
            side="right"
        )
        self.rows[folder] = row
        if not self.winfo_ismapped():
            self.pack(fill="both", padx=8, pady=(0, 8))

