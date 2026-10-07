from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import activity, errors, pane_format, state, transport

# Mobile-sized, not Telegram's 4096-char limit: a readable snippet, not a
# wall of raw terminal output.
PANE_REPLY_CHARS = 600


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not context.args:
        await update.effective_message.reply_text("usage: /status <id>")
        return
    session_id = context.args[0]
    session = state.registry.get(session_id)
    if session is None:
        await update.effective_message.reply_text(f"no such session: {session_id}")
        activity.record(user_id, "/status", session_id, "error: unknown session")
        return

    try:
        pane = transport.capture_pane(session)
    except Exception as exc:
        result = await errors.reply_failure(update, "/status", exc)
        activity.record(user_id, "/status", session_id, result)
        return

    snippet = pane_format.clean_snippet(pane, PANE_REPLY_CHARS)
    text = f"{snippet}\n\nSend a message to continue it, or /status {session_id} again for a fresh look."
    await update.effective_message.reply_text(text)
    activity.record(user_id, "/status", session_id, "ok")


def register(application: Application) -> None:
    application.add_handler(CommandHandler("status", cmd_status))
