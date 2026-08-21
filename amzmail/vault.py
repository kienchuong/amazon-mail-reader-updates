from __future__ import annotations

import base64
import ctypes
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


VAULT_FILE = "vault.json"
VAULT_CHECK = "amazon-mail-reader-vault-v1"
PBKDF2_ITERATIONS = 600_000
AUTO_KEY_FIELD = "auto_key_dpapi"


class VaultError(RuntimeError):
    pass


class VaultMigrationRequired(VaultError):
    """The existing password vault has not yet been unlocked on this Windows user."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _data_blob(value: bytes):
    buffer = ctypes.create_string_buffer(value)
    return (
        _DataBlob(
            len(value),
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
        ),
        buffer,
    )


def _dpapi_protect(value: bytes) -> bytes:
    if os.name != "nt":
        raise VaultError("Mở không mật khẩu chỉ hỗ trợ Windows.")
    input_blob, input_buffer = _data_blob(value)
    output_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "Amazon Mail Reader",
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        raise VaultError("Windows không thể bảo vệ khóa dữ liệu.")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def _dpapi_unprotect(value: bytes) -> bytes:
    if os.name != "nt":
        raise VaultError("Mở không mật khẩu chỉ hỗ trợ Windows.")
    input_blob, input_buffer = _data_blob(value)
    output_blob = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        raise VaultError("Windows không thể mở khóa dữ liệu tự động.")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


class Vault:
    def __init__(self, fernet: Fernet, key: bytes):
        self._fernet = fernet
        self._key = key

    @staticmethod
    def _derive(password: str, salt: bytes, iterations: int) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    @staticmethod
    def _read_payload(data_dir: Path) -> dict:
        path = data_dir / VAULT_FILE
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise VaultError("Không đọc được kho dữ liệu.") from exc

    @staticmethod
    def _write_payload(data_dir: Path, payload: dict) -> None:
        (data_dir / VAULT_FILE).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def _from_key(cls, key: bytes, payload: dict) -> "Vault":
        try:
            fernet = Fernet(key)
            check = fernet.decrypt(payload["check"].encode("ascii")).decode("utf-8")
        except (KeyError, ValueError, InvalidToken) as exc:
            raise VaultError("Không thể mở khóa dữ liệu.") from exc
        if check != VAULT_CHECK:
            raise VaultError("Không thể mở khóa dữ liệu.")
        return cls(fernet, key)

    @classmethod
    def create(cls, data_dir: Path, password: str) -> "Vault":
        if len(password) < 8:
            raise VaultError("Mật khẩu chính phải có ít nhất 8 ký tự.")
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / VAULT_FILE
        if path.exists():
            raise VaultError("Thư mục này đã có kho dữ liệu.")
        salt = os.urandom(16)
        key = cls._derive(password, salt, PBKDF2_ITERATIONS)
        fernet = Fernet(key)
        payload = {
            "version": 1,
            "kdf": "pbkdf2-sha256",
            "iterations": PBKDF2_ITERATIONS,
            "salt": base64.b64encode(salt).decode("ascii"),
            "check": fernet.encrypt(VAULT_CHECK.encode("utf-8")).decode("ascii"),
        }
        cls._write_payload(data_dir, payload)
        return cls(fernet, key)

    @classmethod
    def open(cls, data_dir: Path, password: str) -> "Vault":
        try:
            payload = cls._read_payload(data_dir)
            salt = base64.b64decode(payload["salt"])
            iterations = int(payload["iterations"])
            key = cls._derive(password, salt, iterations)
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise VaultError("Mật khẩu chính không đúng hoặc kho dữ liệu bị lỗi.") from exc
        return cls._from_key(key, payload)

    @classmethod
    def create_auto(cls, data_dir: Path) -> "Vault":
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / VAULT_FILE
        if path.exists():
            raise VaultError("Thư mục này đã có kho dữ liệu.")
        key = Fernet.generate_key()
        fernet = Fernet(key)
        payload = {
            "version": 2,
            "protection": "windows-dpapi-current-user",
            AUTO_KEY_FIELD: base64.b64encode(_dpapi_protect(key)).decode("ascii"),
            "check": fernet.encrypt(VAULT_CHECK.encode("utf-8")).decode("ascii"),
        }
        cls._write_payload(data_dir, payload)
        return cls(fernet, key)

    @classmethod
    def open_auto(cls, data_dir: Path) -> "Vault":
        payload = cls._read_payload(data_dir)
        protected_key = payload.get(AUTO_KEY_FIELD)
        if not protected_key:
            raise VaultMigrationRequired("Kho dữ liệu cần chuyển sang mở tự động.")
        try:
            key = _dpapi_unprotect(base64.b64decode(protected_key))
            return cls._from_key(key, payload)
        except (ValueError, VaultError) as exc:
            raise VaultMigrationRequired("Windows này chưa có khóa mở dữ liệu.") from exc

    @classmethod
    def enable_auto_open(cls, data_dir: Path, password: str) -> "Vault":
        vault = cls.open(data_dir, password)
        payload = cls._read_payload(data_dir)
        payload[AUTO_KEY_FIELD] = base64.b64encode(_dpapi_protect(vault._key)).decode("ascii")
        payload["protection"] = "windows-dpapi-current-user"
        cls._write_payload(data_dir, payload)
        return vault

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
            raise VaultError("Không thể giải mã dữ liệu.") from exc
