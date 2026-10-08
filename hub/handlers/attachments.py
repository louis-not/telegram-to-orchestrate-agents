"""Handles photo uploads by relaying them into a resolved session's cwd.

Mirrors the active-session-or-workspace resolution in fallback.py (E2) for
photos specifically, using the photo's caption as the "message" for
workspace-name matching. Deliberately independent of fallback.py — no
shared code, just the same underlying building blocks (workspace_provision,
matching, confirm, ask_session).
"""

import time
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from hub import activity, confirm, errors, matching, state, workspace_provision
from hub.handlers.ask import ask_session
from hub.workspace_registry import WORKSPACE_MARKER

UPLOADS_DIR = Path("./var/uploads")
NO_TARGET_REPLY = (
    "Which session or workspace is this image for? Select one with /sessions "
    "or /workspaces first, or name a workspace in the caption."
)


async def _download_and_relay(
    update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str, caption: str
) -> None:
    photo = update.effective_message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)

    dest_dir = UPLOADS_DIR / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{int(time.time())}-{photo.file_id}.jpg"

    await tg_file.download_to_drive(str(dest_path))

    text = f"Image attached: {dest_path.resolve()}"
    if caption:
        text += f"\nCaption: {caption}"
    await ask_session(update, session_id, text)


async def cmd_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    caption = update.effective_message.caption or ""
    user_id = update.effective_user.id

    active_session = context.user_data.get("active_session")
    if active_session is not None:
        if state.registry.get(active_session) is None:
            context.user_data.pop("active_session", None)
        else:
            try:
                await _download_and_relay(update, context, active_session, caption)
                result = "ok"
            except Exception as exc:
                result = await errors.reply_failure(update, "(photo)", exc)
            activity.record(user_id, "(photo)", active_session, result)
            return

    names = matching.mentioned(caption, list(state.workspaces.all().keys()))
    if len(names) == 1:
        workspace = state.workspaces.get(names[0])
        if not workspace_provision.revalidate(workspace):
            state.workspaces.remove(names[0])
            await update.effective_message.reply_text(
                f"workspace {names[0]} is no longer available (path or "
                f"{WORKSPACE_MARKER} marker missing)."
            )
            activity.record(user_id, "(photo)", names[0], "error: workspace gone")
            return

        live = workspace_provision.live_session_for_path(workspace.path)
        if live is not None:
            session_id, _ = live
            context.user_data["active_session"] = session_id
            try:
                await _download_and_relay(update, context, session_id, caption)
                result = "ok"
            except Exception as exc:
                result = await errors.reply_failure(update, "(photo)", exc)
            activity.record(user_id, "(photo)", session_id, result)
            return

        async def _do_provision() -> str:
            try:
                session_id = await workspace_provision.resolve_or_provision(workspace, caption)
                context.user_data["active_session"] = session_id
                await _download_and_relay(update, context, session_id, caption)
                return "ok"
            except workspace_provision.WorkspaceGone:
                await update.effective_message.reply_text(f"workspace {workspace.name} is no longer available.")
                return "error: workspace gone"
            except Exception as exc:
                return await errors.reply_failure(update, "(photo)", exc)

        confirm.request(user_id, f"spin up a new session for workspace '{workspace.name}'", _do_provision)
        await update.effective_message.reply_text(
            f"no live session for workspace '{workspace.name}' yet — this will spin one up. "
            f"Reply /confirm within 30s to proceed."
        )
        activity.record(user_id, "(workspace)", workspace.name, "pending confirm")
        return

    await update.effective_message.reply_text(NO_TARGET_REPLY)
    activity.record(user_id, "(photo)", None, "error: no target resolved")


def register(application: Application) -> None:
    application.add_handler(MessageHandler(filters.PHOTO, cmd_photo))
