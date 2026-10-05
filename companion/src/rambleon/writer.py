"""The writer: voices, and the local Claude CLI when it is there. What to write is the caller's prompt."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any

from . import prompts

DEFAULT_VOICE = "golden"
DEFAULT_MODEL = "sonnet"
SYSTEM_PROMPT = ("You are a careful writer helping a player look back on their World of Warcraft "
                 "adventures. Follow the instructions in the message exactly. Output only the requested text.")


def available_voices() -> list[str]:
    """Bundled voices and the player's own (<home>/prompts/voices/*.md)."""
    return sorted(prompts.available("voices"))


def load_voice(name: str | None) -> str:
    """The text of a voice: a name from `ramble voices`, or a path to a .md file of your own."""
    return prompts.load("voices", name or os.environ.get("RAMBLEON_VOICE") or DEFAULT_VOICE)[1]


def claude_available() -> str | None:
    return shutil.which("claude")


def run_claude(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 600) -> tuple[str | None, str]:
    """Returns (text, diagnostic). Uses only flags verified on the installed CLI."""
    exe = claude_available()
    if not exe:
        return None, "claude CLI not found on PATH"
    # No tools, no session, a writer's system prompt instead of the coding one, and an empty working
    # directory so no CLAUDE.md or project settings leak into the writing. Uses the CLI's own login.
    cmd = [exe, "-p", "--tools", "", "--output-format", "json", "--no-session-persistence",
           "--max-budget-usd", "0.50", "--model", model,
           "--system-prompt", SYSTEM_PROMPT]
    with tempfile.TemporaryDirectory(prefix="rambleon-") as cwd:
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        except (OSError, subprocess.TimeoutExpired) as e:
            return None, f"claude failed to run: {e}"
    out = (proc.stdout or "").strip()
    payload: Any = None
    try:
        payload = json.loads(out) if out else None
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        text = payload.get("result")
        if payload.get("is_error") or proc.returncode != 0:
            return None, f"claude reported an error: {text or proc.stderr.strip()[:300]}"
        if isinstance(text, str) and text.strip():
            return text.strip(), "ok"
        return None, f"claude returned no result: {out[:300]}"
    if proc.returncode != 0:
        return None, f"claude exited {proc.returncode}: {(proc.stderr or out).strip()[:500]}"
    return (out, "ok (plain text)") if out else (None, "claude returned nothing")
