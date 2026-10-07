from telegram.ext import Application

from hub.handlers import ask, confirm_cmd, fallback, kill, new, resume, sessions, status


def register_all(application: Application) -> None:
    # fallback last: filters.TEXT & ~filters.COMMAND only matches what no
    # command handler already claimed, but keeping it last documents that.
    for module in (sessions, status, ask, new, kill, resume, confirm_cmd, fallback):
        module.register(application)
