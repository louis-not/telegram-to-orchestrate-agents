from telegram.ext import Application

from hub.handlers import ask, confirm_cmd, fallback, help, kill, new, resume, select, sessions, status


def register_all(application: Application) -> None:
    # fallback last: filters.TEXT & ~filters.COMMAND only matches what no
    # command handler already claimed, but keeping it last documents that.
    for module in (help, sessions, status, ask, new, kill, resume, confirm_cmd, select, fallback):
        module.register(application)
