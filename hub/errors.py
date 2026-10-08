"""Shared helper so a transport failure always becomes a readable Telegram
reply (B7) instead of a hang or an unhandled-exception silent drop.
"""

import logging

from requests.exceptions import RequestException
from telegram import Update

logger = logging.getLogger("hub.errors")


def failure_text(command: str, exc: Exception) -> str:
    """Logs exc and returns a short, non-leaky error message for it —
    the text-building half of reply_failure, usable by a caller that
    doesn't have an Update to reply through directly (e.g. a shared
    handler reached from both a command and a callback query)."""
    logger.exception("%s failed", command)
    if isinstance(exc, RequestException):
        return "that session's agent is unreachable right now. Try again shortly."
    elif isinstance(exc, KeyError):
        return "unknown session id."
    else:
        return "something went wrong running that command."


async def reply_failure(update: Update, command: str, exc: Exception) -> str:
    """Logs exc and sends the user a short, non-leaky error reply.

    Returns the result string (for activity.record's "result" column).
    """
    await update.effective_message.reply_text(failure_text(command, exc))
    return f"error: {exc}"
