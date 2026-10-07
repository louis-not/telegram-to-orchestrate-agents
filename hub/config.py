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

# Bearer token sent on every hub -> agent HTTP call (see agent/config.py).
# Only required once a non-"local" session is registered.
AGENT_SHARED_SECRET = os.environ.get("AGENT_SHARED_SECRET", "")
