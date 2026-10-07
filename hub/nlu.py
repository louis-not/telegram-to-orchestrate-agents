"""Answers a plain-text message via a one-shot `claude -p` subprocess.

Mirrors the shape of bangkax-agent-api's bot/runner (command.py +
process.py): a pure command-builder, a child env that drops this
process's own secrets, and a bounded-time subprocess spawn — just without
that runner's streaming/retry machinery, since this is a single quick
Q&A reply rather than a long-running tool-using session.

Uses the `claude` CLI's own login, not a separate API key: same
authentication every other `claude --permission-mode auto` launch in this
hub already relies on.
"""

import asyncio
import json
import logging
import os

from hub import config

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 45
_SECRET_ENV_PREFIXES = ("TELEGRAM_", "AGENT_SHARED_SECRET", "SESSION_REGISTRY_PATH")


def _child_env() -> dict[str, str]:
    """Copy os.environ, dropping this hub's own secrets before the child sees them."""
    return {
        k: v
        for k, v in os.environ.items()
        if not any(k == p or k.startswith(p) for p in _SECRET_ENV_PREFIXES)
    }


def build_command(prompt: str) -> list[str]:
    return [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--permission-mode",
        "default",
        "--model",
        config.NLU_MODEL,
    ]


async def answer(prompt: str) -> str:
    """Runs claude -p with prompt, returns its text answer (or a short error string)."""
    cmd = build_command(prompt)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_child_env(),
        )
    except FileNotFoundError:
        logger.exception("claude CLI not found")
        return "the troubleshooting agent isn't available (claude CLI not found)."

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return "troubleshooting agent timed out."

    if proc.returncode != 0:
        logger.warning("claude -p exited %s: %s", proc.returncode, stderr.decode(errors="replace")[:500])
        return "troubleshooting agent failed to answer that."

    try:
        data = json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError:
        logger.warning("claude -p returned non-JSON output")
        return "troubleshooting agent returned something unreadable."

    return data.get("result") or "(no answer)"
