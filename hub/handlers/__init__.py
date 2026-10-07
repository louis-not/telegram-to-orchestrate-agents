from telegram.ext import Application

from hub.handlers import (
    approve,
    ask,
    attachments,
    confirm_cmd,
    fallback,
    help,
    kill,
    new,
    request,
    resume,
    select,
    sessions,
    status,
    workspaces,
)


def register_all(application: Application) -> None:
    # fallback last: filters.TEXT & ~filters.COMMAND only matches what no
    # command handler already claimed, but keeping it last documents that.
    # attachments (filters.PHOTO) doesn't overlap fallback's text filter,
    # but registering it before fallback keeps the same documented ordering.
    for module in (
        help,
        sessions,
        workspaces,
        status,
        ask,
        new,
        request,
        approve,
        kill,
        resume,
        confirm_cmd,
        select,
        attachments,
        fallback,
    ):
        module.register(application)
