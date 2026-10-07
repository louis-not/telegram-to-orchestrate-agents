"""Catches anything that isn't a recognized command so the bot never just
goes silent on a plain-text message (same "no silent drop" principle as
hub/errors.py, applied to unrecognized input rather than transport failures).

This is not an NLU layer — no command handler matched, full stop. It just
tells the user what commands exist instead of leaving them wondering if the
message vanished.
"""

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

HELP_TEXT = (
    "I only understand commands, not plain questions. Try:\n"
    "  • /sessions — list all sessions\n"
    "  • /status <id> — show a session's current output\n"
    "  • /ask <id> <message> — send a message into a session\n"
    "  • /new <id> <host> <cwd> — create a session\n"
    "  • /kill <id> — kill a session (asks to /confirm)\n"
    "  • /resume <id> — recreate a session from its stored claude session id"
)


async def cmd_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT)


def register(application: Application) -> None:
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_fallback))
