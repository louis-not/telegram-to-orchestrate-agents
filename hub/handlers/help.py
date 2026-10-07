from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

HELP_TEXT = (
    "This chat is a remote control surface for your Claude Code sessions.\n\n"
    "Commands:\n"
    "  • /sessions — list sessions, with a tap-to-select button per session\n"
    "  • /new <id> <host> <cwd> — create + launch a session; you're "
    "immediately talking to it, no /ask needed\n"
    "  • /resume <id> — recreate a session from its stored claude session "
    "id; also puts you straight into it\n"
    "  • /status <id> — one-off capture of a session's current output\n"
    "  • /ask <id> <message> — send a message to a specific session "
    "regardless of what's currently active\n"
    "  • /kill <id> — kill a session (asks you to /confirm first — the "
    "only command with a confirmation step)\n\n"
    "How the conversation works:\n"
    "Once a session is active (via /new, /resume, or tapping a button "
    "under /sessions), every plain message you send goes straight into "
    "that session — the whole chat behaves like you're inside it, same "
    "as the design calls for. Tap \"Stop talking to this session\" to "
    "leave that mode. Switching to another session (/new, /resume, or a "
    "different tap) just replaces whichever one was active.\n\n"
    "If nothing is active, plain messages go to a general assistant "
    "instead — it can see your sessions' current state for context, but "
    "it has no tools and can't act on anything."
)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("help", cmd_help))
