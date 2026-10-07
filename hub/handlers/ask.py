import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import activity, errors, pane_format, state, transport

POLL_INTERVAL_SECONDS = 1
MAX_WAIT_SECONDS = 20
# Mobile-sized, not Telegram's 4096-char limit: a readable snippet, not a
# wall of raw terminal output.
REPLY_TRUNCATE_CHARS = 600


async def ask_session(update: Update, session_id: str, message: str) -> None:
    """Core /ask logic, reusable by the tap-to-select flow in fallback.py."""
    user_id = update.effective_user.id
    session = state.registry.get(session_id)
    if session is None:
        await update.effective_message.reply_text(f"no such session: {session_id}")
        activity.record(user_id, "/ask", session_id, "error: unknown session")
        return

    try:
        transport.send_keys(session, message)

        last_pane = None
        stable_count = 0
        waited = 0
        stabilized = False
        while waited < MAX_WAIT_SECONDS:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            waited += POLL_INTERVAL_SECONDS
            pane = transport.capture_pane(session)
            if pane == last_pane:
                stable_count += 1
                if stable_count >= 2:
                    stabilized = True
                    break
            else:
                stable_count = 0
            last_pane = pane

        final_pane = last_pane or ""
        truncated = pane_format.clean_snippet(final_pane, REPLY_TRUNCATE_CHARS)
        if stabilized:
            reply_text = f"{truncated}\n\nKeep going, or /status {session_id} for a fresh look."
            result = "ok"
        else:
            reply_text = f"Still working — here's the latest:\n{truncated}\n\nCheck back with /status {session_id} in a bit."
            result = "ok: did not stabilize within max wait"
        await update.effective_message.reply_text(reply_text)
    except Exception as exc:
        result = await errors.reply_failure(update, "/ask", exc)

    activity.record(user_id, "/ask", session_id, result)


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.effective_message.reply_text("usage: /ask <id> <message>")
        return
    session_id = context.args[0]
    message = " ".join(context.args[1:])
    await ask_session(update, session_id, message)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("ask", cmd_ask))
