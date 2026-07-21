
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk


class PaymentsViewMixin:
    def _build_payments_view(self, parent: ctk.CTkFrame) -> None:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Thống kê payment",
            font=ctk.CTkFont(family="Segoe UI Variable", size=20, weight="bold"),
        ).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkButton(header, text="Xuất CSV", width=92, command=self.export_payments_csv).grid(row=0, column=1, padx=4)
        ctk.CTkButton(header, text="Làm mới", width=92, command=self.refresh_payments).grid(row=0, column=2, padx=(4, 0))

        self.payment_summary_var = tk.StringVar(value="")
        ctk.CTkLabel(parent, textvariable=self.payment_summary_var, anchor="w").grid(
            row=1, column=0, sticky="ew", padx=20, pady=(0, 10)
        )

        table_frame = ctk.CTkFrame(parent, corner_radius=10, fg_color=("#ffffff", "#202326"))
        table_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 18))
        columns = ("date", "account", "email", "money", "payment_id")
        headings = {"date": "Ngày", "account": "Account", "email": "Email", "money": "Tiền", "payment_id": "Payment ID"}
        widths = {"date": 75, "account": 130, "email": 300, "money": 160, "payment_id": 230}
        self.payment_tree = self._create_tree(
            table_frame,
            columns,
            headings,
            widths,
            center_columns=("date", "account", "money", "payment_id"),
            truncate_columns=("email",),
        )

        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

