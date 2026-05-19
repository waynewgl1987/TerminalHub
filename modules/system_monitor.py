from __future__ import annotations

import threading
import time
from typing import Any

import psutil


class SystemMonitor:
    def __init__(self, ttl: float = 2.0) -> None:
        self.ttl = ttl
        self._lock = threading.Lock()
        self._process_refs: dict[int, psutil.Process] = {}
        # Separate cache for CPU (needs real time between readings) vs other stats
        self._cpu_cache: dict[int, float] = {}          # pid → last cpu%
        self._stats_cache: dict[int, tuple[float, dict[str, Any]]] = {}
        self._system_stats: tuple[float, dict[str, Any]] = (0.0, {})

        # Background sampler: calls cpu_percent(interval=None) every `ttl`
        # seconds. Because psutil measures CPU% since the LAST call on that
        # process object, successive calls separated by a real interval give
        # accurate readings (unlike two back-to-back calls which always → 0%).
        self._stop_event = threading.Event()
        self._sampler = threading.Thread(target=self._sample_loop, daemon=True, name="cpu-sampler")
        self._sampler.start()

    # ── Background CPU sampler ────────────────────────────────────────────────

    def _sample_loop(self) -> None:
        while not self._stop_event.wait(timeout=self.ttl):
            with self._lock:
                pids = list(self._process_refs.keys())
            for pid in pids:
                try:
                    with self._lock:
                        proc = self._process_refs.get(pid)
                    if proc:
                        pct = round(proc.cpu_percent(interval=None), 2)
                        with self._lock:
                            self._cpu_cache[pid] = pct
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    with self._lock:
                        self._process_refs.pop(pid, None)
                        self._cpu_cache.pop(pid, None)
            # Also refresh system CPU
            try:
                pct = round(psutil.cpu_percent(interval=None), 2)
                with self._lock:
                    ts, cached = self._system_stats
                    self._system_stats = (time.time(), {**cached, "cpu_pct": pct})
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_event.set()

    # ── Process registration ──────────────────────────────────────────────────

    def _get_process(self, pid: int) -> psutil.Process:
        with self._lock:
            proc = self._process_refs.get(pid)
            if proc is None:
                proc = psutil.Process(pid)
                # Prime the counter so the background sampler's NEXT call returns real data
                proc.cpu_percent(interval=None)
                self._process_refs[pid] = proc
            return proc

    # ── Public API ────────────────────────────────────────────────────────────

    def get_process_stats(self, pid: int) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            cached = self._stats_cache.get(pid)
            if cached and now - cached[0] < self.ttl:
                return dict(cached[1])

        try:
            proc = self._get_process(pid)
            with self._lock:
                cpu = self._cpu_cache.get(pid, 0.0)
            stats = {
                "cpu_pct": cpu,
                "mem_mb": round(proc.memory_info().rss / 1024 / 1024, 2),
                "mem_pct": round(proc.memory_percent(), 2),
                "status": proc.status(),
                "threads": proc.num_threads(),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            stats = {
                "cpu_pct": 0.0,
                "mem_mb": 0.0,
                "mem_pct": 0.0,
                "status": "dead",
                "threads": 0,
            }
            with self._lock:
                self._process_refs.pop(pid, None)
                self._cpu_cache.pop(pid, None)

        with self._lock:
            self._stats_cache[pid] = (now, stats)
        return dict(stats)

    def get_system_stats(self) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            ts, cached = self._system_stats
            if cached and now - ts < self.ttl:
                return dict(cached)

        memory = psutil.virtual_memory()
        stats = {
            # cpu_pct is updated by the background sampler; use cached value.
            # On first call before sampler runs, psutil.cpu_percent(None) is 0 — that's fine.
            "cpu_pct": round(psutil.cpu_percent(interval=None), 2),
            "mem_total_gb": round(memory.total / 1024 / 1024 / 1024, 2),
            "mem_used_gb": round(memory.used / 1024 / 1024 / 1024, 2),
            "mem_pct": round(memory.percent, 2),
        }
        with self._lock:
            self._system_stats = (now, stats)
        return dict(stats)
