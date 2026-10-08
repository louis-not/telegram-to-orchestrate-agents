"""`/request <workspace>` (B2) — explicit, confirm-free workspace resolution.

Does the same resolve-or-provision work fallback.py does for a plain-text
workspace mention, but skips the confirm gate: typing /request is itself
the deliberate act (§10). The tap-to-request button in /workspaces
(hub/handlers/workspaces.py) reuses resolve_and_activate below for the
same reason — tapping a button you can see is equally deliberate.
"""

from typing import Awaitable, Callable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import activity, errors, matching, state, workspace_provision
from hub.handlers.select import STOP_BUTTON

Reply = Callable[..., Awaitable[None]]


async def resolve_and_activate(context: ContextTypes.DEFAULT_TYPE, user_id: int, name: str, reply: Reply) -> None:
    """Core /request logic: resolve `name` to a workspace, reuse or provision
    its session, make it this chat's active session, and reply via `reply`
    (a Message.reply_text-shaped callable so both a command reply and a
    callback-query reply can share this)."""
    workspace = state.workspaces.get(name)
    if workspace is None:
        matches = matching.mentioned(name, list(state.workspaces.all().keys()))
        if len(matches) == 0:
            await reply(f"no such workspace: {name}")
            activity.record(user_id, "/request", name, "error: unknown workspace")
            return
        if len(matches) > 1:
            await reply("ambiguous workspace name")
            activity.record(user_id, "/request", name, "error: unknown workspace")
            return
        workspace = state.workspaces.get(matches[0])

    if not workspace_provision.revalidate(workspace):
        state.workspaces.remove(workspace.name)
        await reply("workspace no longer available")
        activity.record(user_id, "/request", workspace.name, "error: workspace gone")
        return

    live = workspace_provision.live_session_for_path(workspace.path)
    if live is not None:
        session_id, _ = live
        context.user_data["active_session"] = session_id
        await reply(
            f"Now talking to {session_id} — just send your message, no need for /ask.",
            reply_markup=STOP_BUTTON,
        )
        activity.record(user_id, "/request", workspace.name, "selected")
        return

    try:
        session_id = await workspace_provision.resolve_or_provision(workspace, f"/request {workspace.name}")
        context.user_data["active_session"] = session_id
        await reply(
            f"registered and launched session {session_id} for workspace {workspace.name}.\n"
            f"Now talking to it directly — just send your messages, no need for /ask.",
            reply_markup=STOP_BUTTON,
        )
        activity.record(user_id, "/request", workspace.name, "provisioned")
    except workspace_provision.WorkspaceGone:
        await reply(f"workspace {workspace.name} is no longer available.")
        activity.record(user_id, "/request", workspace.name, "error: workspace gone")
    except Exception as exc:
        await reply(errors.failure_text("/request", exc))
        activity.record(user_id, "/request", workspace.name, f"error: {exc}")


async def cmd_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if len(context.args) != 1:
        await update.effective_message.reply_text("usage: /request <workspace>")
        return
    await resolve_and_activate(context, user_id, context.args[0], update.effective_message.reply_text)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("request", cmd_request))
