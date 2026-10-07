"""Generates a short, descriptive tmux session name for an auto-provisioned
session, via the same one-shot `claude -p` pattern as `hub/nlu.py` — see
that module's docstring for why the sandbox dir + --disallowedTools +
--strict-mcp-config combination is load-bearing, not optional.
"""

import asyncio
import json
import logging
import os
import re
import time

from hub import config, state
from hub.nlu import SANDBOX_DIR, _DISALLOWED_TOOLS, _child_env

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20

_SLUG_PROMPT = (
    "Turn this message into a short, descriptive kebab-case slug of 2-4 "
    'words, suitable as a tmux session name (e.g. "add-auth-middleware"). '
    "Reply with only the slug, nothing else.\n\nMessage: {message}"
)

_SLUG_CHARS_RE = re.compile(r"[^a-z0-9-]+")
_MULTI_HYPHEN_RE = re.compile(r"-+")


def _sanitize_slug(raw: str) -> str | None:
    slug = raw.strip().lower()
    slug = _SLUG_CHARS_RE.sub("-", slug)
    slug = _MULTI_HYPHEN_RE.sub("-", slug).strip("-")
    return slug or None


def _build_command(prompt: str) -> list[str]:
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
        "--strict-mcp-config",
        "--disallowedTools",
        *_DISALLOWED_TOOLS,
    ]


async def _generate_slug(triggering_message: str) -> str | None:
    cmd = _build_command(_SLUG_PROMPT.format(message=triggering_message))
    os.makedirs(SANDBOX_DIR, exist_ok=True)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=SANDBOX_DIR,
            env=_child_env(),
        )
    except FileNotFoundError:
        logger.exception("claude CLI not found")
        return None

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return None

    if proc.returncode != 0:
        logger.warning("naming claude -p exited %s: %s", proc.returncode, stderr.decode(errors="replace")[:500])
        return None

    try:
        data = json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError:
        logger.warning("naming claude -p returned non-JSON output")
        return None

    result = data.get("result")
    if not result:
        return None
    return _sanitize_slug(result)


async def generate_session_name(triggering_message: str) -> str:
    name = await _generate_slug(triggering_message)
    if name is None:
        name = f"session-{int(time.time())}"

    existing = state.registry.all()
    if name not in existing:
        return name

    suffix = 2
    while f"{name}-{suffix}" in existing:
        suffix += 1
    return f"{name}-{suffix}"
