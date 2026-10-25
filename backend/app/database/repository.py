"""Persistence layer. SQLite for local development behind a small repository interface.

Migrating to PostgreSQL: implement the same `Repository` methods with psycopg/SQLAlchemy
(payload -> JSONB column) and swap it in `create_repository` -- routes/services never touch SQL.

Privacy: only analysis *results* are stored. Uploaded images/videos are never written to disk
(videos use a temp file that is deleted immediately) and frame thumbnails are not persisted.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KINDS = {"food_analysis", "freshness_analysis", "hygiene_report", "saved_recipe", "profile",
         "meal_plan", "shopping_list", "intake_log"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Repository:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, timeout=15)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            # Several uvicorn workers share one file: WAL lets readers and a writer coexist, and the busy
            # timeout makes a writer wait for the lock instead of failing with "database is locked".
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=15000")
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, user_id TEXT NOT NULL DEFAULT 'local',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_records_kind_created ON records(kind, created_at DESC);
            """)

    @staticmethod
    def _row(r: sqlite3.Row) -> dict:
        return {"id": r["id"], "kind": r["kind"], "created_at": r["created_at"], "updated_at": r["updated_at"],
                "payload": json.loads(r["payload"])}

    @staticmethod
    def _check(kind: str) -> None:
        if kind not in KINDS:
            raise ValueError(f"Unknown record kind: {kind}")

    def add(self, kind: str, payload: dict[str, Any], record_id: str | None = None) -> dict:
        self._check(kind)
        rid, now = record_id or uuid.uuid4().hex, _now()
        with self._lock:
            self._conn.execute("INSERT INTO records (id, kind, created_at, updated_at, payload) VALUES (?,?,?,?,?)",
                               (rid, kind, now, now, json.dumps(payload)))
            self._conn.commit()
        return self.get(rid)  # type: ignore[return-value]

    def upsert(self, kind: str, record_id: str, payload: dict[str, Any]) -> dict:
        self._check(kind)
        now = _now()
        with self._lock:
            cur = self._conn.execute("UPDATE records SET payload=?, updated_at=? WHERE id=? AND kind=?",
                                     (json.dumps(payload), now, record_id, kind))
            if cur.rowcount == 0:
                self._conn.execute("INSERT INTO records (id, kind, created_at, updated_at, payload) VALUES (?,?,?,?,?)",
                                   (record_id, kind, now, now, json.dumps(payload)))
            self._conn.commit()
        return self.get(record_id)  # type: ignore[return-value]

    def get(self, record_id: str) -> dict | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
        return self._row(r) if r else None

    def list(self, kind: str | None = None, limit: int = 50, offset: int = 0, since: str | None = None) -> list[dict]:
        if kind:
            self._check(kind)
        q, args = "SELECT * FROM records WHERE 1=1", []
        if kind:
            q += " AND kind=?"; args.append(kind)
        if since:
            q += " AND created_at>=?"; args.append(since)
        q += " ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?"
        args += [max(1, min(limit, 500)), max(0, offset)]
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [self._row(r) for r in rows]

    def latest(self, kind: str) -> dict | None:
        rows = self.list(kind, limit=1)
        return rows[0] if rows else None

    def count(self, kind: str | None = None) -> int:
        with self._lock:
            if kind:
                return self._conn.execute("SELECT COUNT(*) FROM records WHERE kind=?", (kind,)).fetchone()[0]
            return self._conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]

    def delete(self, record_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM records WHERE id=?", (record_id,))
            self._conn.commit()
        return cur.rowcount > 0

    def ping(self) -> bool:
        try:
            with self._lock:
                self._conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def close(self) -> None:
        self._conn.close()


def create_repository(path: str) -> Repository:
    return Repository(path)
