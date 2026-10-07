from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import activity, errors, state, transport


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if len(context.args) != 1:
        await update.effective_message.reply_text("usage: /resume <id>")
        return
    session_id = context.args[0]
    session = state.registry.get(session_id)
    if session is None:
        await update.effective_message.reply_text(f"no such session: {session_id}")
        activity.record(user_id, "/resume", session_id, "error: unknown session")
        return

    if not session.claude_session_id:
        await update.effective_message.reply_text(
            f"session {session_id} has no stored claude session id to resume."
        )
        activity.record(user_id, "/resume", session_id, "error: no claude_session_id")
        return

    try:
        transport.new_session(session, f"claude --resume={session.claude_session_id}")
        result = "resumed"
        await update.effective_message.reply_text(f"resumed session {session_id}.")
    except Exception as exc:
        result = await errors.reply_failure(update, "/resume", exc)

    activity.record(user_id, "/resume", session_id, result)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("resume", cmd_resume))
