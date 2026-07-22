import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UiStructureTests(unittest.TestCase):
    def test_ui_uses_customtkinter_sidebar_shell(self):
        controller = (ROOT / "amzmail" / "ui.py").read_text(encoding="utf-8")
        shell = (ROOT / "amzmail" / "views" / "shell.py").read_text(encoding="utf-8")
        self.assertIn("ctk.CTk", controller)
        self.assertIn('self.show_page("inbox")', shell)
        self.assertNotIn("ttk.Notebook", controller + shell)
        self.assertIn("minsize=220", shell)
        ast.parse(controller)
        ast.parse(shell)

    def test_each_screen_has_its_own_module(self):
        expected = {
            "inbox.py": "_build_inbox_view",
            "payments.py": "_build_payments_view",
            "accounts.py": "_build_accounts_view",
            "settings.py": "_build_settings_view",
        }
        for filename, builder in expected.items():
            source = (ROOT / "amzmail" / "views" / filename).read_text(encoding="utf-8")
            self.assertIn(builder, source)
            ast.parse(source)

    def test_payment_columns_remain_compact(self):
        source = (ROOT / "amzmail" / "views" / "payments.py").read_text(encoding="utf-8")
        self.assertIn('(\"date\", \"account\", \"email\", \"currency\", \"amount\", \"payment_id\")', source)
        self.assertIn('right_columns=(\"currency\", \"amount\")', source)
        self.assertNotIn('"subject"', source)

    def test_fluent_table_supports_windows_11_layout(self):
        source = (ROOT / "amzmail" / "views" / "data_table.py").read_text(encoding="utf-8")
        self.assertIn("from tksheet import Sheet", source)
        self.assertIn('family="Segoe UI Variable"', source)
        self.assertIn('"double_click_column_resize"', source)
        self.assertIn("def shorten", source)
        self.assertIn("def fit_columns", source)
        self.assertIn("FLUENT_DARK_TABLE_OPTIONS", source)
        shell = (ROOT / "amzmail" / "views" / "shell.py").read_text(encoding="utf-8")
        self.assertIn("right_columns=right_columns", shell)
        self.assertIn('"table_bg": "#17191c"', source)
        self.assertIn('"table_grid_fg": "#17191c"', source)
        self.assertIn('"header_grid_fg": "#34383d"', source)
        ast.parse(source)

    def test_inbox_date_is_compact(self):
        source = (ROOT / "amzmail" / "ui.py").read_text(encoding="utf-8")
        self.assertIn('strftime("%d/%m")', source)

    def test_inbox_uses_seven_day_default_and_shared_refresh(self):
        inbox = (ROOT / "amzmail" / "views" / "inbox.py").read_text(encoding="utf-8")
        controller = (ROOT / "amzmail" / "ui.py").read_text(encoding="utf-8")
        self.assertIn('days_back_var = tk.StringVar(value="7")', inbox)
        self.assertIn("Số ngày quét/hiển thị", inbox)
        self.assertIn("def refresh_current_range", controller)
        self.assertIn("self.db.list_payments(self.display_days())", controller)

    def test_accounts_view_has_distinct_single_account_scan_action(self):
        accounts = (ROOT / "amzmail" / "views" / "accounts.py").read_text(encoding="utf-8")
        controller = (ROOT / "amzmail" / "ui.py").read_text(encoding="utf-8")
        self.assertIn('text="Quét account này"', accounts)
        self.assertIn('fg_color="#168a55"', accounts)
        self.assertNotIn("disabled_fg_color", accounts)
        self.assertIn("command=self.start_selected_account_scan", accounts)
        self.assertIn("def start_selected_account_scan", controller)
        self.assertIn("self.db.get_account(self.selected_account_id)", controller)
        self.assertIn("if self.scan_running", controller)
        ast.parse(accounts)
        ast.parse(controller)


    def test_mobile_dashboard_stays_in_its_own_sync_module(self):
        controller = (ROOT / "amzmail" / "ui.py").read_text(encoding="utf-8")
        settings = (ROOT / "amzmail" / "views" / "settings.py").read_text(encoding="utf-8")
        sync = (ROOT / "amzmail" / "mobile_sync.py").read_text(encoding="utf-8")
        self.assertIn("from amzmail.mobile_sync import", controller)
        self.assertIn("def sync_mobile_dashboard", controller)
        self.assertIn("Mobile Dashboard", settings)
        self.assertIn("def build_mobile_snapshot", sync)


if __name__ == "__main__":
    unittest.main()
