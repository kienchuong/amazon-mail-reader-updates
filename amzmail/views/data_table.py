
from __future__ import annotations

from tkinter import font as tkfont
from typing import Any, Callable, Iterable

import customtkinter as ctk
from tksheet import Sheet, num2alpha


ELLIPSIS = "…"


# tksheet's stock dark theme uses a pure black table canvas. Keep the grid on
# the same charcoal surface as the CustomTkinter shell instead.
FLUENT_DARK_TABLE_OPTIONS = {
    "frame_bg": "#202326",
    "table_bg": "#17191c",
    # Keep the body clean: separators stay in the header where columns are resized.
    "table_grid_fg": "#17191c",
    "table_fg": "#eef1f5",
    "table_editor_bg": "#17191c",
    "table_editor_fg": "#eef1f5",
    "header_bg": "#202326",
    # tksheet uses one-pixel canvas lines. Lower contrast makes them read like
    # the subtle dividers in Windows Explorer instead of a heavy spreadsheet.
    "header_border_fg": "#34383d",
    "header_grid_fg": "#34383d",
    "header_fg": "#e7ebf0",
    "header_editor_bg": "#202326",
    "index_bg": "#202326",
    "index_border_fg": "#34383d",
    "top_left_bg": "#202326",
    "outline_color": "#30343a",
    "table_selected_cells_bg": "#263f59",
    "table_selected_rows_bg": "#263f59",
    "table_selected_columns_bg": "#263f59",
    "vertical_scroll_background": "#2a2d31",
    "horizontal_scroll_background": "#2a2d31",
    "vertical_scroll_troughcolor": "#202326",
    "horizontal_scroll_troughcolor": "#202326",
    "vertical_scroll_bordercolor": "#202326",
    "horizontal_scroll_bordercolor": "#202326",
    "vertical_scroll_lightcolor": "#202326",
    "horizontal_scroll_lightcolor": "#202326",
    "vertical_scroll_darkcolor": "#202326",
    "horizontal_scroll_darkcolor": "#202326",
    "vertical_scroll_not_active_bg": "#4b5159",
    "horizontal_scroll_not_active_bg": "#4b5159",
}


def shorten(value: Any, limit: int = 25) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + ELLIPSIS


class FluentDataTable(ctk.CTkFrame):
    """Read-only tksheet wrapper with the small Treeview API used by the app."""

    def __init__(
        self,
        parent,
        columns: Iterable[str],
        headings: dict[str, str],
        widths: dict[str, int],
        *,
        center_columns: Iterable[str] = (),
        truncate_columns: Iterable[str] = (),
        status_columns: Iterable[str] = (),
    ) -> None:
        super().__init__(parent, corner_radius=10, fg_color=("#ffffff", "#202326"))
        self.columns = tuple(columns)
        self.headings = headings
        self.default_widths = dict(widths)
        self.center_columns = set(center_columns)
        self.truncate_columns = set(truncate_columns)
        self.status_columns = set(status_columns)
        self._callbacks: list[Callable] = []
        self._full_values: dict[str, list[str]] = {}

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        tools = ctk.CTkFrame(self, height=34, corner_radius=8, fg_color=("#f4f6f8", "#202326"))
        tools.grid(row=0, column=0, sticky="ew", padx=8, pady=(7, 0))
        ctk.CTkLabel(
            tools,
            text="Kéo vạch cột để đổi độ rộng • nhấp đúp để tự căn",
            text_color=("#667085", "#9aa4b2"),
            font=ctk.CTkFont(family="Segoe UI Variable", size=11),
        ).pack(side="left")
        ctk.CTkButton(
            tools,
            text="Đặt lại cột",
            width=96,
            height=28,
            corner_radius=5,
            fg_color=("#e7edf4", "#30353b"),
            hover_color=("#d8e2ed", "#3b424a"),
            text_color=("#202124", "#f4f6f8"),
            font=ctk.CTkFont(family="Segoe UI Variable", size=12),
            command=self.reset_columns,
        ).pack(side="right")

        self.sheet = Sheet(
            self,
            data=[],
            headers=[headings[column] for column in self.columns],
            treeview=True,
            theme="dark" if ctk.get_appearance_mode() == "Dark" else "light blue",
            show_row_index=False,
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            table_wrap="",
            header_wrap="",
            header_align="center",
            allow_cell_overflow=False,
            tooltips=True,
            font=("Segoe UI Variable", 11, "normal"),
            header_font=("Segoe UI Variable", 11, "bold"),
            default_row_height=34,
            default_header_height=36,
            scrollbar_theme_inheritance="clam",
            scrollbar_show_arrows=False,
        )
        self.sheet.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))
        self.sheet.hide("row_index")
        self.sheet.enable_bindings(
            "single_select",
            "row_select",
            "arrowkeys",
            "copy",
            "column_width_resize",
            "double_click_column_resize",
        )
        self.sheet.extra_bindings("all_select_events", self._selection_changed)
        self._configure_sheet_theme()
        self._apply_alignment()
        self.reset_columns()

    def bind(self, sequence=None, func=None, add=None):
        if sequence == "<<TreeviewSelect>>" and func is not None:
            self._callbacks.append(func)
            return None
        return super().bind(sequence, func, add)

    def _selection_changed(self, _event=None) -> None:
        for callback in tuple(self._callbacks):
            callback(None)

    def selection(self) -> list[str]:
        return list(self.sheet.selection(cells=True))

    def selection_set(self, *items: str) -> None:
        if items:
            self.sheet.selection_set(*items, run_binding=False)

    def focus(self, item: str | None = None):
        if item is not None:
            self.selection_set(item)
        return item

    def get_children(self) -> list[str]:
        return list(self.sheet.get_children())

    def delete(self, *items: str) -> None:
        if items:
            self.sheet.del_items(*items, undo=False)
        self._full_values.clear()

    def insert(self, parent="", index="end", iid=None, values=()) -> str:
        item_id = str(iid) if iid is not None else None
        full = ["" if value is None else str(value) for value in values]
        display = [
            shorten(value) if column in self.truncate_columns else value
            for column, value in zip(self.columns, full)
        ]
        item_id = self.sheet.insert(
            parent=parent,
            index=index,
            iid=item_id,
            text="",
            values=display,
            undo=False,
        )
        self._full_values[item_id] = full
        row = self.sheet.itemrow(item_id)
        self._decorate_row(row, full, display)
        return item_id

    def _decorate_row(self, row: int, full: list[str], display: list[str]) -> None:
        for column_index, column in enumerate(self.columns):
            if column in self.truncate_columns and full[column_index] != display[column_index]:
                self.sheet.note(row, column_index, note=full[column_index], readonly=True)
            if column in self.status_columns:
                colors = self._status_colors(full[column_index])
                if colors:
                    self.sheet.highlight((row, column_index), bg=colors[0], fg=colors[1], redraw=False)

    @staticmethod
    def _status_colors(value: str) -> tuple[str, str] | None:
        dark = ctk.get_appearance_mode() == "Dark"
        key = value.strip().casefold()
        palette = {
            "payment": (("#dff3e4", "#175c2c"), ("#183d27", "#8fe3a6")),
            "security": (("#fde7e9", "#9c1c28"), ("#4a2328", "#ff9aa5")),
            "high": (("#fde7e9", "#9c1c28"), ("#4a2328", "#ff9aa5")),
            "amazon": (("#e3effd", "#175c9c"), ("#193753", "#8ec5ff")),
            "amazon account": (("#e3effd", "#175c9c"), ("#193753", "#8ec5ff")),
            "normal": (("#edf0f3", "#4b5563"), ("#343940", "#d5dae0")),
        }
        pair = palette.get(key)
        return pair[1 if dark else 0] if pair else None

    def _apply_alignment(self) -> None:
        for index, column in enumerate(self.columns):
            alignment = "center" if column in self.center_columns else "w"
            self.sheet.align_columns(columns=index, align=alignment)
            header = self.sheet.span(num2alpha(index), header=True, table=False)
            self.sheet.align(header, align=alignment, redraw=False)

    def reset_columns(self) -> None:
        for index, column in enumerate(self.columns):
            self.sheet.column_width(index, width=self.default_widths[column], redraw=False)
        self.sheet.redraw()

    def fit_columns(self) -> None:
        font = tkfont.Font(family="Segoe UI Variable", size=11)
        rows = list(self._full_values.values())
        for index, column in enumerate(self.columns):
            texts = [self.headings[column]]
            for values in rows:
                value = values[index]
                texts.append(shorten(value) if column in self.truncate_columns else value)
            measured = max((font.measure(text) for text in texts), default=60) + 30
            maximum = font.measure("M" * 25) + 30 if column in self.truncate_columns else 360
            width = max(64, min(maximum, measured))
            self.sheet.column_width(index, width=width, redraw=False)
        self.sheet.redraw()

    def _configure_sheet_theme(self) -> None:
        dark = ctk.get_appearance_mode() == "Dark"
        self.sheet.change_theme("dark" if dark else "light blue", redraw=False)
        if dark:
            self.sheet.set_options(redraw=False, **FLUENT_DARK_TABLE_OPTIONS)

    def apply_appearance(self) -> None:
        self._configure_sheet_theme()
        for iid, values in self._full_values.items():
            row = self.sheet.itemrow(iid)
            self._decorate_row(row, values, [shorten(v) for v in values])
        self.sheet.redraw()


class FluentSplitPane(ctk.CTkFrame):
    def __init__(self, parent, ratio: float = 0.72) -> None:
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self.ratio = ratio
        self.left = ctk.CTkFrame(self, corner_radius=6)
        self.right = ctk.CTkFrame(self, corner_radius=6)
        self.divider = ctk.CTkFrame(self, width=9, corner_radius=0, fg_color="transparent")
        self.grip = ctk.CTkLabel(
            self.divider,
            text="⋮",
            width=7,
            text_color=("#7a8491", "#98a2ad"),
            font=ctk.CTkFont(family="Segoe UI Variable", size=18),
        )
        self.left.grid(row=0, column=0, sticky="nsew")
        self.divider.grid(row=0, column=1, sticky="ns")
        self.right.grid(row=0, column=2, sticky="nsew")
        self.grip.place(relx=0.5, rely=0.5, anchor="center")
        self.grid_rowconfigure(0, weight=1)
        left_weight = max(1, round(ratio * 100))
        self.grid_columnconfigure(0, weight=left_weight, minsize=500)
        self.grid_columnconfigure(1, weight=0, minsize=9)
        self.grid_columnconfigure(2, weight=100 - left_weight, minsize=280)
        for widget in (self.divider, self.grip):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)

    def _start_drag(self, event) -> None:
        del event

    def _drag(self, event) -> None:
        width = max(1, self.winfo_width() - 9)
        local_x = self.winfo_pointerx() - self.winfo_rootx()
        left = max(500, min(width - 280, local_x))
        self.grid_columnconfigure(0, weight=left)
        self.grid_columnconfigure(2, weight=max(280, width - left))

