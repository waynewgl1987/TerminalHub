"""ContextStore — persist terminal session context across service restarts.

Each terminal's context is saved to:
    tmp/contexts/{terminal_id}.json

The file holds a lightweight snapshot:
  - metadata  : id, title, description, shell, cwd, created_at, watch_path
  - ai_info   : last-known AI detection result
  - log_tail  : last N lines of terminal output (stripped of ANSI)
  - code_stats: { files_changed, lines_added, lines_removed } counters
  - saved_at  : unix timestamp of the snapshot

A background thread flushes dirty sessions every FLUSH_INTERVAL seconds.
Callers mark a session dirty via `mark_dirty(tid)`.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
LOG_TAIL_LINES = 500   # lines to persist per session
FLUSH_INTERVAL = 30    # seconds between background flushes


class ContextStore:
    def __init__(self, store_dir: Path) -> None:
        self._dir = store_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._dirty: set[str] = set()
        self._lock = threading.Lock()
        self._sessions_ref: Any = None   # set to terminal_manager.sessions dict
        self._flush_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ── Public API ────────────────────────────────────────────────────────────

    def attach(self, sessions: dict) -> None:
        """Point the store at the live sessions dict (call once at startup)."""
        self._sessions_ref = sessions
        self._start_flush_thread()

    def mark_dirty(self, tid: str) -> None:
        with self._lock:
            self._dirty.add(tid)

    def flush(self, tid: str, session: Any, code_changes_count: int = 0) -> None:
        """Write a single session's context to disk immediately."""
        try:
            log_lines = list(session.log_buffer)[-LOG_TAIL_LINES:]
            clean_log = "".join(ANSI_RE.sub("", line) for line in log_lines)
            payload = {
                "id": session.id,
                "title": session.title,
                "description": session.description,
                "shell": session.shell,
                "cwd": session.cwd,
                "created_at": session.created_at,
                "watch_path": getattr(session, "watch_path", ""),
                "ai_info": session.ai_info,
                "log_tail": clean_log,
                "code_changes_count": code_changes_count,
                "saved_at": time.time(),
            }
            path = self._dir / f"{tid}.json"
            tmp  = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)   # atomic rename
        except Exception:
            pass

    def load(self, tid: str) -> dict[str, Any] | None:
        """Return the persisted context for a terminal, or None if missing."""
        path = self._dir / f"{tid}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def list_contexts(self) -> list[dict[str, Any]]:
        """Return all persisted contexts, sorted newest first."""
        results = []
        for p in self._dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                results.append(data)
            except Exception:
                pass
        results.sort(key=lambda d: d.get("saved_at", 0), reverse=True)
        return results

    def delete(self, tid: str) -> None:
        path = self._dir / f"{tid}.json"
        path.unlink(missing_ok=True)

    def stop(self) -> None:
        self._stop_event.set()
        if self._flush_thread and self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5)

    # ── Background flush thread ───────────────────────────────────────────────

    def _start_flush_thread(self) -> None:
        self._flush_thread = threading.Thread(
            target=self._flush_loop, name="context-store-flush", daemon=True
        )
        self._flush_thread.start()

    def _flush_loop(self) -> None:
        while not self._stop_event.wait(FLUSH_INTERVAL):
            self._flush_all_dirty()

    def _flush_all_dirty(self) -> None:
        if not self._sessions_ref:
            return
        with self._lock:
            dirty = list(self._dirty)
            self._dirty.clear()
        for tid in dirty:
            session = self._sessions_ref.get(tid)
            if session:
                self.flush(tid, session)
