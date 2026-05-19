from __future__ import annotations

import os
import re
from typing import Any

import psutil

AI_PATTERNS = {
    "copilot": {
        "cmdline_keywords": ["copilot", "gh copilot", "github-copilot"],
        "env_vars": ["COPILOT_GITHUB_TOKEN", "GH_TOKEN"],
        "provider": "GitHub",
        "framework": "GitHub Copilot",
    },
    "claude": {
        "cmdline_keywords": ["claude", "anthropic"],
        "env_vars": ["ANTHROPIC_API_KEY"],
        "provider": "Anthropic",
        "framework": "Claude",
    },
    "ollama": {
        "cmdline_keywords": ["ollama"],
        "env_vars": [],
        "provider": "Ollama",
        "framework": "Ollama",
    },
    "openai": {
        "cmdline_keywords": ["openai", "chatgpt", "gpt"],
        "env_vars": ["OPENAI_API_KEY"],
        "provider": "OpenAI",
        "framework": "OpenAI API",
    },
    "deepseek": {
        "cmdline_keywords": ["deepseek"],
        "env_vars": ["DEEPSEEK_API_KEY"],
        "provider": "DeepSeek",
        "framework": "DeepSeek",
    },
    "aider": {
        "cmdline_keywords": ["aider"],
        "env_vars": [],
        "provider": "Various",
        "framework": "Aider",
    },
    "cursor": {
        "cmdline_keywords": ["cursor"],
        "env_vars": [],
        "provider": "Cursor",
        "framework": "Cursor AI",
    },
    "qwen": {
        "cmdline_keywords": ["qwen", "dashscope", "qwq"],
        "env_vars": ["DASHSCOPE_API_KEY"],
        "provider": "Alibaba",
        "framework": "Qwen",
    },
}

MODEL_PATTERN = re.compile(r"(gpt[-\w.]+|claude[-\w.]+|deepseek[-\w.]+|qwen[-\w.]+|gemini[-\w.]+|llama[-\w.]+)", re.I)


class AIDetector:
    def detect_process(self, pid: int) -> dict[str, Any]:
        try:
            proc = psutil.Process(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return self._default_result()

        candidates = [proc]
        try:
            candidates.extend(proc.children(recursive=True))
        except Exception:
            pass

        best = self._default_result()
        for candidate in candidates:
            result = self._inspect_candidate(candidate)
            if result["confidence"] > best["confidence"]:
                best = result
        return best

    def _inspect_candidate(self, proc: psutil.Process) -> dict[str, Any]:
        score_map: dict[str, float] = {}
        text = self._safe_cmdline(proc)
        env = self._safe_env(proc)
        connections = self._safe_connections(proc)

        for key, meta in AI_PATTERNS.items():
            score = 0.0
            if any(word in text for word in meta["cmdline_keywords"]):
                score += 0.6
            if any(var in env for var in meta["env_vars"]):
                score += 0.25
            if key == "ollama" and any(conn.get("port") == 11434 for conn in connections):
                score += 0.2
            if key in {"openai", "claude", "deepseek", "qwen", "copilot"} and any(conn.get("port") == 443 for conn in connections):
                score += 0.05
            score_map[key] = score

        best_key, confidence = max(score_map.items(), key=lambda item: item[1], default=("", 0.0))
        if confidence <= 0:
            return self._default_result()

        meta = AI_PATTERNS[best_key]
        model = self._extract_model(text, env)
        return {
            "detected": True,
            "provider": meta["provider"],
            "model": model,
            "framework": meta["framework"],
            "confidence": round(min(confidence, 0.99), 2),
        }

    def _safe_cmdline(self, proc: psutil.Process) -> str:
        values: list[str] = []
        try:
            values.append(proc.name().lower())
        except Exception:
            pass
        try:
            values.extend(part.lower() for part in proc.cmdline())
        except Exception:
            pass
        return " ".join(values)

    def _safe_env(self, proc: psutil.Process) -> dict[str, str]:
        try:
            env = proc.environ()
            return {str(k): str(v) for k, v in env.items()}
        except Exception:
            return {}

    def _safe_connections(self, proc: psutil.Process) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            for conn in proc.net_connections(kind="inet"):
                if conn.raddr:
                    results.append({"ip": getattr(conn.raddr, "ip", ""), "port": getattr(conn.raddr, "port", None)})
        except Exception:
            pass
        return results

    def _extract_model(self, text: str, env: dict[str, str]) -> str:
        match = MODEL_PATTERN.search(text)
        if match:
            return match.group(1)
        for value in env.values():
            match = MODEL_PATTERN.search(value)
            if match:
                return match.group(1)
        for name in ("OPENAI_MODEL", "ANTHROPIC_MODEL", "OLLAMA_MODEL", "DEEPSEEK_MODEL", "QWEN_MODEL"):
            if env.get(name):
                return env[name]
        return ""

    @staticmethod
    def _default_result() -> dict[str, Any]:
        return {
            "detected": False,
            "provider": "",
            "model": "",
            "framework": "",
            "confidence": 0.0,
        }
