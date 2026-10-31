from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from support_agent.config import Settings


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + "$" + digest.hex()


def password_matches(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", 1)
    expected = password_hash(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
    return hmac.compare_digest(expected, digest_hex)


@contextmanager
def connect(path: Path):
    """Commit or roll back each operation and always release Windows file handles."""

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize(settings: Settings) -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(settings.database_path) as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, role TEXT NOT NULL, student_id TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY, full_name TEXT NOT NULL, email TEXT NOT NULL, fee_status TEXT NOT NULL, scholarship_status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS approval_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL, field TEXT NOT NULL, new_value TEXT NOT NULL,
            status TEXT NOT NULL, requested_at TEXT NOT NULL, reviewed_at TEXT, reviewer_username TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
            subject_id TEXT, decision TEXT NOT NULL, outcome TEXT NOT NULL, metadata_json TEXT NOT NULL
        );
        """)
        if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        students = [
            ("S1001", "Asha Sharma", "asha@example.test", "Payment plan active", "Merit scholarship approved"),
            ("S1002", "Rahul Mehta", "rahul@example.test", "No outstanding action", "No scholarship application"),
        ]
        connection.executemany("INSERT INTO students VALUES (?,?,?,?,?)", students)
        users = [
            ("student1", password_hash(settings.student_one_password), "student", "S1001"),
            ("student2", password_hash(settings.student_two_password), "student", "S1002"),
            ("reviewer", password_hash(settings.reviewer_password), "reviewer", None),
        ]
        connection.executemany("INSERT INTO users VALUES (?,?,?,?)", users)


def audit(path: Path, actor: str, action: str, subject_id: str | None, decision: str, outcome: str, metadata: dict[str, object] | None = None) -> None:
    with connect(path) as connection:
        connection.execute(
            "INSERT INTO audit_events (occurred_at,actor,action,subject_id,decision,outcome,metadata_json) VALUES (?,?,?,?,?,?,?)",
            (now(), actor, action, subject_id, decision, outcome, json.dumps(metadata or {})),
        )

