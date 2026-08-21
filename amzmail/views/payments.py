from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from amzmail.views.controls import ValueBinding


class PaymentsViewMixin:
    def _build_payments_view(self, parent: QWidget) -> None:
        page = QVBoxLayout(parent)
        page.setContentsMargins(20, 18, 20, 18)
        page.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Thống kê payment")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch(1)
        export = QPushButton("Xuất CSV")
        export.clicked.connect(self.export_payments_csv)
        refresh = QPushButton("Làm mới")
        refresh.clicked.connect(self.refresh_payments)
        header.addWidget(export)
        header.addWidget(refresh)
        page.addLayout(header)

        summary = QLabel("")
        self.payment_summary_var = ValueBinding(summary)
        page.addWidget(summary)

        columns = ("date", "account", "email", "currency", "amount", "payment_id")
        headings = {
            "date": "Date", "account": "Account", "email": "Email",
            "currency": "Currency", "amount": "Amount", "payment_id": "Payment ID",
        }
        widths = {"date": 75, "account": 130, "email": 300, "currency": 100, "amount": 145, "payment_id": 230}
        self.payment_tree = self._create_tree(
            parent,
            columns,
            headings,
            widths,
            center_columns=("date", "account", "payment_id"),
            right_columns=("currency", "amount"),
            truncate_columns=("email",),
        )
        page.addWidget(self.payment_tree, 1)
