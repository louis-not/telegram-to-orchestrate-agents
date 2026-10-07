"""Workspace -> live session resolution and auto-provisioning (C4, C5, C6).

Telegram-update-agnostic on purpose: callers (fallback.py, request.py) own
setting context.user_data["active_session"] and relaying the triggering
message — this module only ever hands back a session id.
"""

from pathlib import Path

from hub import config, naming, state, transport
from hub.registry import Session
from hub.workspace_registry import Workspace


class WorkspaceGone(Exception):
    pass


def revalidate(workspace: Workspace) -> bool:
    return Path(workspace.path).exists() and (Path(workspace.path) / ".creds.md").exists()


def live_session_for_path(path: str) -> tuple[str, Session] | None:
    for session_id, session in state.registry.all().items():
        if session.cwd == path:
            return session_id, session
    return None


async def resolve_or_provision(workspace: Workspace, triggering_message: str) -> str:
    if not revalidate(workspace):
        state.workspaces.remove(workspace.name)
        raise WorkspaceGone

    live = live_session_for_path(workspace.path)
    if live is not None:
        session_id, _ = live
        return session_id

    name = await naming.generate_session_name(triggering_message)
    session = Session(host=workspace.host, tmux_session=name, cwd=workspace.path)
    transport.new_session(session, f"claude --permission-mode auto --model {config.WORKSPACE_SESSION_MODEL}")
    state.registry.put(name, session)
    return name
