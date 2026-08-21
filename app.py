from __future__ import annotations

import ctypes
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _missing_ui_dependency(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, "Amazon Mail Reader", 0x10)


def main() -> int:
    try:
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        _missing_ui_dependency(
            "App cần PySide6. Hãy cài environment của project bằng:\n\n"
            "python -m pip install -r requirements.txt"
        )
        return 1

    from amzmail import APP_NAME
    from amzmail.bootstrap import initialize_storage
    from amzmail.resources import app_icon_path
    from amzmail.ui import AmazonMailReaderApp

    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AmazonMailReader.Desktop")

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(APP_NAME)
    qt_app.setOrganizationName("Amazon Mail Reader")
    icon = QIcon(str(app_icon_path()))
    if not icon.isNull():
        qt_app.setWindowIcon(icon)
    storage = initialize_storage(BASE_DIR)
    if storage is None:
        return 0
    data_dir, vault = storage
    window = AmazonMailReaderApp(data_dir, vault)
    window.show()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
