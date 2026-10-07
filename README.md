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
`tmux capture-pane` reads the rendered screen, and this works identically
whether the pane is local or reached over SSH. Sessions launched directly by
an IDE extension have no such hook and remain observable only via their
on-disk transcripts — **only tmux-hosted sessions are controllable.**

**Telegram is the cross-machine transport.** The Bot API is cloud-hosted, so
any machine with outbound internet access can reach it — no inbound ports,
VPN, or port forwarding between machines. Exactly one process ("the hub")
long-polls the bot token, since Telegram splits/loses updates if two pollers
share a token.

**The hub** is a single persistent process (on one "main" PC) that:

1. Keeps a registry of known sessions (id → host, tmux session name, cwd, Claude session id for resume)
2. Accepts commands from Telegram, from an allowlisted user ID only, and fans them out via local `tmux send-keys`/`capture-pane` or `ssh host "tmux ..."` for remote machines
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
                local tmux        ssh -> remote tmux
                send-keys/         send-keys/capture-pane
                capture-pane       on other PCs
                         |            |
               +---------------+  +---------------+
               | tmux: sessA   |  | tmux: sessX    |
               | claude --perm |  | claude --perm  |
               | -mode auto    |  | -mode auto     |
               +---------------+  +---------------+
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

- The bot token is a credential: lives only in `.env`, which is gitignored, never logged
- Every command is checked against a hard allowlist of Telegram numeric user IDs before it's parsed — this is remote code execution on real machines, so this check is non-negotiable
- SSH access from the hub to remote PCs should use a dedicated, scoped key (forced command / restricted shell), not a general login key
- Destructive commands (`/kill`, anything resembling `rm`, force pushes) issued remotely deserve a confirmation step, since there's no second human in the loop to catch a mistake

## Project layout

```
hub/
  config.py      env vars: bot token, allowlist, monitor interval, registry path
  registry.py    session registry (load/save sessions.json)
  tmux.py        send-keys / capture-pane / new-session / kill-session, local or over ssh
  monitor.py     poll-and-diff loop, classifies state transitions
  __main__.py    entrypoint (bot wiring is still a TODO)
docs/
  technical-concept.md   full design doc, open decisions, out-of-scope items
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env   # fill in TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_USER_IDS
cp sessions.example.json sessions.json   # optional: seed the registry
```

## Run

```bash
python -m hub
```

## Current status

Scaffolding only: config loading, session registry, tmux wrapper, and a
monitor-loop skeleton exist. The Telegram bot itself (command handlers,
`getUpdates` polling, wiring the monitor loop to proactive notifications) is
not yet implemented. See `docs/technical-concept.md` §7 for open decisions
(scope for v1, hub persistence mechanism, monitor interval, notification
heuristics) that are worth settling before that build-out.

## Out of scope (for now)

- Controlling IDE-extension-spawned sessions directly (no stdio hook available) — transcript files only
- A web UI — Telegram chat is the only interface for v1
- Multi-user support — single authorized operator only
