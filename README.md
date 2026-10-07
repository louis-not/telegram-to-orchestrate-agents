# telegram-to-orchestrate-agents

A Telegram bot that lets you remotely monitor and control a fleet of Claude
Code sessions — from your phone, away from any of the machines they're
running on.

## The problem

Multiple Claude Code sessions run concurrently across one or more PCs. There
is no way today to:

- See all live sessions and their status (idle / working / stuck) from one place
- Send a prompt into a specific session without physically switching to that window/machine
- Get notified proactively when a session finishes, errors, or gets stuck
- Do any of this remotely

## How it works

**tmux is the control point.** A Claude Code session launched inside a tmux
pane exposes a stable interface: `tmux send-keys` injects text as if typed,
`tmux capture-pane` reads the rendered screen. Sessions launched directly by
an IDE extension have no such hook and remain observable only via their
on-disk transcripts — **only tmux-hosted sessions are controllable.**

**Telegram is the remote transport.** The Bot API is cloud-hosted, so the
hub machine just needs outbound internet to reach it — no inbound ports, VPN,
or port forwarding. Exactly one process ("the hub") long-polls the bot
token, since Telegram splits/loses updates if two pollers share a token.

**All PCs live on the same local network — no SSH.** Every other PC runs a
small long-lived **agent** process that wraps its own local tmux only and
exposes it over a minimal, token-authenticated HTTP API. The hub reaches
each one with a plain HTTP call to its LAN address.

**The hub** is a single persistent process (on one "main" PC) that:

1. Keeps a registry of known sessions (id → host, tmux session name, cwd, Claude session id for resume)
2. Accepts commands from Telegram, from an allowlisted user ID only, and fans them out via local `tmux send-keys`/`capture-pane` directly, or an HTTP call to that PC's agent
3. Runs a monitor loop that periodically captures each pane, diffs it against the last snapshot, classifies state (working / idle / awaiting-input / errored), and pushes a Telegram message when something changes that's worth surfacing

```
                    Telegram Bot API (cloud)
                              |
                      long-poll getUpdates
                              |
                  +-------------------------+
                  |       Hub process        |  <- one long-running process
                  |  registry · router ·     |
                  |  monitor loop            |
                  +------------+-------------+
                         |            |
                local tmux        HTTP, same LAN
                send-keys/         (no SSH)
                capture-pane            |
                         |              v
               +---------------+  +----------------+
               | tmux: sessA   |  | agent (PC B)   |
               | claude --perm |  | wraps its own  |
               | -mode auto    |  | local tmux     |
               +---------------+  +-------+--------+
                                          |
                                    local tmux
                                          |
                                  +---------------+
                                  | tmux: sessX    |
                                  | claude --perm  |
                                  | -mode auto     |
                                  +---------------+
```

All managed sessions run with `--permission-mode auto`, since there's no
human at the keyboard to click "allow."

## Commands (v1)

| Command | Effect |
|---|---|
| `/sessions` | List all registered sessions + current state |
| `/ask <id> <message>` | Send `<message>` into session `<id>`, reply with captured output once settled |
| `/status <id>` | Capture and return current pane content |
| `/new <id> <host> <cwd>` | Create a tmux session, launch `claude --permission-mode auto` in it, register it |
| `/kill <id>` | Kill the tmux session |
| `/resume <id>` | Recreate the tmux session and `claude --resume=<claude_session_id>` |

## Security

- The bot token is a credential: lives only in `.env`, which is gitignored, never logged; this hub uses its own dedicated token, never shared with another bot/service
- Every command is checked against a hard allowlist of Telegram numeric user IDs before it's parsed — this is remote code execution on real machines, so this check is non-negotiable
- Every hub → agent HTTP call carries a shared-secret bearer token (`AGENT_SHARED_SECRET`); an agent rejects any request without a valid one — being on the same LAN is not treated as "trusted"
- Destructive commands (`/kill`, anything resembling `rm`, force pushes) issued remotely require a confirmation step, since there's no second human in the loop to catch a mistake

## Project layout

```
hub/
  config.py        env vars: bot token, allowlist, monitor interval, registry path, agent shared secret
  registry.py      session registry (load/save sessions.json)
  tmux.py          local tmux wrapper: send-keys / capture-pane / new-session / kill-session
  transport.py     routes a command to local tmux.py, or an HTTP call to that session's agent
  monitor.py       poll-and-diff loop, classifies state transitions
  security.py      allowlist gate — runs before every other handler
  ratelimit.py      per-user sliding-window rate limit (second line of defense)
  confirm.py        generic "reply /confirm" gate for destructive commands
  activity.py       structured log line + sqlite audit row per command
  errors.py         turns a transport exception into a readable Telegram reply
  lock.py           single-instance guard (flock on ./hub.lock)
  logging_setup.py  stdout logging, secrets redacted from every line
  state.py          process-wide registry/monitor singletons
  handlers/         one module per command (sessions, status, ask, new, kill, resume, confirm)
  __main__.py       entrypoint — builds the Application, wires everything above, polls Telegram
agent/
  config.py      env vars: shared secret, listen port
  app.py          Flask app: thin HTTP wrapper around hub/tmux.py, for non-hub PCs
  __main__.py     entrypoint — run this on every PC except the hub
docs/
  technical-concept.md   full design doc, decisions, out-of-scope items
  prd.md                 product requirements
  backlog.md             per-item build status
  agent-runbook.md       bringing up `agent/` on a new PC
  secrets-rotation.md    rotating TELEGRAM_BOT_TOKEN / AGENT_SHARED_SECRET
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env   # fill in TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS, AGENT_SHARED_SECRET
chmod 600 .env           # it holds live credentials — owner-read-write only
cp sessions.example.json sessions.json   # optional: seed the registry
```

On every PC that isn't the hub: same clone, same `.env` (same
`AGENT_SHARED_SECRET`, pick a free `AGENT_PORT`), run `python -m agent`
instead of `python -m hub`.

## Run

```bash
python -m hub     # on the main PC
python -m agent   # on every other registered PC
```

## Current status

The bot is implemented: all six commands, the allowlist/rate-limit gates,
the single-instance guard, structured+audit logging, the `/kill`
confirmation flow, and the monitor loop wired to proactive Telegram
notifications. See `docs/backlog.md` for the item-by-item build status —
notably still open: an actual multi-PC smoke test against a second physical
machine (D1), and a noise-level review of real-world notifications after a
few days of use (E4), neither of which can be done from a single dev box.

## Out of scope (for now)

- Controlling IDE-extension-spawned sessions directly (no stdio hook available) — transcript files only
- A web UI — Telegram chat is the only interface for v1
- Multi-user support — single authorized operator only
