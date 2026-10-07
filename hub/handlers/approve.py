from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from hub import activity, config, errors, state, transport, workspace_provision
from hub.handlers.ask import ask_session
from hub.registry import Session

BACKLOG_INSTRUCTION = (
    "The PRD above is approved. Generate a backlog from it now — same file "
    "shape as this repo's own docs/backlog.md (a per-item checklist "
    "referencing the PRD's FR/SR/NFR ids) — and write it to disk in this "
    "workspace. Reply once it's done with the path you wrote it to."
)


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    active = context.user_data.get("active_session")

    if not active or not workspace_provision.is_workspace_session(active):
        await update.effective_message.reply_text("no active planning session to approve.")
        activity.record(user_id, "/approve", active, "error: no planning session")
        return

    session = state.registry.get(active)
    if session is None:
        context.user_data.pop("active_session", None)
        await update.effective_message.reply_text(f"{active} no longer exists.")
        activity.record(user_id, "/approve", active, "error: unknown session")
        return

    await ask_session(update, active, BACKLOG_INSTRUCTION)

    try:
        base = active[: -len("-plan")] if active.endswith("-plan") else active
        executor_name = f"{base}-build"
        existing = state.registry.all()
        if executor_name in existing:
            suffix = 2
            while f"{executor_name}-{suffix}" in existing:
                suffix += 1
            executor_name = f"{executor_name}-{suffix}"

        new_session = Session(host=session.host, tmux_session=executor_name, cwd=session.cwd)
        transport.new_session(new_session, f"claude --permission-mode auto --model {config.WORKSPACE_SESSION_MODEL}")
        state.registry.put(executor_name, new_session)
        context.user_data["active_session"] = executor_name

        handoff_message = (
            f"Continue implementation in {session.cwd}: review the PRD and backlog files "
            "the planning session just wrote in this workspace, then start executing the backlog."
        )
        await ask_session(update, executor_name, handoff_message)
        result = "backlog + executor provisioned"
    except Exception as exc:
        result = await errors.reply_failure(update, "/approve", exc)

    activity.record(user_id, "/approve", active, result)


def register(application: Application) -> None:
    application.add_handler(CommandHandler("approve", cmd_approve))
