from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from typing import Any, Optional


class LLMResponseCache:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.environ.get("PBICOMPASS_LLM_CACHE") or "off"
        self.db_path = db_path
        self.conn = None
        if self.db_path != "off":
            try:
                # timeout: agents in one job now run concurrently, so several
                # threads open their own connection to this same file and
                # write to it at once. Without a busy timeout the loser of a
                # write race raises "database is locked" immediately, which
                # the callers below swallow — turning contention into silent
                # cache misses (and, on a resumed job, re-billed LLM calls).
                # WAL lets readers proceed during a write, which is the common
                # case here: every call reads before it writes.
                self.conn = sqlite3.connect(self.db_path, timeout=10.0,
                                            check_same_thread=False)
                try:
                    self.conn.execute("PRAGMA journal_mode=WAL")
                except Exception:
                    pass  # e.g. a filesystem with no WAL support — plain mode still works
                self._create_table()
            except Exception:
                pass

    def _create_table(self):
        if not self.conn:
            return
        with self.conn:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS llm_cache ("
                "  key TEXT PRIMARY KEY,"
                "  response TEXT,"
                "  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP"
                ")"
            )

    def _get_key(self, system: str, payload: dict, schema: dict, model_id: str,
                 effort: Optional[str] = None) -> str:
        data = {
            "system": system,
            "payload": payload,
            "schema": schema,
            "model_id": model_id,
            "effort": effort,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def get(self, system: str, payload: dict, schema: dict, model_id: str,
            effort: Optional[str] = None) -> Optional[dict]:
        if not self.conn:
            return None
        key = self._get_key(system, payload, schema, model_id, effort)
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT response FROM llm_cache WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
        except Exception:
            pass
        return None

    def set(self, system: str, payload: dict, schema: dict, model_id: str, response: dict,
            effort: Optional[str] = None) -> None:
        if not self.conn:
            return
        key = self._get_key(system, payload, schema, model_id, effort)
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO llm_cache (key, response) VALUES (?, ?)",
                    (key, json.dumps(response))
                )
        except Exception:
            pass

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
