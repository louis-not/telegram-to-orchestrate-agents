from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import activity, state


async def cmd_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sessions = state.registry.all()
    if not sessions:
        await update.effective_message.reply_text("no sessions registered.")
        activity.record(update.effective_user.id, "/sessions", None, "empty")
        return

    by_host: dict[str, list[str]] = {}
    for session_id, session in sorted(sessions.items()):
        last_state = "unknown (not yet polled)"
        snapshot = state.monitor.last_known(session_id)
        if snapshot is not None:
            last_state = snapshot[-200:] or "(empty pane)"
        by_host.setdefault(session.host, []).append(f"  {session_id} — {last_state}")

    lines = []
    for host, entries in sorted(by_host.items()):
        lines.append(f"*{host}*")
        lines.extend(entries)
    await update.effective_message.reply_text("\n".join(lines))
    activity.record(update.effective_user.id, "/sessions", None, f"listed {len(sessions)}")


def register(application: Application) -> None:
    application.add_handler(CommandHandler("sessions", cmd_sessions))
