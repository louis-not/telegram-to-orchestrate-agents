import logging

from telegram import Update
from telegram.ext import Application, ApplicationHandlerStop, ContextTypes, TypeHandler

from hub import activity, config, discovery, handlers, lock, logging_setup, ratelimit, security, state

logger = logging.getLogger(__name__)

DISCOVERY_INTERVAL_SECONDS = 15


async def _rate_limit_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is not None and not ratelimit.allow(user.id):
        logger.warning("rate limit exceeded for user_id=%s", user.id)
        await update.effective_message.reply_text("slow down — rate limit exceeded, try again shortly.")
        raise ApplicationHandlerStop


async def _notify_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    for session_id, text in state.monitor.tick():
        for user_id in config.ALLOWED_USER_IDS:
            await context.bot.send_message(chat_id=user_id, text=f"[{session_id}] {text}")
        activity.record(0, "monitor.tick", session_id, "notified")


async def _discovery_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    for session_id in discovery.sync_local_sessions():
        activity.record(0, "discovery.sync", session_id, "auto-registered")
        for user_id in config.ALLOWED_USER_IDS:
            await context.bot.send_message(chat_id=user_id, text=f"auto-registered new local session: {session_id}")


def main() -> None:
    lock.acquire()
    logging_setup.configure()

    state.init(config.SESSION_REGISTRY_PATH)
    logger.info("loaded %d session(s) from %s", len(state.registry.all()), config.SESSION_REGISTRY_PATH)

    application = Application.builder().token(config.BOT_TOKEN).build()
    application.add_handler(TypeHandler(Update, security.allowlist_gate), group=-2)
    application.add_handler(TypeHandler(Update, _rate_limit_gate), group=-1)
    handlers.register_all(application)

    application.job_queue.run_repeating(_notify_job, interval=config.MONITOR_INTERVAL_SECONDS, first=config.MONITOR_INTERVAL_SECONDS)
    application.job_queue.run_repeating(_discovery_job, interval=DISCOVERY_INTERVAL_SECONDS, first=5)

    application.run_polling()


if __name__ == "__main__":
    main()
