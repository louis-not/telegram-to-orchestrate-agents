# Agent startup runbook

Bringing up `agent/` on a new, non-hub PC and registering it with the hub.
See `README.md` for architecture.

## 1. Prerequisites

Python 3, `tmux`, and a `git clone` of this repo on the new PC.

## 2. Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Configure `.env`

```bash
cp .env.template .env
```

- `AGENT_SHARED_SECRET` — must exactly match the hub's `.env` value. The
  agent's `_check_auth` hook (`agent/app.py`) compares the request's
  `Authorization` header to `Bearer {config.SHARED_SECRET}`; a mismatch
  with what the hub sends (`hub/transport.py`) means every hub request
  gets a 401. One shared value across hub and all agents.
- `AGENT_PORT` — only set if the default `8787` (`agent/config.py`) is
  already taken. `TELEGRAM_*` vars are hub-only; leave blank here.

## 4. Run

```bash
python -m agent
```

Binds Flask to `0.0.0.0` on `AGENT_PORT` (`agent/__main__.py`) — reachable
from any machine on the LAN, not just the hub. The only gate is the shared
bearer token; there's no IP allowlist or TLS. Run this only on a trusted
LAN.

## 5. Register with the hub

The hub reads `SESSION_REGISTRY_PATH` (`hub/config.py`, default
`./sessions.json`). `hub/transport.py` routes a session via HTTP whenever
`session.host != "local"`, so `host` must be
`http://<lan-ip>:<AGENT_PORT>`. Add an entry matching `Session`
(`hub/registry.py`), per `sessions.example.json`:

```json
{
  "sessions": {
    "pc-b-builder": {
      "host": "http://192.168.1.42:8787",
      "tmux_session": "builder",
      "cwd": "/home/user/project",
      "claude_session_id": null
    }
  }
}
```

## 6. Smoke test

From the hub (Telegram):

```
/new pc-b-builder http://192.168.1.42:8787 /home/user/project
/status pc-b-builder
```

Pane content back means the agent is reachable and authenticated.
