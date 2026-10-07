from telegram.ext import Application

from hub.handlers import ask, confirm_cmd, kill, new, resume, sessions, status


def register_all(application: Application) -> None:
    for module in (sessions, status, ask, new, kill, resume, confirm_cmd):
        module.register(application)
