from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import activity, confirm, errors, state, transport


async def cmd_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not context.args:
        await update.effective_message.reply_text("usage: /kill <id>")
        return
    session_id = context.args[0]
    session = state.registry.get(session_id)
    if session is None:
        await update.effective_message.reply_text(f"no such session: {session_id}")
        activity.record(user_id, "/kill", session_id, "error: unknown session")
        return

    async def _do_kill() -> str:
        try:
            transport.kill_session(session)
            state.registry.remove(session_id)
            result = "killed"
            await update.effective_message.reply_text(f"killed session {session_id}.")
        except Exception as exc:
            result = await errors.reply_failure(update, "/kill", exc)
        activity.record(user_id, "/kill", session_id, result)
        return result

    confirm.request(user_id, f"kill session {session_id}", _do_kill)
    await update.effective_message.reply_text(
        f"this will kill session {session_id}. Reply /confirm within 30s to proceed."
    )


def register(application: Application) -> None:
    application.add_handler(CommandHandler("kill", cmd_kill))
