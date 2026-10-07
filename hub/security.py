import logging

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from hub import config

logger = logging.getLogger(__name__)


async def allowlist_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Drops any update from a user not in config.ALLOWED_USER_IDS, silently.

    Registered as a group=-1 TypeHandler so it runs before every other
    handler; raising ApplicationHandlerStop here prevents those from firing.
    """
    user = update.effective_user
    if user is None or user.id not in config.ALLOWED_USER_IDS:
        logger.warning("dropped update from disallowed user_id=%s", user.id if user else None)
        raise ApplicationHandlerStop
