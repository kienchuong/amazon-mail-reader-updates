from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from .vault import Vault


SCHEMA_VERSION = 2


class AppDatabase:
    def __init__(self, path: Path, vault: Vault):
        self.path = path
        self.vault = vault
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _columns(self, table: str) -> set[str]:
        return {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}

    def _init_schema(self) -> None:
        with self._lock, self.conn:
            self.conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;

                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT 'Custom',
                    host TEXT NOT NULL DEFAULT '',
                    port INTEGER NOT NULL DEFAULT 993,
                    username TEXT NOT NULL DEFAULT '',
                    password_blob TEXT NOT NULL DEFAULT '',
                    folder TEXT NOT NULL DEFAULT 'INBOX',
                    use_ssl INTEGER NOT NULL DEFAULT 1,
                    active INTEGER NOT NULL DEFAULT 1,
                    auth_type TEXT NOT NULL DEFAULT 'imap_password',
                    token_blob TEXT NOT NULL DEFAULT '',
                    provider_account_id TEXT NOT NULL DEFAULT '',
                    connection_status TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    folder TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    message_id TEXT,
                    mail_date TEXT,
                    from_addr TEXT,
                    to_addr TEXT,
                    subject TEXT,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    trusted_sender INTEGER NOT NULL DEFAULT 0,
                    currency TEXT,
                    amount REAL,
                    payment_id TEXT,
                    snippet TEXT,
                    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE,
                    UNIQUE(account_id, folder, uid)
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                """
            )
            account_columns = self._columns("accounts")
            migrations = {
                "auth_type": "ALTER TABLE accounts ADD COLUMN auth_type TEXT NOT NULL DEFAULT 'imap_password'",
                "token_blob": "ALTER TABLE accounts ADD COLUMN token_blob TEXT NOT NULL DEFAULT ''",
                "provider_account_id": "ALTER TABLE accounts ADD COLUMN provider_account_id TEXT NOT NULL DEFAULT ''",
                "connection_status": "ALTER TABLE accounts ADD COLUMN connection_status TEXT NOT NULL DEFAULT ''",
            }
            for column, statement in migrations.items():
                if column not in account_columns:
                    self.conn.execute(statement)
            self.conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def add_imap_account(self, data: dict[str, Any]) -> int:
        with self._lock, self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO accounts
                (name, email, provider, host, port, username, password_blob, folder,
                 use_ssl, active, auth_type, connection_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'imap_password', 'Đã lưu')
                """,
                (
                    data["name"].strip(),
                    data["email"].strip(),
                    data["provider"],
                    data["host"].strip(),
                    int(data["port"]),
                    data["username"].strip(),
                    self.vault.encrypt(data["password"]),
                    data.get("folder", "INBOX").strip() or "INBOX",
                    1 if data.get("use_ssl", True) else 0,
                    1 if data.get("active", True) else 0,
                ),
            )
            return int(cur.lastrowid)

    def add_or_update_microsoft_account(self, profile: dict[str, str], token_json: str, name: str = "") -> int:
        email = profile["email"].strip().lower()
        provider_id = profile.get("id", "")
        with self._lock, self.conn:
            existing = self.conn.execute(
                "SELECT id FROM accounts WHERE auth_type='microsoft_oauth' AND (email=? OR provider_account_id=?)",
                (email, provider_id),
            ).fetchone()
            encrypted = self.vault.encrypt(token_json)
            if existing:
                self.conn.execute(
                    """
                    UPDATE accounts SET name=?, email=?, provider='Outlook', token_blob=?,
                        provider_account_id=?, connection_status='Đã kết nối', updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (name.strip() or profile.get("display_name") or email, email, encrypted, provider_id, existing["id"]),
                )
                return int(existing["id"])
            cur = self.conn.execute(
                """
                INSERT INTO accounts
                (name, email, provider, host, port, username, password_blob, folder, use_ssl,
                 active, auth_type, token_blob, provider_account_id, connection_status)
                VALUES (?, ?, 'Outlook', '', 0, ?, '', 'inbox', 1, 1,
                        'microsoft_oauth', ?, ?, 'Đã kết nối')
                """,
                (name.strip() or profile.get("display_name") or email, email, email, encrypted, provider_id),
            )
            return int(cur.lastrowid)

    def update_imap_account(self, account_id: int, data: dict[str, Any], update_password: bool) -> None:
        fields = [
            "name=?", "email=?", "provider=?", "host=?", "port=?", "username=?",
            "folder=?", "use_ssl=?", "active=?", "updated_at=CURRENT_TIMESTAMP",
        ]
        values: list[Any] = [
            data["name"].strip(), data["email"].strip(), data["provider"], data["host"].strip(),
            int(data["port"]), data["username"].strip(), data.get("folder", "INBOX").strip() or "INBOX",
            1 if data.get("use_ssl", True) else 0, 1 if data.get("active", True) else 0,
        ]
        if update_password:
            fields.append("password_blob=?")
            values.append(self.vault.encrypt(data["password"]))
        values.append(account_id)
        with self._lock, self.conn:
            self.conn.execute(f"UPDATE accounts SET {', '.join(fields)} WHERE id=?", values)

    def update_account_name_active(self, account_id: int, name: str, active: bool) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "UPDATE accounts SET name=?, active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (name.strip(), 1 if active else 0, account_id),
            )

    def update_oauth_token(self, account_id: int, token_json: str) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "UPDATE accounts SET token_blob=?, connection_status='Đã kết nối', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (self.vault.encrypt(token_json), account_id),
            )

    def set_connection_status(self, account_id: int, status: str) -> None:
        with self._lock, self.conn:
            self.conn.execute("UPDATE accounts SET connection_status=? WHERE id=?", (status, account_id))

    def delete_account(self, account_id: int) -> None:
        with self._lock, self.conn:
            self.conn.execute("DELETE FROM messages WHERE account_id=?", (account_id,))
            self.conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))

    def get_accounts(self, active_only: bool = False) -> list[sqlite3.Row]:
        query = "SELECT * FROM accounts"
        if active_only:
            query += " WHERE active=1"
        query += " ORDER BY name COLLATE NOCASE"
        with self._lock:
            return list(self.conn.execute(query))

    def get_account(self, account_id: int) -> sqlite3.Row | None:
        with self._lock:
            return self.conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()

    def account_password(self, account: sqlite3.Row) -> str:
        return self.vault.decrypt(account["password_blob"])

    def account_token(self, account: sqlite3.Row) -> str:
        return self.vault.decrypt(account["token_blob"])

    def upsert_message(self, message: dict[str, Any]) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                """
                INSERT INTO messages
                (account_id, folder, uid, message_id, mail_date, from_addr, to_addr, subject,
                 category, priority, trusted_sender, currency, amount, payment_id, snippet)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id, folder, uid) DO UPDATE SET
                    message_id=excluded.message_id, mail_date=excluded.mail_date,
                    from_addr=excluded.from_addr, to_addr=excluded.to_addr, subject=excluded.subject,
                    category=excluded.category, priority=excluded.priority,
                    trusted_sender=excluded.trusted_sender, currency=excluded.currency,
                    amount=excluded.amount, payment_id=excluded.payment_id,
                    snippet=excluded.snippet, updated_at=CURRENT_TIMESTAMP
                """,
                (
                    message["account_id"], message["folder"], message["uid"], message.get("message_id"),
                    message.get("mail_date"), message.get("from_addr"), message.get("to_addr"),
                    message.get("subject"), message["category"], message["priority"],
                    1 if message.get("trusted_sender") else 0, message.get("currency"),
                    message.get("amount"), message.get("payment_id"), message.get("snippet"),
                ),
            )

    def list_messages(self, category: str = "All", query: str = "", limit: int = 500) -> list[sqlite3.Row]:
        clauses: list[str] = []
        values: list[Any] = []
        if category != "All":
            clauses.append("m.category=?")
            values.append(category)
        if query:
            clauses.append("(m.subject LIKE ? OR m.from_addr LIKE ? OR m.snippet LIKE ? OR a.name LIKE ? OR a.email LIKE ?)")
            like = f"%{query}%"
            values.extend([like, like, like, like, like])
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        values.append(limit)
        sql = f"""
            SELECT m.*, a.name AS account_name, a.email AS account_email
            FROM messages m JOIN accounts a ON a.id=m.account_id
            {where}
            ORDER BY COALESCE(m.mail_date, m.first_seen_at) DESC LIMIT ?
        """
        with self._lock:
            return list(self.conn.execute(sql, values))

    def get_message(self, message_id: int) -> sqlite3.Row | None:
        with self._lock:
            return self.conn.execute(
                """SELECT m.*, a.name AS account_name, a.email AS account_email
                   FROM messages m JOIN accounts a ON a.id=m.account_id WHERE m.id=?""",
                (message_id,),
            ).fetchone()

    def list_payments(self) -> list[sqlite3.Row]:
        with self._lock:
            return list(self.conn.execute(
                """SELECT m.*, a.name AS account_name, a.email AS account_email
                   FROM messages m JOIN accounts a ON a.id=m.account_id
                   WHERE m.category='Payment'
                   ORDER BY COALESCE(m.mail_date, m.first_seen_at) DESC"""
            ))

    def set_setting(self, key: str, value: str) -> None:
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_setting(self, key: str, default: str = "") -> str:
        with self._lock:
            row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_secret_setting(self, key: str, value: str) -> None:
        self.set_setting(key, self.vault.encrypt(value))

    def get_secret_setting(self, key: str, default: str = "") -> str:
        value = self.get_setting(key)
        return self.vault.decrypt(value) if value else default

    def close(self) -> None:
        with self._lock:
            self.conn.close()
