from __future__ import annotations

import json
import os
from pathlib import Path
from tkinter import Tk, filedialog, messagebox, simpledialog

from .vault import VAULT_FILE, Vault, VaultError


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


def _choose_data_dir(root: Tk, program_dir: Path) -> Path | None:
    initial = Path("D:/") if Path("D:/").exists() else Path.home()
    while True:
        selected = filedialog.askdirectory(
            parent=root,
            title="Chọn thư mục lưu dữ liệu Amazon Mail Reader (không chọn ổ C)",
            initialdir=str(initial),
            mustexist=False,
        )
        if not selected:
            return None
        path = Path(selected).resolve()
        system_drive = os.environ.get("SystemDrive", "C:").rstrip("\\/").lower()
        if path.drive.rstrip("\\/").lower() == system_drive:
            messagebox.showwarning(
                "Không chọn ổ C",
                "Hãy chọn một thư mục ở ổ khác để dữ liệu không bị mất khi cài lại Windows.",
                parent=root,
            )
            continue
        if _inside(path, program_dir):
            messagebox.showwarning(
                "Chọn thư mục riêng",
                "Thư mục dữ liệu phải nằm ngoài thư mục chương trình để cập nhật không ảnh hưởng dữ liệu.",
                parent=root,
            )
            continue
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Không tạo được thư mục", str(exc), parent=root)
            continue
        return path


def _unlock_or_create(root: Tk, data_dir: Path) -> Vault | None:
    vault_path = data_dir / VAULT_FILE
    if vault_path.exists():
        while True:
            password = simpledialog.askstring(
                "Mở Amazon Mail Reader",
                "Nhập mật khẩu chính:",
                show="*",
                parent=root,
            )
            if password is None:
                return None
            try:
                return Vault.open(data_dir, password)
            except VaultError as exc:
                messagebox.showerror("Không mở được dữ liệu", str(exc), parent=root)

    messagebox.showinfo(
        "Tạo kho dữ liệu",
        "Đây là lần đầu dùng thư mục này. Hãy tạo mật khẩu chính và nhớ kỹ mật khẩu này.",
        parent=root,
    )
    while True:
        first = simpledialog.askstring("Tạo mật khẩu chính", "Mật khẩu chính (ít nhất 8 ký tự):", show="*", parent=root)
        if first is None:
            return None
        second = simpledialog.askstring("Xác nhận mật khẩu", "Nhập lại mật khẩu chính:", show="*", parent=root)
        if second is None:
            return None
        if first != second:
            messagebox.showwarning("Không khớp", "Hai mật khẩu không giống nhau.", parent=root)
            continue
        try:
            return Vault.create(data_dir, first)
        except VaultError as exc:
            messagebox.showerror("Không tạo được kho dữ liệu", str(exc), parent=root)


def initialize_storage(program_dir: Path) -> tuple[Path, Vault] | None:
    root = Tk()
    root.withdraw()
    try:
        data_dir = _load_saved_location()
        if data_dir is not None and _inside(data_dir, program_dir):
            data_dir = None
        if data_dir is None:
            data_dir = _choose_data_dir(root, program_dir)
        if data_dir is None:
            return None
        vault = _unlock_or_create(root, data_dir)
        if vault is None:
            return None
        _save_location(data_dir)
        return data_dir, vault
    finally:
        root.destroy()
