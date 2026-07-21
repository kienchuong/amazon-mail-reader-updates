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
        self.assertIn('(\"date\", \"account\", \"email\", \"money\", \"payment_id\")', source)
        self.assertNotIn('"subject"', source)


if __name__ == "__main__":
    unittest.main()

