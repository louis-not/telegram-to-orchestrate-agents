"""`/request <workspace>` (B2) — explicit, confirm-free workspace resolution.

Does the same resolve-or-provision work fallback.py does for a plain-text
workspace mention, but skips the confirm gate: typing /request is itself
the deliberate act (§10).
"""

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import activity, errors, matching, state, workspace_provision
from hub.handlers.select import STOP_BUTTON


async def cmd_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if len(context.args) != 1:
        await update.effective_message.reply_text("usage: /request <workspace>")
        return
    name = context.args[0]

    workspace = state.workspaces.get(name)
    if workspace is None:
        matches = matching.mentioned(name, list(state.workspaces.all().keys()))
        if len(matches) == 0:
            await update.effective_message.reply_text(f"no such workspace: {name}")
            activity.record(user_id, "/request", name, "error: unknown workspace")
            return
        if len(matches) > 1:
            await update.effective_message.reply_text("ambiguous workspace name")
            activity.record(user_id, "/request", name, "error: unknown workspace")
            return
        workspace = state.workspaces.get(matches[0])

    if not workspace_provision.revalidate(workspace):
        state.workspaces.remove(workspace.name)
        await update.effective_message.reply_text("workspace no longer available")
        activity.record(user_id, "/request", workspace.name, "error: workspace gone")
        return

    live = workspace_provision.live_session_for_path(workspace.path)
    if live is not None:
        session_id, _ = live
        context.user_data["active_session"] = session_id
        await update.effective_message.reply_text(
            f"Now talking to {session_id} — just send your message, no need for /ask.",
            reply_markup=STOP_BUTTON,
        )
        activity.record(user_id, "/request", workspace.name, "selected")
        return

    try:
        session_id = await workspace_provision.resolve_or_provision(workspace, f"/request {workspace.name}")
        context.user_data["active_session"] = session_id
        await update.effective_message.reply_text(
            f"registered and launched session {session_id} for workspace {workspace.name}.\n"
            f"Now talking to it directly — just send your messages, no need for /ask.",
            reply_markup=STOP_BUTTON,
        )
        activity.record(user_id, "/request", workspace.name, "provisioned")
    except workspace_provision.WorkspaceGone:
        await update.effective_message.reply_text(f"workspace {workspace.name} is no longer available.")
        activity.record(user_id, "/request", workspace.name, "error: workspace gone")
    except Exception as exc:
        result = await errors.reply_failure(update, "/request", exc)
        activity.record(user_id, "/request", workspace.name, result)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("request", cmd_request))
