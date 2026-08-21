from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from amzmail.resources import app_icon_path, resource_path


class AppIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_portable_icon_assets_exist_and_load(self):
        self.assertTrue(resource_path("assets", "icons", "app.png").is_file())
        self.assertTrue(resource_path("assets", "icons", "app.ico").is_file())
        icon = QIcon(str(app_icon_path()))
        self.assertFalse(icon.isNull())
        available = {(size.width(), size.height()) for size in icon.availableSizes()}
        for size in (16, 24, 32, 48, 64, 128, 256):
            self.assertIn((size, size), available)


if __name__ == "__main__":
    unittest.main()
