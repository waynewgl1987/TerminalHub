from __future__ import annotations

import os
import select
import shlex
import signal
import struct
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

if sys.platform != "win32":
    import fcntl
    import pty
    import termios


@dataclass
class TerminalSession:
    id: str
    title: str
    description: str
    shell: str
    cwd: str
    pid: int
    created_at: float
    connected: bool = False
    log_max_lines: int = 5000
    ai_info: dict[str, Any] = field(default_factory=lambda: {
        "detected": False,
        "provider": "",
        "model": "",
        "framework": "",
        "confidence": 0.0,
    })
    watch_path: str = ""
    _master_fd: Optional[int] = None
    _process: Any = None
    _pty_process: Any = None
    _use_winpty: bool = False
    _read_thread: Optional[threading.Thread] = None
    _output_callbacks: list[Callable[[dict[str, Any]], None]] = field(default_factory=list)
    log_buffer: deque[str] = field(default_factory=deque)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.log_buffer = deque(maxlen=self.log_max_lines)

    def add_output_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._output_callbacks.append(callback)
            self.connected = bool(self._output_callbacks)

    def remove_output_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            if callback in self._output_callbacks:
                self._output_callbacks.remove(callback)
            self.connected = bool(self._output_callbacks)

    def write_input(self, data: str) -> None:
        if not data:
            return
        encoded = data.encode()
        if self._use_winpty and self._pty_process is not None:
            self._pty_process.write(data)
        elif self._master_fd is not None:
            os.write(self._master_fd, encoded)
        elif self._process and self._process.stdin:
            self._process.stdin.write(encoded)
            self._process.stdin.flush()

    def resize(self, rows: int, cols: int) -> None:
        if rows <= 0 or cols <= 0:
            return
        if self._use_winpty and self._pty_process is not None:
            try:
                self._pty_process.set_size(cols, rows)
            except Exception:
                return
            return
        if self._master_fd is None or sys.platform == "win32":
            return
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)

    def is_alive(self) -> bool:
        if self._use_winpty and self._pty_process is not None:
            try:
                return self._pty_process.isalive()
            except Exception:
                return False
        if self._process is None:
            return False
        return self._process.poll() is None

    def full_log(self) -> list[str]:
        with self._lock:
            return list(self.log_buffer)

    def tail_log(self, limit: int = 200) -> list[str]:
        with self._lock:
            return list(self.log_buffer)[-limit:]

    def append_output(self, text: str) -> None:
        if not text:
            return
        with self._lock:
            for line in text.splitlines(keepends=True) or [text]:
                self.log_buffer.append(line)

    def broadcast(self, message: dict[str, Any]) -> None:
        with self._lock:
            callbacks = list(self._output_callbacks)
        for callback in callbacks:
            try:
                callback(message)
            except Exception:
                continue

    def close(self) -> None:
        try:
            if self._use_winpty and self._pty_process is not None:
                self._pty_process.terminate(force=True)
            elif self._process is not None:
                if sys.platform == "win32":
                    self._process.terminate()
                else:
                    os.killpg(self.pid, signal.SIGTERM)
        except Exception:
            pass
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=1)
        self.broadcast({"type": "status", "connected": False})


class TerminalManager:
    def __init__(
        self,
        default_shell_unix: str,
        default_shell_windows: str,
        log_max_lines: int = 5000,
        code_watcher: Any | None = None,
        ai_detector: Any | None = None,
    ) -> None:
        self.default_shell_unix = default_shell_unix
        self.default_shell_windows = default_shell_windows
        self.log_max_lines = log_max_lines
        self.code_watcher = code_watcher
        self.ai_detector = ai_detector
        self.sessions: dict[str, TerminalSession] = {}
        self._lock = threading.Lock()

    async def create(
        self,
        shell: str | None = None,
        cwd: str | None = None,
        title: str | None = None,
        description: str | None = None,
        watch_path: str | None = None,
    ) -> TerminalSession:
        import asyncio

        loop = asyncio.get_running_loop()
        session = await loop.run_in_executor(None, self._create_sync, shell, cwd, title, description, watch_path)
        with self._lock:
            self.sessions[session.id] = session
        return session

    def _create_sync(
        self,
        shell: str | None,
        cwd: str | None,
        title: str | None,
        description: str | None,
        watch_path: str | None,
    ) -> TerminalSession:
        shell = shell or (self.default_shell_windows if sys.platform == "win32" else self.default_shell_unix)
        cwd_path = Path(cwd or Path.home()).expanduser().resolve()
        cwd_path.mkdir(parents=True, exist_ok=True)
        session = self._start_windows_session(shell, cwd_path) if sys.platform == "win32" else self._start_unix_session(shell, cwd_path)
        session.title = title or Path(shlex.split(shell)[0]).name
        session.description = description or ""
        session.watch_path = str(Path(watch_path or cwd_path).expanduser().resolve())
        if self.ai_detector:
            session.ai_info = self.ai_detector.detect_process(session.pid)
        if self.code_watcher and session.watch_path:
            self.code_watcher.start_watching(session.id, session.watch_path)
        return session

    def _start_unix_session(self, shell: str, cwd: Path) -> TerminalSession:
        master_fd, slave_fd = pty.openpty()
        command = shlex.split(shell)
        process = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=str(cwd),
            close_fds=True,
            start_new_session=True,
        )
        os.close(slave_fd)
        session = TerminalSession(
            id=str(uuid.uuid4()),
            title="",
            description="",
            shell=shell,
            cwd=str(cwd),
            pid=process.pid,
            created_at=time.time(),
            log_max_lines=self.log_max_lines,
            _master_fd=master_fd,
            _process=process,
        )
        session._read_thread = threading.Thread(target=self._reader_loop, args=(session,), daemon=True)
        session._read_thread.start()
        return session

    def _start_windows_session(self, shell: str, cwd: Path) -> TerminalSession:
        session = TerminalSession(
            id=str(uuid.uuid4()),
            title="",
            description="",
            shell=shell,
            cwd=str(cwd),
            pid=0,
            created_at=time.time(),
            log_max_lines=self.log_max_lines,
        )
        try:
            import winpty  # type: ignore

            pty_process = winpty.PtyProcess.spawn(shell, cwd=str(cwd))
            session.pid = pty_process.pid
            session._pty_process = pty_process
            session._use_winpty = True
        except Exception:
            process = subprocess.Popen(
                [shell],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(cwd),
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            session.pid = process.pid
            session._process = process
        session._read_thread = threading.Thread(target=self._reader_loop, args=(session,), daemon=True)
        session._read_thread.start()
        return session

    def _reader_loop(self, session: TerminalSession) -> None:
        """Read PTY output in a tight background thread and broadcast to all WebSocket callbacks.

        Performance notes:
        - 64 KB read buffer reduces syscall frequency for burst output.
        - select() timeout of 5 ms only controls aliveness-check cadence;
          it returns immediately the moment data is available so it does NOT
          add latency to live output.
        - winpty sleep reduced from 100 ms to 5 ms for the same reason.
        """
        READ_BUF = 65536  # 64 KB
        SELECT_TIMEOUT = 0.005  # 5 ms
        try:
            while True:
                if session._use_winpty and session._pty_process is not None:
                    try:
                        chunk = session._pty_process.read(READ_BUF)
                    except Exception:
                        chunk = ""
                    if not chunk:
                        if not session.is_alive():
                            break
                        time.sleep(SELECT_TIMEOUT)
                        continue
                    text = chunk if isinstance(chunk, str) else chunk.decode("utf-8", errors="replace")
                elif session._master_fd is not None:
                    ready, _, _ = select.select([session._master_fd], [], [], SELECT_TIMEOUT)
                    if not ready:
                        if not session.is_alive():
                            break
                        continue
                    data = os.read(session._master_fd, READ_BUF)
                    if not data:
                        if not session.is_alive():
                            break
                        continue
                    text = data.decode("utf-8", errors="replace")
                else:
                    if not session._process or not session._process.stdout:
                        break
                    data = session._process.stdout.read(READ_BUF)
                    if not data:
                        if not session.is_alive():
                            break
                        time.sleep(SELECT_TIMEOUT)
                        continue
                    text = data.decode("utf-8", errors="replace")

                session.append_output(text)
                session.broadcast({"type": "output", "data": text})
        except Exception:
            pass
        finally:
            session.broadcast({"type": "status", "connected": False})

    async def kill(self, tid: str) -> bool:
        import asyncio

        with self._lock:
            session = self.sessions.pop(tid, None)
        if not session:
            return False
        if self.code_watcher:
            self.code_watcher.stop_watching(tid)
        await asyncio.get_running_loop().run_in_executor(None, session.close)
        return True

    def get(self, tid: str) -> Optional[TerminalSession]:
        with self._lock:
            return self.sessions.get(tid)

    def list_all(self) -> list[dict[str, Any]]:
        with self._lock:
            sessions = list(self.sessions.values())
        return [
            {
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "shell": s.shell,
                "cwd": s.cwd,
                "pid": s.pid,
                "created_at": s.created_at,
                "connected": s.connected,
                "watch_path": s.watch_path,
                "ai_info": s.ai_info,
                "alive": s.is_alive(),
            }
            for s in sessions
        ]
