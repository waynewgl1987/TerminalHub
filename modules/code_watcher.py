"""On-demand code-change detector.

Instead of watching the file system in real time (which caused FSEvents
thread errors and high resource usage), changes are computed via ``git diff
HEAD`` only when explicitly requested – typically at report-export time.

Public API (unchanged from the previous watchdog-based version):
  start_watching(terminal_id, path)  – record the watch path for a terminal
  stop_watching(terminal_id)         – forget the watch path
  get_changes(terminal_id)           – full diff list (slow, call sparingly)
  count_changes(terminal_id)         – fast file-count for UI badge
  clear_changes(terminal_id)         – discard cached result
  record_change(...)                 – no-op stub kept for compat
"""
from __future__ import annotations

import difflib
import html
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".swift", ".kt", ".java", ".go", ".rs",
    ".cpp", ".cc", ".c", ".h", ".hpp", ".css", ".scss", ".html", ".json", ".yml",
    ".yaml", ".sh", ".rb", ".php", ".cs", ".vue", ".sql", ".md",
}
IGNORED_DIR_NAMES = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
MAX_CAPTURE_CHARS = 200_000
CACHE_TTL = 120  # seconds – re-use cached badge count to avoid git calls every tick

LANGUAGE_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".tsx": "tsx", ".jsx": "jsx", ".swift": "swift", ".kt": "kotlin",
    ".java": "java", ".go": "go", ".rs": "rust", ".cpp": "cpp",
    ".cc": "cpp", ".c": "c", ".h": "c", ".hpp": "cpp", ".css": "css",
    ".scss": "scss", ".html": "html", ".json": "json", ".yml": "yaml",
    ".yaml": "yaml", ".sh": "bash", ".rb": "ruby", ".php": "php",
    ".cs": "csharp", ".vue": "vue", ".sql": "sql", ".md": "markdown",
}


class CodeWatcher:
    """Lazily computes code changes via git diff – no background threads."""

    def __init__(self, base_dir: Path, file_pattern: str) -> None:
        self.base_dir = Path(base_dir)
        self.file_pattern = file_pattern  # kept for API compat, unused
        self._lock = threading.Lock()
        self._watch_paths: dict[str, str] = {}          # terminal_id → abs path
        self._cache: dict[str, tuple[float, list]] = {} # terminal_id → (ts, changes)
        self._count_cache: dict[str, tuple[float, int]] = {}  # terminal_id → (ts, count)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start_watching(self, terminal_id: str, path: str) -> None:
        """Record the watch path.  No threads are started."""
        watch_path = Path(path).expanduser().resolve()
        if watch_path.exists():
            with self._lock:
                self._watch_paths[terminal_id] = str(watch_path)
                self._cache.pop(terminal_id, None)
                self._count_cache.pop(terminal_id, None)

    def stop_watching(self, terminal_id: str) -> None:
        with self._lock:
            self._watch_paths.pop(terminal_id, None)
            self._cache.pop(terminal_id, None)
            self._count_cache.pop(terminal_id, None)

    # ── public query API ──────────────────────────────────────────────────────

    def get_changes(self, terminal_id: str, force: bool = False) -> list[dict[str, Any]]:
        """Return full diff list.  Results are cached for CACHE_TTL seconds.

        Pass ``force=True`` (e.g. at report-export time) to bypass the cache.
        """
        with self._lock:
            watch_path = self._watch_paths.get(terminal_id)
            cached = self._cache.get(terminal_id)

        if watch_path is None:
            return []

        if not force and cached and (time.time() - cached[0]) < CACHE_TTL:
            return cached[1]

        changes = self._compute_git_changes(terminal_id, Path(watch_path))
        with self._lock:
            self._cache[terminal_id] = (time.time(), changes)
            self._count_cache[terminal_id] = (time.time(), len(changes))
        return changes

    def count_changes(self, terminal_id: str) -> int:
        """Fast change-file count for the UI badge (cached, uses git --name-only)."""
        with self._lock:
            watch_path = self._watch_paths.get(terminal_id)
            cached = self._count_cache.get(terminal_id)

        if watch_path is None:
            return 0

        if cached and (time.time() - cached[0]) < CACHE_TTL:
            return cached[1]

        count = self._fast_count(Path(watch_path))
        with self._lock:
            self._count_cache[terminal_id] = (time.time(), count)
        return count

    def clear_changes(self, terminal_id: str) -> None:
        with self._lock:
            self._cache.pop(terminal_id, None)
            self._count_cache.pop(terminal_id, None)

    # ── stub kept for backward compatibility ──────────────────────────────────

    def record_change(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
        """No-op – real-time recording is disabled."""

    def should_ignore_path(self, path: Path) -> bool:
        resolved = path.expanduser().resolve(strict=False)
        return any(part in IGNORED_DIR_NAMES for part in resolved.parts)

    # ── internals ─────────────────────────────────────────────────────────────

    def _git_root(self, start: Path) -> Path | None:
        proc = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return Path(proc.stdout.strip())
        return None

    def _find_git_repos(self, root: Path, max_depth: int = 2) -> list[Path]:
        """Find all git repo roots under *root* up to *max_depth* levels deep.

        Stops descending into a directory once a .git folder is found there
        (no nested repos). Skips hidden dirs and common noise folders.
        """
        repos: list[Path] = []
        _skip = IGNORED_DIR_NAMES | {"Library", "Applications", "go", "opt"}

        def _scan(path: Path, depth: int) -> None:
            if depth > max_depth:
                return
            try:
                if (path / ".git").is_dir():
                    repos.append(path)
                    return  # don't recurse into a git repo
                for child in sorted(path.iterdir()):
                    if child.is_dir() and child.name not in _skip and not child.name.startswith("."):
                        _scan(child, depth + 1)
            except (PermissionError, OSError):
                pass

        _scan(root, 0)
        return repos

    def _fast_count(self, root: Path) -> int:
        """Count changed files via git diff HEAD --name-only (one subprocess).

        Falls back to counting recently modified files (mtime < 1 h) when no
        git repo is found.
        """
        repo_root = self._git_root(root)
        repos = [repo_root] if repo_root else self._find_git_repos(root)
        if repos:
            total = 0
            for repo in repos:
                proc = subprocess.run(
                    ["git", "-C", str(repo), "diff", "HEAD", "--name-only"],
                    capture_output=True, text=True, timeout=15,
                )
                if proc.returncode == 0:
                    total += sum(
                        1 for f in proc.stdout.splitlines()
                        if Path(f).suffix.lower() in CODE_EXTENSIONS
                    )
                # Count untracked new files too
                st = subprocess.run(
                    ["git", "-C", str(repo), "status", "--porcelain"],
                    capture_output=True, text=True, timeout=15,
                )
                if st.returncode == 0:
                    for line in st.stdout.splitlines():
                        if line[:2].strip() == "??" and Path(line[3:].strip()).suffix.lower() in CODE_EXTENSIONS:
                            total += 1
            return total
        # Filesystem fallback
        cutoff = time.time() - 3600
        count = 0
        try:
            for f in root.rglob("*"):
                if f.is_file() and f.suffix.lower() in CODE_EXTENSIONS and not self.should_ignore_path(f):
                    try:
                        if f.stat().st_mtime >= cutoff:
                            count += 1
                    except OSError:
                        pass
        except (PermissionError, OSError):
            pass
        return count

    def _compute_git_changes(self, terminal_id: str, root: Path) -> list[dict[str, Any]]:
        """Compute full diffs for all files changed since HEAD.

        If *root* is not itself a git repo, scans subdirectories for repos
        (up to 2 levels deep) and aggregates changes from all of them.
        If no git repos are found at all, falls back to a filesystem scan
        for recently modified code files.
        """
        repo_root = self._git_root(root)
        repos = [repo_root] if repo_root else self._find_git_repos(root)
        if repos:
            all_changes: list[dict[str, Any]] = []
            for r in repos:
                all_changes.extend(self._changes_in_repo(terminal_id, r))
            return all_changes

        # No git repo found — fall back to filesystem scan (mtime < 1 h)
        return self._scan_dir_changes(terminal_id, root)

    def _changes_in_repo(self, terminal_id: str, repo_root: Path) -> list[dict[str, Any]]:
        """Collect changed files for one git repo.

        Covers three cases:
        1. Normal repo with commits  → git diff HEAD + untracked files from git status
        2. Fresh repo (no commits)   → git status --porcelain only (all files are new)
        3. Untracked new files       → included via git status ?
        """
        head_hash = ""
        head_proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        has_head = head_proc.returncode == 0
        if has_head:
            head_hash = head_proc.stdout.strip()

        changes: list[dict[str, Any]] = []
        seen_paths: set[str] = set()

        # ── 1. Tracked changes (modified / added / deleted vs HEAD) ───────────
        if has_head:
            status_proc = subprocess.run(
                ["git", "-C", str(repo_root), "diff", "HEAD", "--name-status"],
                capture_output=True, text=True, timeout=30,
            )
            if status_proc.returncode == 0:
                for line in status_proc.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("\t", 1)
                    if len(parts) < 2:
                        continue
                    status_char = parts[0][0]
                    file_rel = parts[1].strip()
                    file_path = repo_root / file_rel
                    if file_path.suffix.lower() not in CODE_EXTENSIONS:
                        continue
                    if self.should_ignore_path(file_path):
                        continue
                    change_type = {"A": "created", "D": "deleted"}.get(status_char, "modified")
                    before = ""
                    if status_char != "A":
                        try:
                            show = subprocess.run(
                                ["git", "-C", str(repo_root), "show", f"HEAD:{file_rel}"],
                                capture_output=True, text=True, timeout=10,
                            )
                            if show.returncode == 0:
                                before = show.stdout
                        except Exception:
                            pass
                    after = ""
                    if change_type != "deleted" and file_path.exists():
                        try:
                            after = file_path.read_text(encoding="utf-8", errors="replace")
                        except Exception:
                            pass
                    before = self._normalize(before)
                    after = self._normalize(after)
                    if before == after:
                        continue
                    language = LANGUAGE_MAP.get(file_path.suffix.lower(), "text")
                    diff_lines = list(difflib.unified_diff(
                        before.splitlines(), after.splitlines(),
                        fromfile=f"before/{file_path.name}",
                        tofile=f"after/{file_path.name}",
                        lineterm="",
                    ))
                    changes.append({
                        "terminal_id": terminal_id,
                        "file_path": str(file_path),
                        "change_type": change_type,
                        "before": before,
                        "after": after,
                        "diff": "\n".join(diff_lines),
                        "diff_html": self._diff_to_html(diff_lines),
                        "timestamp": time.time(),
                        "git_commit": head_hash,
                        "language": language,
                    })
                    seen_paths.add(str(file_path))

        # ── 2. Untracked new files (git status --porcelain lines starting with ??) ─
        porcelain = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=30,
        )
        if porcelain.returncode == 0:
            for line in porcelain.stdout.splitlines():
                if not line:
                    continue
                xy = line[:2]
                file_rel = line[3:].strip()
                # ?? = untracked; also include staged-new (A ) and staged-modified (M)
                if xy.strip() in ("??", "A", "M", "AM", "MM") or xy[0] in ("A", "M"):
                    file_path = repo_root / file_rel
                    if str(file_path) in seen_paths:
                        continue
                    if file_path.suffix.lower() not in CODE_EXTENSIONS:
                        continue
                    if self.should_ignore_path(file_path):
                        continue
                    if not file_path.exists():
                        continue
                    try:
                        after = self._normalize(file_path.read_text(encoding="utf-8", errors="replace"))
                    except Exception:
                        continue
                    # For untracked files there is no "before"
                    before = ""
                    if before == after:
                        continue
                    language = LANGUAGE_MAP.get(file_path.suffix.lower(), "text")
                    diff_lines = list(difflib.unified_diff(
                        [], after.splitlines(),
                        fromfile="(new file)",
                        tofile=file_path.name,
                        lineterm="",
                    ))
                    changes.append({
                        "terminal_id": terminal_id,
                        "file_path": str(file_path),
                        "change_type": "created",
                        "before": "",
                        "after": after,
                        "diff": "\n".join(diff_lines),
                        "diff_html": self._diff_to_html(diff_lines),
                        "timestamp": time.time(),
                        "git_commit": head_hash,
                        "language": language,
                    })
                    seen_paths.add(str(file_path))

        return changes

    def _scan_dir_changes(self, terminal_id: str, root: Path,
                          since_ts: float | None = None) -> list[dict[str, Any]]:
        """Filesystem fallback: collect code files modified recently under *root*.

        Used when no git repo is found.  Returns files whose mtime is newer than
        *since_ts* (defaults to 1 hour ago).
        """
        cutoff = since_ts if since_ts is not None else time.time() - 3600
        changes: list[dict[str, Any]] = []
        try:
            for file_path in root.rglob("*"):
                if not file_path.is_file():
                    continue
                if file_path.suffix.lower() not in CODE_EXTENSIONS:
                    continue
                if self.should_ignore_path(file_path):
                    continue
                try:
                    mtime = file_path.stat().st_mtime
                except OSError:
                    continue
                if mtime < cutoff:
                    continue
                try:
                    after = self._normalize(file_path.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    continue
                language = LANGUAGE_MAP.get(file_path.suffix.lower(), "text")
                diff_lines = list(difflib.unified_diff(
                    [], after.splitlines(),
                    fromfile="(new file)",
                    tofile=file_path.name,
                    lineterm="",
                ))
                changes.append({
                    "terminal_id": terminal_id,
                    "file_path": str(file_path),
                    "change_type": "created",
                    "before": "",
                    "after": after,
                    "diff": "\n".join(diff_lines),
                    "diff_html": self._diff_to_html(diff_lines),
                    "timestamp": time.time(),
                    "git_commit": "",
                    "language": language,
                })
        except (PermissionError, OSError):
            pass
        return changes

    def _normalize(self, content: str) -> str:
        if len(content) <= MAX_CAPTURE_CHARS:
            return content
        return content[:MAX_CAPTURE_CHARS] + "\n\n[TerminalHub truncated large file content]"

    def _diff_to_html(self, diff_lines: list[str]) -> str:
        rendered = []
        for line in diff_lines:
            if line.startswith("+++") or line.startswith("---"):
                css = "diff-file"
            elif line.startswith("@@"):
                css = "diff-hunk"
            elif line.startswith("+"):
                css = "diff-add"
            elif line.startswith("-"):
                css = "diff-remove"
            else:
                css = "diff-context"
            rendered.append(f'<div class="{css}">{html.escape(line)}</div>')
        return "".join(rendered)

    # ── resolve_git_before kept for compat with any callers ──────────────────

    def resolve_git_before(self, file_path: Path) -> tuple[str, str]:
        repo_root = self._git_root(file_path.parent)
        if not repo_root:
            return "", ""
        try:
            rel_path = file_path.resolve().relative_to(repo_root)
        except ValueError:
            rel_path = Path(file_path.name)
        show = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"HEAD:{rel_path.as_posix()}"],
            capture_output=True, text=True, timeout=5,
        )
        before = show.stdout if show.returncode == 0 else ""
        head = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        commit = head.stdout.strip() if head.returncode == 0 else ""
        return before, commit
