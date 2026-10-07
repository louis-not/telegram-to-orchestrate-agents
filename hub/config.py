import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required env var: {name}")
    return value


BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_IDS = {
    int(uid) for uid in _require("TELEGRAM_ALLOWED_USER_IDS").split(",") if uid.strip()
}
MONITOR_INTERVAL_SECONDS = int(os.environ.get("MONITOR_INTERVAL_SECONDS", "600"))
SESSION_REGISTRY_PATH = os.environ.get("SESSION_REGISTRY_PATH", "./sessions.json")
WORKSPACE_REGISTRY_PATH = os.environ.get("WORKSPACE_REGISTRY_PATH", "./var/workspaces.json")

# Bearer token sent on every hub -> agent HTTP call (see agent/config.py).
# Only required once a non-"local" session is registered.
AGENT_SHARED_SECRET = os.environ.get("AGENT_SHARED_SECRET", "")

# Model used to answer plain-text (non-command) messages: a one-shot
# `claude -p` subprocess, not an API call — reuses the CLI's own login,
# same as every other `claude` invocation this hub launches.
NLU_MODEL = os.environ.get("NLU_MODEL", "claude-haiku-4-5-20251001")

# Model for workspace-provisioned sessions (planner, executor, and any
# session that actually writes code) — see docs/prd-workspace-mapping.md
# §10: Sonnet or Haiku only, never Opus (cost; project-wide rule, G8/FR13).
WORKSPACE_SESSION_MODEL = os.environ.get("WORKSPACE_SESSION_MODEL", "claude-sonnet-5")
