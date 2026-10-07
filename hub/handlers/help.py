from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

HELP_TEXT = (
    "Remote control for your Claude Code sessions.\n\n"
    "/sessions — list + tap one to select\n"
    "/new <id> <host> <cwd> — create, auto-selected\n"
    "/resume <id> — relaunch, auto-selected\n"
    "/status <id> — quick peek\n"
    "/ask <id> <msg> — message any session directly\n"
    "/kill <id> — asks /confirm first\n\n"
    "Once a session is selected (via /new, /resume, or a tap), your "
    "plain messages go straight to it. No selection? You get a general "
    "assistant instead.\n\n"
    "Try /sessions to pick one."
)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("help", cmd_help))
