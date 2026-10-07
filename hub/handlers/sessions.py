from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import activity, state

STATUS_LINE_MAX_CHARS = 70


def _last_status_line(snapshot: str) -> str:
    """The most recent non-blank line of a pane capture, as a short summary."""
    for line in reversed(snapshot.splitlines()):
        line = line.strip()
        if line:
            return line if len(line) <= STATUS_LINE_MAX_CHARS else line[: STATUS_LINE_MAX_CHARS - 1] + "…"
    return "(empty pane)"


async def cmd_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sessions = state.registry.all()
    if not sessions:
        await update.effective_message.reply_text("No sessions registered.")
        activity.record(update.effective_user.id, "/sessions", None, "empty")
        return

    by_host: dict[str, list[tuple[str, str]]] = {}
    for session_id, session in sorted(sessions.items()):
        snapshot = state.monitor.last_known(session_id)
        status = "not yet polled" if snapshot is None else _last_status_line(snapshot)
        by_host.setdefault(session.host, []).append((session_id, status))

    blocks = []
    for host, entries in sorted(by_host.items()):
        host_label = "Local" if host == "local" else host
        bullets = "\n".join(f"  • {session_id} — {status}" for session_id, status in entries)
        blocks.append(f"{host_label}:\n{bullets}")
    text = "\n\n".join(blocks) + "\n\nTap a session to send it messages directly:"

    buttons = [[InlineKeyboardButton(session_id, callback_data=f"ask:{session_id}")] for session_id in sorted(sessions)]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    activity.record(update.effective_user.id, "/sessions", None, f"listed {len(sessions)}")


def register(application: Application) -> None:
    application.add_handler(CommandHandler("sessions", cmd_sessions))
