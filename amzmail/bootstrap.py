from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QMessageBox, QWidget

from .vault import VAULT_FILE, Vault, VaultError, VaultMigrationRequired


APP_FOLDER = "AmazonMailReader"


def _pointer_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_FOLDER
    return base / "data-location.json"


def _load_saved_location() -> Path | None:
    try:
        payload = json.loads(_pointer_path().read_text(encoding="utf-8"))
        path = Path(payload["data_dir"])
        return path if path.is_dir() else None
    except (OSError, KeyError, json.JSONDecodeError):
        return None


def _save_location(path: Path) -> None:
    pointer = _pointer_path()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(json.dumps({"data_dir": str(path)}, indent=2), encoding="utf-8")


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _choose_data_dir(parent: QWidget | None, program_dir: Path) -> Path | None:
    initial = Path("D:/") if Path("D:/").exists() else Path.home()
    while True:
        selected = QFileDialog.getExistingDirectory(
            parent,
            "Chọn thư mục lưu dữ liệu Amazon Mail Reader (không chọn ổ C)",
            str(initial),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not selected:
            return None
        path = Path(selected).resolve()
        system_drive = os.environ.get("SystemDrive", "C:").rstrip("\\/").lower()
        if path.drive.rstrip("\\/").lower() == system_drive:
            QMessageBox.warning(
                parent,
                "Không chọn ổ C",
                "Hãy chọn một thư mục ở ổ khác để dữ liệu không bị mất khi cài lại Windows.",
            )
            continue
        if _inside(path, program_dir):
            QMessageBox.warning(
                parent,
                "Chọn thư mục riêng",
                "Thư mục dữ liệu phải nằm ngoài thư mục chương trình để cập nhật không ảnh hưởng dữ liệu.",
            )
            continue
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(parent, "Không tạo được thư mục", str(exc))
            continue
        return path


def _unlock_or_create(parent: QWidget | None, data_dir: Path) -> Vault | None:
    vault_path = data_dir / VAULT_FILE
    if vault_path.exists():
        try:
            return Vault.open_auto(data_dir)
        except VaultMigrationRequired:
            QMessageBox.information(
                parent,
                "Chuyển sang mở tự động",
                "Danh sách account, token và App Password vẫn được giữ nguyên.\n\n"
                "Nhập mật khẩu chính hiện tại một lần cuối để Windows bảo vệ khóa dữ liệu cho tài khoản Windows này. "
                "Từ lần mở app sau sẽ không hỏi mật khẩu nữa.",
            )
            while True:
                password, accepted = QInputDialog.getText(
                    parent,
                    "Mở Amazon Mail Reader",
                    "Nhập mật khẩu chính hiện tại:",
                    QLineEdit.EchoMode.Password,
                )
                if not accepted:
                    return None
                try:
                    return Vault.enable_auto_open(data_dir, password)
                except VaultError as exc:
                    QMessageBox.critical(parent, "Không mở được dữ liệu", str(exc))
        except VaultError as exc:
            QMessageBox.critical(parent, "Không mở được dữ liệu", str(exc))
            return None

    try:
        return Vault.create_auto(data_dir)
    except VaultError as exc:
        QMessageBox.critical(parent, "Không tạo được kho dữ liệu", str(exc))
        return None


def initialize_storage(program_dir: Path, parent: QWidget | None = None) -> tuple[Path, Vault] | None:
    data_dir = _load_saved_location()
    if data_dir is not None and _inside(data_dir, program_dir):
        data_dir = None
    if data_dir is None:
        data_dir = _choose_data_dir(parent, program_dir)
    if data_dir is None:
        return None
    vault = _unlock_or_create(parent, data_dir)
    if vault is None:
        return None
    _save_location(data_dir)
    return data_dir, vault
