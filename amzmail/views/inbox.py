from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from amzmail.views.data_table import FluentSplitPane


class InboxViewMixin:
    def _build_inbox_view(self, parent: ctk.CTkFrame) -> None:
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 12))
        toolbar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(toolbar, text="Loại").grid(row=0, column=0, sticky="w", padx=(0, 7))
        self.category_filter = tk.StringVar(value="All")
        category_box = ctk.CTkComboBox(
            toolbar,
            variable=self.category_filter,
            values=["All", "Payment", "Reject", "Amazon Account", "Amazon", "Security", "General"],
            width=170,
            state="readonly",
            command=lambda _value: self.refresh_inbox(),
        )
        category_box.grid(row=0, column=1, sticky="w", padx=(0, 14))

        self.search_var = tk.StringVar()
        search = ctk.CTkEntry(toolbar, textvariable=self.search_var, placeholder_text="Tìm tiêu đề hoặc người gửi")
        search.grid(row=0, column=2, sticky="ew", padx=(0, 8))
        search.bind("<Return>", lambda _event: self.refresh_inbox())
        ctk.CTkButton(toolbar, text="Tìm kiếm", width=92, command=self.refresh_inbox).grid(row=0, column=3, padx=4)
        ctk.CTkButton(toolbar, text="Quét tất cả", width=104, command=self.start_scan).grid(row=0, column=4, padx=(4, 0))

        options = ctk.CTkFrame(parent, fg_color="transparent")
        options.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 12))
        ctk.CTkLabel(options, text="Số ngày").pack(side="left")
        self.days_back_var = tk.StringVar(value="30")
        ctk.CTkEntry(options, textvariable=self.days_back_var, width=65).pack(side="left", padx=(7, 18))
        ctk.CTkLabel(options, text="Giới hạn/account").pack(side="left")
        self.max_messages_var = tk.StringVar(value="300")
        ctk.CTkEntry(options, textvariable=self.max_messages_var, width=75).pack(side="left", padx=(7, 18))
        self.include_general_var = tk.BooleanVar(value=False)
        ctk.CTkSwitch(options, text="Lưu cả mail thường", variable=self.include_general_var).pack(side="left")

        pane = FluentSplitPane(parent)
        pane.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 18))
        self.inbox_pane = pane

        list_frame = pane.left
        detail_frame = pane.right

        columns = ("date", "account", "category", "priority", "from", "subject", "amount")
        headings = {
            "date": "Ngày", "account": "Account", "category": "Loại", "priority": "Mức",
            "from": "Người gửi", "subject": "Tiêu đề", "amount": "Payment",
        }
        widths = {"date": 132, "account": 105, "category": 105, "priority": 72, "from": 180, "subject": 310, "amount": 100}
        self.inbox_tree = self._create_tree(
            list_frame,
            columns,
            headings,
            widths,
            center_columns=("date", "account", "category", "priority", "amount"),
            truncate_columns=("from", "subject"),
            status_columns=("category", "priority"),
        )
        self.inbox_tree.bind("<<TreeviewSelect>>", self.on_message_selected)

        ctk.CTkLabel(
            detail_frame,
            text="Nội dung mail",
            font=ctk.CTkFont(family="Segoe UI Variable", size=16, weight="bold"),
        ).pack(
            anchor="w", padx=14, pady=(12, 8)
        )
        self.message_text = ctk.CTkTextbox(
            detail_frame, wrap="word", font=("Segoe UI Variable", 13), corner_radius=4
        )
        self.message_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.message_text.insert("1.0", "Chọn một mail để đọc nội dung.")
        self.message_text.configure(state="disabled")

        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)
