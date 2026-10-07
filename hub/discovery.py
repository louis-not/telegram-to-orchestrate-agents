"""Periodically syncs the registry with whatever local tmux sessions
actually exist, so a new session shows up in /sessions without anyone
hand-editing sessions.json or restarting the hub.

Local-only by design: there's no way to enumerate a remote agent's tmux
sessions without a new agent endpoint, so remote sessions still need /new.
"""

import logging
import subprocess

from hub import state
from hub.registry import Session

logger = logging.getLogger(__name__)


def _own_tmux_session_name() -> str | None:
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{session_name}"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def _pane_cwd(session_name: str) -> str | None:
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "-t", session_name, "#{pane_current_path}"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def sync_local_sessions() -> tuple[list[str], list[str]]:
    """Registers new local tmux sessions and prunes registry entries whose
    local tmux session no longer exists. Returns (added_ids, removed_ids).

    If `tmux list-sessions` itself fails (no server, tmux not installed),
    returns ([], []) rather than treating "can't tell" as "everything is
    gone" — a transient tmux hiccup must never mass-delete the registry.
    """
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return [], []

    own_session = _own_tmux_session_name()
    live_names = {name.strip() for name in result.stdout.splitlines() if name.strip()}
    known = state.registry.all()

    added = []
    for name in live_names:
        if name == own_session or name in known:
            continue
        cwd = _pane_cwd(name)
        if cwd is None:
            continue
        state.registry.put(name, Session(host="local", tmux_session=name, cwd=cwd))
        added.append(name)
        logger.info("auto-registered local session %s (cwd=%s)", name, cwd)

    removed = []
    for session_id, session in known.items():
        if session.host == "local" and session.tmux_session not in live_names:
            state.registry.remove(session_id)
            removed.append(session_id)
            logger.info("auto-removed stale local session %s (tmux session gone)", session_id)

    return added, removed
