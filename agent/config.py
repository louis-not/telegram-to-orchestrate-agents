import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required env var: {name}")
    return value


SHARED_SECRET = _require("AGENT_SHARED_SECRET")
PORT = int(os.environ.get("AGENT_PORT", "8787"))
