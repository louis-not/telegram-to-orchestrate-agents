"""Handles the inline buttons /sessions attaches to each listed session.

Tapping one sets a per-chat "active session": every plain-text message
after that goes straight to /ask on that session (via ask.ask_session)
instead of the general assistant in fallback.py, until the user taps
"stop" or picks a different session. Purely a UX shortcut for not
retyping the session id — /ask <id> <message> still works as before
regardless of what's active.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

STOP_BUTTON = InlineKeyboardMarkup([[InlineKeyboardButton("Stop talking to this session", callback_data="deselect")]])


async def cmd_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    session_id = query.data.removeprefix("ask:")
    context.user_data["active_session"] = session_id
    await query.answer()
    await query.message.reply_text(
        f"Now talking to {session_id} — just send your message, no need for /ask.",
        reply_markup=STOP_BUTTON,
    )


async def cmd_deselect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    context.user_data.pop("active_session", None)
    await query.answer()
    await query.message.reply_text("Back to the general assistant. Plain messages won't go to any session now.")


def register(application: Application) -> None:
    application.add_handler(CallbackQueryHandler(cmd_select, pattern=r"^ask:"))
    application.add_handler(CallbackQueryHandler(cmd_deselect, pattern=r"^deselect$"))
