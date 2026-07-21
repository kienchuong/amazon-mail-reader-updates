from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


VAULT_FILE = "vault.json"
VAULT_CHECK = "amazon-mail-reader-vault-v1"
PBKDF2_ITERATIONS = 600_000


class VaultError(RuntimeError):
    pass


class Vault:
    def __init__(self, fernet: Fernet):
        self._fernet = fernet

    @staticmethod
    def _derive(password: str, salt: bytes, iterations: int) -> Fernet:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
        return Fernet(key)

    @classmethod
    def create(cls, data_dir: Path, password: str) -> "Vault":
        if len(password) < 8:
            raise VaultError("Mật khẩu chính phải có ít nhất 8 ký tự.")
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / VAULT_FILE
        if path.exists():
            raise VaultError("Thư mục này đã có kho dữ liệu.")
        salt = os.urandom(16)
        fernet = cls._derive(password, salt, PBKDF2_ITERATIONS)
        payload = {
            "version": 1,
            "kdf": "pbkdf2-sha256",
            "iterations": PBKDF2_ITERATIONS,
            "salt": base64.b64encode(salt).decode("ascii"),
            "check": fernet.encrypt(VAULT_CHECK.encode("utf-8")).decode("ascii"),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return cls(fernet)

    @classmethod
    def open(cls, data_dir: Path, password: str) -> "Vault":
        path = data_dir / VAULT_FILE
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            salt = base64.b64decode(payload["salt"])
            iterations = int(payload["iterations"])
            fernet = cls._derive(password, salt, iterations)
            check = fernet.decrypt(payload["check"].encode("ascii")).decode("utf-8")
        except (OSError, KeyError, ValueError, json.JSONDecodeError, InvalidToken) as exc:
            raise VaultError("Mật khẩu chính không đúng hoặc kho dữ liệu bị lỗi.") from exc
        if check != VAULT_CHECK:
            raise VaultError("Mật khẩu chính không đúng.")
        return cls(fernet)

    def encrypt(self, value: str) -> str:
        if not value:
            return ""
        return "vault:v1:" + self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        if not value:
            return ""
        if not value.startswith("vault:v1:"):
            raise VaultError("Dữ liệu bí mật dùng định dạng cũ và cần nhập lại.")
        try:
            return self._fernet.decrypt(value[9:].encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise VaultError("Không thể giải mã dữ liệu bằng mật khẩu chính này.") from exc

