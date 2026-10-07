from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import hub.activity
import hub.errors
import hub.registry
import hub.transport
import hub.workspace_registry
from hub import state
from hub.handlers.fallback import NLU_HISTORY_KEY
from hub.handlers.select import STOP_BUTTON


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
        root = hub.workspace_registry.find_workspace_root(cwd)
        if root is not None:
            state.workspaces.register(root, host, session_id)
        result = "registered"
        # Per docs/technical-concept.md: this chat is meant to *be* the
        # control surface for a session, not a bot you redirect each time
        # — so a freshly created session becomes the active one immediately.
        context.user_data["active_session"] = session_id
        context.user_data.pop(NLU_HISTORY_KEY, None)
        await update.effective_message.reply_text(
            f"registered and launched session {session_id} on {host}.\n"
            f"Now talking to it directly — just send your messages, no need for /ask.",
            reply_markup=STOP_BUTTON,
        )
    except Exception as exc:
        result = await hub.errors.reply_failure(update, "/new", exc)

    hub.activity.record(user_id, "/new", session_id, result)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("new", cmd_new))
