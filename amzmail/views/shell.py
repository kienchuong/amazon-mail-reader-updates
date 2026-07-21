from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from amzmail import APP_VERSION


class ShellViewMixin:
    def _build_style(self) -> None:
        self.tree_style = ttk.Style(self)
        if "clam" in self.tree_style.theme_names():
            self.tree_style.theme_use("clam")
        self._last_appearance = ""
        self._apply_tree_style(force=True)

    def _build_ui(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.status_var = tk.StringVar(value="Sẵn sàng. App chỉ đọc mail, không gửi/xóa/sửa email.")
        self.page_title_var = tk.StringVar(value="Inbox")

        self.sidebar = ctk.CTkFrame(self, width=210, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(6, weight=1)
        ctk.CTkLabel(
            self.sidebar, text="Amazon Mail\nReader", justify="left", anchor="w",
            font=ctk.CTkFont(size=21, weight="bold"),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(22, 24))

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for row, (key, label) in enumerate(
            [("inbox", "Inbox"), ("payments", "Payment"), ("accounts", "Accounts"), ("settings", "Cài đặt")],
            start=1,
        ):
            button = ctk.CTkButton(
                self.sidebar, text=label, height=40, anchor="w", corner_radius=5,
                fg_color="transparent", command=lambda page=key: self.show_page(page),
            )
            button.grid(row=row, column=0, sticky="ew", padx=10, pady=3)
            self.nav_buttons[key] = button

        ctk.CTkLabel(
            self.sidebar, text=f"Phiên bản {APP_VERSION}", anchor="w", font=ctk.CTkFont(size=12)
        ).grid(row=7, column=0, sticky="ew", padx=18, pady=(8, 3))
        ctk.CTkLabel(
            self.sidebar, text="Chỉ đọc email", anchor="w", text_color=("#52606d", "#aab2bd"),
            font=ctk.CTkFont(size=12),
        ).grid(row=8, column=0, sticky="ew", padx=18, pady=(0, 18))

        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color=("#f4f6f8", "#17191c"))
        self.main_area.grid(row=0, column=1, sticky="nsew")
        self.main_area.grid_rowconfigure(1, weight=1)
        self.main_area.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.main_area, height=64, corner_radius=0, fg_color=("#ffffff", "#202226"))
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        ctk.CTkLabel(
            header, textvariable=self.page_title_var, font=ctk.CTkFont(size=22, weight="bold")
        ).pack(side="left", padx=22, pady=16)

        self.content = ctk.CTkFrame(self.main_area, corner_radius=0, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.pages: dict[str, ctk.CTkFrame] = {}
        for key in ("inbox", "payments", "accounts", "settings"):
            page = ctk.CTkFrame(self.content, corner_radius=0, fg_color="transparent")
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = page

        self.inbox_tab = self.pages["inbox"]
        self.payments_tab = self.pages["payments"]
        self.accounts_tab = self.pages["accounts"]
        self.settings_tab = self.pages["settings"]
        self._build_inbox_view(self.inbox_tab)
        self._build_payments_view(self.payments_tab)
        self._build_accounts_view(self.accounts_tab)
        self._build_settings_view(self.settings_tab)

        status = ctk.CTkFrame(self.main_area, height=34, corner_radius=0, fg_color=("#ffffff", "#202226"))
        status.grid(row=2, column=0, sticky="ew")
        status.grid_propagate(False)
        ctk.CTkLabel(status, textvariable=self.status_var, anchor="w", font=ctk.CTkFont(size=12)).pack(
            fill="x", padx=18, pady=7
        )
        self.show_page("inbox")
        self.after(800, self._sync_appearance)

    def _create_tree(self, parent, columns, headings, widths, selectmode="browse"):
        tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode=selectmode, style="App.Treeview")
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=widths[column], minwidth=55, anchor="w")
        scrollbar = ctk.CTkScrollbar(parent, orientation="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y", padx=(0, 5), pady=6)
        tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        return tree

    def show_page(self, page: str) -> None:
        titles = {"inbox": "Inbox", "payments": "Payment", "accounts": "Accounts", "settings": "Cài đặt"}
        self.pages[page].tkraise()
        self.page_title_var.set(titles[page])
        for key, button in self.nav_buttons.items():
            button.configure(fg_color=("#dce8f5", "#233a52") if key == page else "transparent")

    def _apply_tree_style(self, force: bool = False) -> None:
        appearance = ctk.get_appearance_mode()
        if not force and appearance == self._last_appearance:
            return
        self._last_appearance = appearance
        if appearance == "Dark":
            background, foreground, heading, selected, border = "#24272b", "#f1f3f5", "#30343a", "#1f6aa5", "#3a3e44"
        else:
            background, foreground, heading, selected, border = "#ffffff", "#17202a", "#e9edf2", "#2f75b5", "#d6dce3"
        self.tree_style.configure(
            "App.Treeview", background=background, fieldbackground=background, foreground=foreground,
            bordercolor=border, lightcolor=border, darkcolor=border, rowheight=30,
            font=("Segoe UI", 10), borderwidth=0,
        )
        self.tree_style.configure(
            "App.Treeview.Heading", background=heading, foreground=foreground,
            relief="flat", font=("Segoe UI", 10, "bold"),
        )
        self.tree_style.map("App.Treeview", background=[("selected", selected)], foreground=[("selected", "#ffffff")])
        self.tree_style.map("App.Treeview.Heading", background=[("active", heading)])
        if hasattr(self, "inbox_pane"):
            self.inbox_pane.configure(background=border)

    def _sync_appearance(self) -> None:
        self._apply_tree_style()
        self.after(1000, self._sync_appearance)

