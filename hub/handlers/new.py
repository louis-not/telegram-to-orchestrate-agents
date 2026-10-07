from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import hub.activity
import hub.errors
import hub.registry
import hub.transport
from hub import state


async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if len(context.args) != 3:
        await update.effective_message.reply_text("usage: /new <id> <host> <cwd>")
        return
    session_id, host, cwd = context.args

    if state.registry.get(session_id) is not None:
        await update.effective_message.reply_text(f"session {session_id} already exists.")
        return

    session = hub.registry.Session(host=host, tmux_session=session_id, cwd=cwd)
    try:
        hub.transport.new_session(session, "claude --permission-mode auto")
        state.registry.put(session_id, session)
        result = "registered"
        await update.effective_message.reply_text(
            f"registered and launched session {session_id} on {host}."
        )
    except Exception as exc:
        result = await hub.errors.reply_failure(update, "/new", exc)

    hub.activity.record(user_id, "/new", session_id, result)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("new", cmd_new))
