"""Periodically syncs the registry with whatever local tmux sessions
actually exist, so a new session shows up in /sessions without anyone
hand-editing sessions.json or restarting the hub.

Local-only by design: there's no way to enumerate a remote agent's tmux
sessions without a new agent endpoint, so remote sessions still need /new.
"""

import logging
import subprocess
from pathlib import Path

import hub.workspace_registry
from hub import state
from hub.registry import Session

logger = logging.getLogger(__name__)

# The hub's own repo root (hub/discovery.py -> hub/ -> repo root), so a live
# tmux session pointed at this same directory never gets auto-tracked as a
# project session. _own_tmux_session_name() below only works when the hub
# itself runs inside a tmux pane; it doesn't when it's a systemd/plain
# background process (no TMUX env, no pane of its own) — in that case it
# silently returns None and excludes nothing, so a tmux session that happens
# to exist (named "hub" or anything else) with this cwd would otherwise slip
# through as a seemingly legitimate project session. This check doesn't
# depend on how the hub itself is run.
_OWN_REPO_ROOT = Path(__file__).resolve().parent.parent


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
        if cwd is None or Path(cwd).resolve() == _OWN_REPO_ROOT:
            continue
        state.registry.put(name, Session(host="local", tmux_session=name, cwd=cwd))
        root = hub.workspace_registry.find_workspace_root(cwd)
        if root is not None:
            state.workspaces.register(root, "local", name)
        added.append(name)
        logger.info("auto-registered local session %s (cwd=%s)", name, cwd)

    removed = []
    for session_id, session in known.items():
        if session.host == "local" and session.tmux_session not in live_names:
            state.registry.remove(session_id)
            removed.append(session_id)
            logger.info("auto-removed stale local session %s (tmux session gone)", session_id)

    # Backfill: a session already in the registry before workspace mapping
    # existed (or added by hand to sessions.json) never goes through the
    # "newly discovered" branch above, so it would otherwise never get a
    # workspace resolved for it. Re-resolving every live local session each
    # tick is cheap (just .creds.md existence checks) and self-healing —
    # also silent, same as the newly-discovered case (A6).
    for session_id, session in known.items():
        if session.host == "local" and session.tmux_session in live_names:
            root = hub.workspace_registry.find_workspace_root(session.cwd)
            if root is not None:
                state.workspaces.register(root, "local", session_id)

    return added, removed
