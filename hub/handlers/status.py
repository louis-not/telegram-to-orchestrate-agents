from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import activity, errors, state, transport


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

    if len(pane) > 3500:
        text = "(truncated, showing last 3500 chars)\n" + pane[-3500:]
    else:
        text = pane
    await update.effective_message.reply_text(text)
    activity.record(user_id, "/status", session_id, "ok")


def register(application: Application) -> None:
    application.add_handler(CommandHandler("status", cmd_status))
