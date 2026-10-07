"""Shared helper so a transport failure always becomes a readable Telegram
reply (B7) instead of a hang or an unhandled-exception silent drop.
"""

import logging

from requests.exceptions import RequestException
from telegram import Update

logger = logging.getLogger("hub.errors")


async def reply_failure(update: Update, command: str, exc: Exception) -> str:
    """Logs exc and sends the user a short, non-leaky error reply.

    Returns the result string (for activity.record's "result" column).
    """
    logger.exception("%s failed", command)
    if isinstance(exc, RequestException):
        text = "that session's agent is unreachable right now. Try again shortly."
    elif isinstance(exc, KeyError):
        text = "unknown session id."
    else:
        text = "something went wrong running that command."
    await update.effective_message.reply_text(text)
    return f"error: {exc}"
