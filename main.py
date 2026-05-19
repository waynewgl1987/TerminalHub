from __future__ import annotations

import asyncio
import configparser
import contextlib
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# ── uvloop: 2-4× faster asyncio event loop (Unix only) ───────────────────────
try:
    import uvloop  # type: ignore
    uvloop.install()
except ImportError:
    pass

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from modules import AIDetector, CodeWatcher, ContextStore, EmailSender, ReportGenerator, SystemMonitor, TerminalManager
from modules.ai_provider import call_llm, get_copilot_models, get_job_status, start_chat_job, test_provider

BASE_DIR = Path(__file__).resolve().parent
config = configparser.ConfigParser()
config.read(BASE_DIR / "config.ini", encoding="utf-8")

APP_NAME = config.get("app", "name", fallback="TerminalHub")
APP_VERSION = config.get("app", "version", fallback="v1.0.0")
APP_HOST = config.get("app", "host", fallback="0.0.0.0")
APP_PORT = int(os.environ.get("TERMINALHUB_PORT", config.getint("app", "port", fallback=8765)))
DEFAULT_SHELL_UNIX = config.get("app", "default_shell_unix", fallback="/bin/zsh")
DEFAULT_SHELL_WINDOWS = config.get("app", "default_shell_windows", fallback="cmd.exe")
DEFAULT_LANG = config.get("app", "default_lang", fallback="zh")
DEFAULT_THEME = config.get("app", "default_theme", fallback="light")
STATS_INTERVAL = config.getfloat("monitoring", "stats_interval", fallback=2.0)
LOG_MAX_LINES = config.getint("monitoring", "log_max_lines", fallback=5000)
CODE_CHANGES_FILE = config.get("monitoring", "code_changes_file", fallback="tmp/code_changes_{terminal_id}.json")
DEFAULT_SMTP = {
    "smtp_host": config.get("email", "smtp_host", fallback="smtp.gmail.com"),
    "smtp_port": config.getint("email", "smtp_port", fallback=587),
    "smtp_user": config.get("email", "smtp_user", fallback=""),
    "smtp_pass": config.get("email", "smtp_pass", fallback=""),
}

PROVIDER_LABELS = {
    "copilot": "GitHub Copilot",
    "openai": "OpenAI",
    "anthropic": "Anthropic Claude",
    "deepseek": "DeepSeek",
    "qwen": "Qwen",
    "ollama": "Ollama",
    "custom": "Custom OpenAI-Compatible",
}

DEFAULT_MODELS = {
    "openai": ["gpt-4o", "gpt-4.1", "gpt-4o-mini"],
    "anthropic": ["claude-3-7-sonnet-latest", "claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "qwen": ["qwen-plus", "qwen-turbo", "qwq-plus"],
    "ollama": ["llama3.1", "qwen2.5-coder", "deepseek-r1"],
    "custom": ["gpt-4o", "claude-3-5-sonnet", "deepseek-chat"],
}

@asynccontextmanager
async def lifespan(_: FastAPI):
    (BASE_DIR / "tmp").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "tmp" / "reports").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "tmp" / "contexts").mkdir(parents=True, exist_ok=True)
    context_store.attach(terminal_manager.sessions)
    monitor_task = asyncio.create_task(monitor_broadcast_loop())
    try:
        yield
    finally:
        monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor_task
        # Flush all live sessions to disk before shutdown
        for tid, session in list(terminal_manager.sessions.items()):
            context_store.flush(tid, session, code_watcher.count_changes(tid))
        context_store.stop()
        for tid in list(terminal_manager.sessions.keys()):
            with contextlib.suppress(Exception):
                await terminal_manager.kill(tid)


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
# Ensure reports dir exists before mounting (lifespan runs after app construction)
_reports_dir = BASE_DIR / "tmp" / "reports"
_reports_dir.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(_reports_dir)), name="reports")

ai_detector = AIDetector()
code_watcher = CodeWatcher(BASE_DIR, CODE_CHANGES_FILE)
system_monitor = SystemMonitor(ttl=STATS_INTERVAL)
email_sender = EmailSender()
report_generator = ReportGenerator()
context_store = ContextStore(BASE_DIR / "tmp" / "contexts")
terminal_manager = TerminalManager(
    default_shell_unix=DEFAULT_SHELL_UNIX,
    default_shell_windows=DEFAULT_SHELL_WINDOWS,
    log_max_lines=LOG_MAX_LINES,
    code_watcher=code_watcher,
    ai_detector=ai_detector,
)
monitor_clients: set[WebSocket] = set()


class TerminalCreateRequest(BaseModel):
    shell: str | None = None
    cwd: str | None = None
    title: str | None = None
    description: str | None = None
    watch_path: str | None = None


class TerminalUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None


class ReportRequest(BaseModel):
    terminal_id: str
    lang: str = DEFAULT_LANG
    include_ai_analysis: bool = False
    ai_provider_config: dict[str, Any] | None = None


class EmailRequest(BaseModel):
    to: str
    subject: str
    html: str
    smtp_config: dict[str, Any] | None = None


class AITestRequest(BaseModel):
    provider: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class AIChatRequest(AITestRequest):
    messages: list[dict[str, str]]


class ApplyChangeRequest(BaseModel):
    sidecar_id: str
    change_index: int
    action: str  # "accept" or "reject"


def _git(args: list[str], cwd: str) -> tuple[int, str]:
    """Run a git command; returns (returncode, stripped stdout)."""
    import subprocess
    try:
        r = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=10
        )
        return r.returncode, r.stdout.strip()
    except Exception:
        return -1, ""


@app.get("/", response_class=FileResponse)
async def root() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/terminals")
async def list_terminals() -> list[dict[str, Any]]:
    return enrich_terminal_list()


@app.post("/api/terminals")
async def create_terminal(request: TerminalCreateRequest) -> dict[str, Any]:
    session = await terminal_manager.create(
        shell=request.shell,
        cwd=request.cwd,
        title=request.title,
        description=request.description,
        watch_path=request.watch_path,
    )
    return serialize_session(session)


@app.delete("/api/terminals/{tid}")
async def delete_terminal(tid: str) -> dict[str, bool]:
    ok = await terminal_manager.kill(tid)
    if not ok:
        raise HTTPException(status_code=404, detail="Terminal not found")
    return {"ok": True}


@app.patch("/api/terminals/{tid}")
async def update_terminal(tid: str, request: TerminalUpdateRequest) -> dict[str, Any]:
    session = terminal_manager.get(tid)
    if not session:
        raise HTTPException(status_code=404, detail="Terminal not found")
    if request.title is not None:
        session.title = request.title
    if request.description is not None:
        session.description = request.description
    return serialize_session(session)


@app.get("/api/terminals/{tid}/log")
async def get_terminal_log(tid: str) -> dict[str, Any]:
    session = terminal_manager.get(tid)
    if not session:
        raise HTTPException(status_code=404, detail="Terminal not found")
    return {"terminal_id": tid, "log": "".join(session.full_log())}


@app.get("/api/contexts")
async def list_contexts() -> list[dict[str, Any]]:
    """Return all persisted terminal contexts (survives service restarts)."""
    return context_store.list_contexts()


@app.get("/api/contexts/{tid}")
async def get_context(tid: str) -> dict[str, Any]:
    """Return the persisted context for a specific terminal."""
    ctx = context_store.load(tid)
    if not ctx:
        raise HTTPException(status_code=404, detail="Context not found")
    return ctx


@app.delete("/api/contexts/{tid}")
async def delete_context(tid: str) -> dict[str, bool]:
    context_store.delete(tid)
    return {"ok": True}


@app.websocket("/ws/terminal/{tid}")
async def terminal_socket(websocket: WebSocket, tid: str) -> None:
    session = terminal_manager.get(tid)
    if not session:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    loop = asyncio.get_running_loop()

    # ── Per-connection PRIORITY output queue ─────────────────────────────────
    # Items: (priority, seq, payload) — lower number = dequeued first.
    #   priority 0: pong  (control, must bypass all queued output)
    #   priority 1: everything else (output, stats, status, ai_info)
    # seq guarantees stable FIFO ordering within the same priority level.
    # The PriorityQueue fix is the key change: previously pong shared the same
    # plain Queue as terminal output, so it had to wait behind all buffered
    # PTY chunks before being sent, making the latency indicator show 200-400ms
    # instead of the true WS RTT of ~1-5ms on localhost.
    pq: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=4096)
    _seq = 0

    def enqueue(payload: dict[str, Any], priority: int = 1) -> None:
        nonlocal _seq
        _seq += 1
        try:
            pq.put_nowait((priority, _seq, payload))
        except asyncio.QueueFull:
            pass  # drop under extreme back-pressure; avoids blocking the reader thread

    def callback(payload: dict[str, Any]) -> None:
        # thread-safe; wakes the event loop via an internal pipe write (O(1))
        loop.call_soon_threadsafe(enqueue, payload)

    session.add_output_callback(callback)

    # Seed with initial state (priority 1)
    enqueue({"type": "status", "connected": session.is_alive()})
    enqueue({"type": "ai_info", **session.ai_info})
    backlog = "".join(session.tail_log(200))
    if backlog:
        enqueue({"type": "output", "data": backlog})

    # ── Single consumer: pong-priority aware + greedy output batching ─────────
    # Batching: when output chunks pile up in the queue we drain all immediately
    # available ones and concatenate them into a single WS frame.  This halves
    # the frame count for TUI apps (like Copilot CLI) that repaint frequently.
    async def output_consumer() -> None:
        while True:
            _, _, payload = await pq.get()
            pq.task_done()

            if payload.get("type") == "output":
                # Greedy drain: keep pulling output chunks that are already
                # in the queue without waiting (get_nowait).  Non-output items
                # break the batch and are sent immediately.
                data = payload["data"]
                while True:
                    try:
                        _, _, nxt = pq.get_nowait()
                        pq.task_done()
                        if nxt.get("type") == "output":
                            data += nxt["data"]
                        else:
                            # flush accumulated output first, then the control msg
                            with contextlib.suppress(Exception):
                                await websocket.send_json({"type": "output", "data": data})
                            with contextlib.suppress(Exception):
                                await websocket.send_json(nxt)
                            data = None
                            break
                    except asyncio.QueueEmpty:
                        break
                if data is not None:
                    with contextlib.suppress(Exception):
                        await websocket.send_json({"type": "output", "data": data})
            else:
                with contextlib.suppress(Exception):
                    await websocket.send_json(payload)

    consumer_task = asyncio.create_task(output_consumer())
    updates_task = asyncio.create_task(periodic_terminal_updates(enqueue, session))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg_type = message.get("type")
            if msg_type == "input":
                # os.write() to PTY kernel buffer — non-blocking for small payloads
                session.write_input(message.get("data", ""))
            elif msg_type == "resize":
                rows = int(message.get("rows") or 0)
                cols = int(message.get("cols") or 0)
                session.resize(rows, cols)
            elif msg_type == "ping":
                # Priority 0: jumps ahead of all buffered output in the queue.
                # This gives a true WS RTT measurement instead of queue drain time.
                enqueue({"type": "pong", "t": message.get("t", 0)}, priority=0)
    except WebSocketDisconnect:
        pass
    finally:
        consumer_task.cancel()
        updates_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consumer_task
        with contextlib.suppress(asyncio.CancelledError):
            await updates_task
        session.remove_output_callback(callback)


@app.websocket("/ws/monitor")
async def monitor_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    monitor_clients.add(websocket)
    await websocket.send_json(build_monitor_payload())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        monitor_clients.discard(websocket)


@app.get("/api/code-changes/{tid}")
async def get_code_changes(tid: str) -> dict[str, Any]:
    return {"terminal_id": tid, "changes": code_watcher.get_changes(tid)}


@app.post("/api/terminals/{tid}/resolve-path")
async def resolve_file_path(tid: str, request: Request) -> dict[str, Any]:
    """Resolve a dropped file/folder name to its absolute path.

    Search order:
      1. Shell's actual cwd (via psutil.Process.cwd — tracks cd changes)
      2. Terminal's configured watch_path / initial cwd
      3. Home directory (depth-limited to 4)
    """
    import psutil

    body = await request.json()
    name: str = body.get("name", "").strip()
    size: int | None = body.get("size")  # None for folders
    if not name:
        raise HTTPException(status_code=400, detail="name required")

    session = terminal_manager.get(tid)
    search_roots: list[Path] = []

    # 1. Actual shell cwd — most accurate because it follows `cd` commands
    if session:
        try:
            proc_cwd = Path(psutil.Process(session.pid).cwd())
            search_roots.append(proc_cwd)
        except Exception:
            pass
        # 2. Configured roots
        for attr in ("cwd", "watch_path"):
            val = getattr(session, attr, None)
            if val:
                search_roots.append(Path(val).expanduser())

    # 3. Home directory fallback
    search_roots.append(Path.home())

    seen: set[Path] = set()
    for root in search_roots:
        root = root.resolve() if root.exists() else root
        if root in seen or not root.exists():
            continue
        seen.add(root)
        # Fast exact-child check before doing a deep rglob
        direct = root / name
        if direct.exists():
            return {"path": str(direct)}
        try:
            for candidate in root.rglob(name):
                if candidate.name != name:
                    continue
                if size is not None and candidate.is_file() and candidate.stat().st_size != size:
                    continue
                return {"path": str(candidate)}
        except (PermissionError, OSError):
            pass

    return {"path": None}  # let JS fall back gracefully


@app.post("/api/report/generate", response_class=HTMLResponse)
async def generate_report(request: ReportRequest) -> HTMLResponse:
    import time, psutil as _psutil
    session = terminal_manager.get(request.terminal_id)
    if not session:
        raise HTTPException(status_code=404, detail="Terminal not found")

    # Determine the best search root for code changes.
    # Priority: actual shell process cwd (follows `cd`) > watch_path > initial cwd > home.
    # Using the live cwd prevents scanning unrelated git repos that happen to be
    # under a broad root like $HOME.
    search_root = session.watch_path or session.cwd or str(Path.home())
    try:
        proc_cwd = _psutil.Process(session.pid).cwd()
        if proc_cwd and Path(proc_cwd).is_dir():
            search_root = proc_cwd
    except Exception:
        pass

    # Always register/update the watch path so code_watcher scans the right dir.
    code_watcher.start_watching(request.terminal_id, search_root)
    try:
        code_changes = await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                None, lambda: code_watcher.get_changes(request.terminal_id, force=True)
            ),
            timeout=45.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail=(
                f"代码扫描超时（目录 '{search_root}' 文件过多）。请缩小监控目录范围后重试。"
                if request.lang == "zh"
                else f"Code scan timed out for '{search_root}'. The directory may have too many files."
            ),
        )
    if not code_changes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"未检测到代码变更。请确保 '{search_root}' 目录下有最近修改的代码文件。"
                if request.lang == "zh"
                else f"No code changes detected in '{search_root}'. Make sure code files have been recently modified."
            ),
        )

    ai_summary = ""
    config_payload = request.ai_provider_config or {}
    if request.include_ai_analysis and config_payload.get("provider") and config_payload.get("model"):
        prompt = [
            {"role": "system", "content": "You summarize terminal sessions and code changes concisely."},
            {
                "role": "user",
                "content": (
                    f"Title: {session.title}\nDescription: {session.description}\n"
                    f"Log excerpt:\n{''.join(session.tail_log(120))}\n\n"
                    f"Code changes:\n{json.dumps(code_changes[:10], ensure_ascii=False)[:12000]}\n\n"
                    "Summarize the goal, notable code changes, and any risks."
                ),
            },
        ]
        try:
            ai_summary = await asyncio.wait_for(
                asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: call_llm(
                        config_payload.get("provider", ""),
                        config_payload.get("api_key", ""),
                        config_payload.get("base_url", ""),
                        config_payload.get("model", ""),
                        prompt,
                    )[1],
                ),
                timeout=90.0,
            )
        except asyncio.TimeoutError:
            ai_summary = "[AI summary timed out after 90s]"
    ts = int(time.time())
    sidecar_id = f"sidecar_{request.terminal_id[:8]}_{ts}"
    sidecar_path = BASE_DIR / "tmp" / "reports" / f"{sidecar_id}.json"
    sidecar_path.write_text(json.dumps(code_changes, ensure_ascii=False), encoding="utf-8")

    # ── Git info for the session directory ───────────────────────────────────
    git_info: dict[str, Any] = {"is_git": False}
    rc, _ = _git(["rev-parse", "--is-inside-work-tree"], search_root)
    if rc == 0:
        _, branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], search_root)
        _, commit = _git(["rev-parse", "--short", "HEAD"], search_root)
        _, message = _git(["log", "-1", "--pretty=%s"], search_root)
        _, author = _git(["log", "-1", "--pretty=%an"], search_root)
        _, date = _git(["log", "-1", "--pretty=%ar"], search_root)
        _, prev_commit = _git(["rev-parse", "--short", "HEAD~1"], search_root)
        git_info = {
            "is_git": True,
            "branch": branch,
            "commit": commit,
            "prev_commit": prev_commit,
            "message": message,
            "author": author,
            "date": date,
        }

    html = report_generator.generate_report(
        terminal=serialize_session(session),
        log_text="".join(session.full_log()),
        code_changes=code_changes,
        lang=request.lang,
        ai_summary=ai_summary,
        ai_provider_config=config_payload,
        git_info=git_info,
        sidecar_id=sidecar_id,
    )
    # ── Persist report to disk ────────────────────────────────────────────────
    filename = f"report_{request.terminal_id[:8]}_{ts}.html"
    report_path = BASE_DIR / "tmp" / "reports" / filename
    report_path.write_text(html, encoding="utf-8")
    report_url = f"/reports/{filename}"
    abs_path = str(report_path.resolve())
    return HTMLResponse(
        content=html,
        headers={
            "X-Report-Path": abs_path,
            "X-Report-URL": report_url,
            "X-Report-Filename": filename,
        },
    )


@app.get("/api/git/info")
async def get_git_info(path: str) -> dict[str, Any]:
    """Return git metadata (branch, commit, last message) for a directory path."""
    p = Path(path)
    cwd = str(p if p.is_dir() else p.parent)
    rc, _ = _git(["rev-parse", "--is-inside-work-tree"], cwd)
    if rc != 0:
        return {"is_git": False}
    _, branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    _, commit = _git(["rev-parse", "--short", "HEAD"], cwd)
    _, commit_full = _git(["rev-parse", "HEAD"], cwd)
    _, message = _git(["log", "-1", "--pretty=%s"], cwd)
    _, author = _git(["log", "-1", "--pretty=%an"], cwd)
    _, date = _git(["log", "-1", "--pretty=%ar"], cwd)
    _, prev_commit = _git(["rev-parse", "--short", "HEAD~1"], cwd)
    _, remote = _git(["remote", "get-url", "origin"], cwd)
    return {
        "is_git": True,
        "branch": branch,
        "commit": commit,
        "commit_full": commit_full,
        "prev_commit": prev_commit,
        "message": message,
        "author": author,
        "date": date,
        "remote": remote,
    }


@app.get("/api/git/file-diff")
async def get_git_file_diff(file_path: str) -> dict[str, Any]:
    """Return git diff (HEAD~1 vs working tree) for a specific file."""
    p = Path(file_path)
    cwd = str(p.parent) if p.exists() else str(Path.home())
    rc, git_root = _git(["rev-parse", "--show-toplevel"], cwd)
    if rc != 0:
        return {"ok": False, "error": "Not a git repository"}
    try:
        rel_path = str(p.relative_to(git_root))
    except ValueError:
        rel_path = p.name
    rc_prev, prev_content = _git(["show", f"HEAD~1:{rel_path}"], git_root)
    try:
        curr_content = p.read_text(encoding="utf-8") if p.exists() else ""
    except Exception:
        curr_content = ""
    _, diff = _git(["diff", "HEAD~1", "HEAD", "--", rel_path], git_root)
    if not diff:
        _, diff = _git(["diff", "HEAD~1", "--", rel_path], git_root)
    _, prev_hash = _git(["rev-parse", "--short", "HEAD~1"], git_root)
    _, curr_hash = _git(["rev-parse", "--short", "HEAD"], git_root)
    _, prev_msg = _git(["log", "-1", "--pretty=%s", "HEAD~1"], git_root)
    _, curr_msg = _git(["log", "-1", "--pretty=%s", "HEAD"], git_root)
    return {
        "ok": True,
        "file_path": str(p),
        "file_name": p.name,
        "before": prev_content if rc_prev == 0 else "",
        "after": curr_content,
        "diff": diff,
        "prev_hash": prev_hash,
        "curr_hash": curr_hash,
        "prev_msg": prev_msg,
        "curr_msg": curr_msg,
    }


@app.post("/api/report/apply-change")
async def apply_report_change(request: ApplyChangeRequest) -> dict[str, Any]:
    """Write the accepted/rejected file content back to disk."""
    if request.action not in ("accept", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'accept' or 'reject'")
    safe_id = Path(request.sidecar_id).name  # prevent path traversal
    sidecar_path = BASE_DIR / "tmp" / "reports" / f"{safe_id}.json"
    if not sidecar_path.exists():
        raise HTTPException(status_code=404, detail="Change set not found")
    try:
        changes = json.loads(sidecar_path.read_text(encoding="utf-8"))
        if request.change_index < 0 or request.change_index >= len(changes):
            raise HTTPException(status_code=400, detail="Invalid change index")
        change = changes[request.change_index]
        file_path = Path(change["file_path"])
        content = change.get("after", "") if request.action == "accept" else change.get("before", "")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return {"ok": True, "file_path": str(file_path), "action": request.action}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email/send")
async def send_email(request: EmailRequest) -> dict[str, Any]:
    smtp_config = {**DEFAULT_SMTP, **(request.smtp_config or {})}
    ok, message = await asyncio.get_running_loop().run_in_executor(
        None,
        email_sender.send_email,
        request.to,
        request.subject,
        request.html,
        smtp_config,
    )
    return {"ok": ok, "message": message}


@app.get("/api/ai/providers")
async def ai_providers() -> list[dict[str, Any]]:
    return [
        {
            "id": provider,
            "name": label,
            "requires_key": provider not in {"copilot", "ollama"},
        }
        for provider, label in PROVIDER_LABELS.items()
    ]


@app.post("/api/ai/test")
async def ai_test(request: AITestRequest) -> dict[str, Any]:
    ok, message = await asyncio.get_running_loop().run_in_executor(
        None,
        test_provider,
        request.provider,
        request.api_key,
        request.base_url,
        request.model,
    )
    return {"ok": ok, "message": message}


@app.get("/api/ai/models")
async def ai_models(provider: str) -> dict[str, Any]:
    provider = provider.lower()
    if provider == "copilot":
        models = await asyncio.get_running_loop().run_in_executor(None, get_copilot_models)
    else:
        models = DEFAULT_MODELS.get(provider, DEFAULT_MODELS["custom"])
    return {"provider": provider, "models": models}


@app.post("/api/ai/chat")
async def ai_chat(request: AIChatRequest) -> dict[str, Any]:
    job_id = start_chat_job(
        request.provider,
        request.api_key,
        request.base_url,
        request.model,
        request.messages,
    )
    return {"job_id": job_id}


@app.get("/api/ai/job/{job_id}")
async def ai_job(job_id: str) -> dict[str, Any]:
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


async def periodic_terminal_updates(enqueue: Any, session: Any) -> None:
    """Push stats + AI info via the per-connection enqueue callable."""
    import psutil as _psutil
    loop = asyncio.get_running_loop()
    ai_tick = 0
    _last_cwd: str | None = None
    while True:
        # ── Process stats (blocking syscall → thread pool) ────────────────────
        stats = await loop.run_in_executor(None, system_monitor.get_process_stats, session.pid)

        # Detect live cwd change (follows cd commands by AI or user).
        # _last_cwd caches the most-recently confirmed cwd so that transient
        # psutil failures (macOS permission races) don't snap the subtitle back
        # to the session's *initial* cwd and cause flickering.
        try:
            live_cwd = await loop.run_in_executor(
                None, lambda: _psutil.Process(session.pid).cwd()
            )
            _last_cwd = live_cwd  # persist the last known-good value
        except Exception:
            live_cwd = _last_cwd or session.cwd  # keep last confirmed cwd on transient errors

        enqueue({
            "type": "stats",
            "cpu": stats["cpu_pct"],
            "mem_mb": stats["mem_mb"],
            "mem_pct": stats["mem_pct"],
            "status": stats["status"],
            "threads": stats["threads"],
            "cwd": live_cwd,  # include live cwd so client can update subtitle
        })
        enqueue({"type": "status", "connected": session.is_alive()})

        # ── AI detection (expensive net scan) — every 5 cycles ≈ 10 s ────────
        if ai_tick % 5 == 0:
            ai_info = await loop.run_in_executor(None, ai_detector.detect_process, session.pid)
            session.ai_info = ai_info
            enqueue({"type": "ai_info", **ai_info})
            # Persist context snapshot periodically (piggyback on AI detect cycle)
            context_store.mark_dirty(session.id)

        ai_tick += 1
        await asyncio.sleep(STATS_INTERVAL)


async def monitor_broadcast_loop() -> None:
    while True:
        payload = build_monitor_payload()
        stale: list[WebSocket] = []
        for client in list(monitor_clients):
            try:
                await client.send_json(payload)
            except Exception:
                stale.append(client)
        for client in stale:
            monitor_clients.discard(client)
        await asyncio.sleep(STATS_INTERVAL)


def build_monitor_payload() -> dict[str, Any]:
    terminals = enrich_terminal_list()
    code_counts = {item["id"]: code_watcher.count_changes(item["id"]) for item in terminals}
    return {
        "type": "monitor",
        "system": system_monitor.get_system_stats(),
        "terminals": terminals,
        "code_changes": code_counts,
    }


def enrich_terminal_list() -> list[dict[str, Any]]:
    terminals = terminal_manager.list_all()
    for item in terminals:
        stats = system_monitor.get_process_stats(item["pid"])
        item["stats"] = stats
        item["code_changes"] = code_watcher.count_changes(item["id"])
    return terminals


def serialize_session(session: Any) -> dict[str, Any]:
    return {
        "id": session.id,
        "title": session.title,
        "description": session.description,
        "shell": session.shell,
        "cwd": session.cwd,
        "pid": session.pid,
        "created_at": session.created_at,
        "connected": session.connected,
        "watch_path": session.watch_path,
        "ai_info": session.ai_info,
        "alive": session.is_alive(),
        "stats": system_monitor.get_process_stats(session.pid),
        "code_changes": code_watcher.count_changes(session.id),
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host=APP_HOST, port=APP_PORT, reload=False)
