from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import confirm


async def cmd_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    result = await confirm.resolve(user_id)
    if result is None:
        await update.effective_message.reply_text("nothing pending to confirm (or it expired).")


def register(application: Application) -> None:
    application.add_handler(CommandHandler("confirm", cmd_confirm))
