from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from hub import activity, state
from hub.handlers.request import resolve_and_activate


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
            else:
                buttons.append([InlineKeyboardButton(f"{name} (spin up)", callback_data=f"request_workspace:{name}")])
        bullets = "\n".join(lines)
        blocks.append(f"{host_label}:\n{bullets}")
    text = (
        "\n\n".join(blocks)
        + "\n\nTap a workspace to send it messages directly — one with a live "
        "session relays right in, one without spins a new session up first:"
    )

    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    activity.record(update.effective_user.id, "/workspaces", None, f"listed {len(workspaces)}")


async def cmd_request_workspace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    name = query.data.removeprefix("request_workspace:")
    await query.answer()
    await resolve_and_activate(context, update.effective_user.id, name, query.message.reply_text)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("workspaces", cmd_workspaces))
    application.add_handler(CallbackQueryHandler(cmd_request_workspace, pattern=r"^request_workspace:"))
