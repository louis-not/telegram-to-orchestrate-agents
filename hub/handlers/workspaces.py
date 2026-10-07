from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import activity, state


async def cmd_workspaces(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    workspaces = state.workspaces.all()
    if not workspaces:
        await update.effective_message.reply_text("No workspaces registered.")
        activity.record(update.effective_user.id, "/workspaces", None, "empty")
        return

    sessions = state.registry.all()
    live_by_path: dict[str, str] = {session.cwd: session_id for session_id, session in sessions.items()}

    by_host: dict[str, list[tuple[str, str | None]]] = {}
    for name, workspace in sorted(workspaces.items()):
        live_session_id = live_by_path.get(workspace.path)
        by_host.setdefault(workspace.host, []).append((name, live_session_id))

    blocks = []
    buttons = []
    for host, entries in sorted(by_host.items()):
        host_label = "Local" if host == "local" else host
        lines = []
        for name, live_session_id in entries:
            workspace = workspaces[name]
            status = f"(live: {live_session_id})" if live_session_id else "(no live session)"
            lines.append(f"  • {name} — {workspace.path} {status}")
            if live_session_id:
                buttons.append([InlineKeyboardButton(name, callback_data=f"ask:{live_session_id}")])
        bullets = "\n".join(lines)
        blocks.append(f"{host_label}:\n{bullets}")
    text = "\n\n".join(blocks) + "\n\nTap a workspace with a live session to send it messages directly:"

    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    activity.record(update.effective_user.id, "/workspaces", None, f"listed {len(workspaces)}")


def register(application: Application) -> None:
    application.add_handler(CommandHandler("workspaces", cmd_workspaces))
