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
| `/help` | Short command reference |
| `/sessions` | List all registered sessions + current state, with a tap-to-select button per session |
| `/ask <id> <message>` | Send `<message>` into session `<id>`, reply with captured output once settled |
| `/status <id>` | Capture and return current pane content |
| `/new <id> <host> <cwd>` | Create a tmux session, launch `claude --permission-mode auto` in it, register it — and make it the chat's active session |
| `/kill <id>` | Kill the tmux session (asks for `/confirm` first) |
| `/resume <id>` | Recreate the tmux session and `claude --resume=<claude_session_id>` — also becomes the active session |
| `/workspaces` | List known project workspaces (directories opted in via a `.creds.md` marker), with a tap-to-select button for any that already have a live session |
| `/request <workspace>` | Select a workspace's live session, or provision a new one if it doesn't have one yet — no `/confirm` needed, typing the command is itself the deliberate act |
| `/approve` | Only while a workspace-provisioned planning session is active: tells it to write a backlog from the PRD it drafted, then hands off to a new executor session in the same workspace |

### Conversation model

Local tmux sessions are auto-discovered and auto-pruned every 15s — a
session created outside `/new` shows up on its own, and one whose tmux
pane is gone drops out, both without a restart.

Once a session is **active** (via `/new`, `/resume`, `/request`, or tapping
a button under `/sessions`/`/workspaces`), every plain message goes
straight to it via `/ask` — the chat behaves like you're inside that
session. Tap "Stop talking to this session" to leave that mode. With
nothing active, plain messages go to a general-purpose assistant instead:
a sandboxed one-shot `claude -p` call (`hub/nlu.py`) with no tool access
and no MCP servers (`--disallowedTools` + `--strict-mcp-config`, verified
against real side-effects, not just the model's self-report) and a
neutral working directory, so it can discuss anything — including a
mentioned session's current pane content as read-only context — without
being able to act on it. This assistant keeps short-term memory of the
last few exchanges (stored in Telegram's own per-chat data, not a
separate store), so a follow-up reply like "sure" to its own question
still resolves — cleared on `/new`, since that's a deliberate switch into
direct session control. Replies everywhere are kept short and end with a
concrete next step; on a phone, a 3500-char terminal dump is not a reply.

### Workspaces & on-demand sessions

A directory becomes a hub-integrable **workspace** purely by containing a
`.creds.md` marker — no separate registration step. The hub discovers the
nearest one walking up from a session's cwd every time a session is
created (`/new`) or auto-discovered locally, and registers `<basename>` →
`{path, host}` (a same-named workspace on a different host gets suffixed
`<name>@<host>` rather than overwriting the first one).

Naming a known workspace in a plain message (no command, no active
session) resolves it: if it already has a live session, the message
relays straight into it; if not, the hub asks for `/confirm` before
spinning one up (`claude --permission-mode auto --model
<config.WORKSPACE_SESSION_MODEL>`), names it with a short Haiku-generated
slug, and relays the message once it's up. `/request <workspace>` does
the same resolution without the confirm step. A workspace is
re-validated against disk (path + `.creds.md` still present) immediately
before every relay or provision — one that's been deleted or had its
marker removed fails closed, not silently stale. A photo sent to an
active session or a workspace named in its caption is downloaded and
relayed as a file-path reference (`Image attached: <path>`), not pasted
binary content.

A freshly provisioned workspace session is told to classify the request
that triggered it: a quick scoped task, it just does; a feature-shaped
one, it drafts a PRD and ends it with a prompt to reply `/approve`.
Approving tells it to write a backlog to disk, then the hub provisions a
second, paired **executor** session in the same workspace to carry it out
— referencing the PRD/backlog by path, never pasting their contents.

## Security

- The bot token is a credential: lives only in `.env`, which is gitignored, never logged; this hub uses its own dedicated token, never shared with another bot/service
- Every command is checked against a hard allowlist of Telegram numeric user IDs before it's parsed — this is remote code execution on real machines, so this check is non-negotiable
- Every hub → agent HTTP call carries a shared-secret bearer token (`AGENT_SHARED_SECRET`); an agent rejects any request without a valid one — being on the same LAN is not treated as "trusted"
- Destructive commands (`/kill`, anything resembling `rm`, force pushes) issued remotely require a confirmation step, since there's no second human in the loop to catch a mistake
- The general-assistant fallback (`hub/nlu.py`) gets no tools and no MCP servers, not just a prompt telling it not to act — "no tools" in the prompt text alone did nothing in testing (it ran Bash anyway); only an explicit `--disallowedTools` list plus `--strict-mcp-config` actually blocks execution, verified against real file-write side effects rather than the model's own claims
- Auto-provisioning a workspace session from free text requires `/confirm` first, same gate as `/kill` — this spins up a new always-on `--permission-mode auto` agent in a real project directory, meaningfully more powerful than a read-only reply; `/request <workspace>` skips it only because typing the command is itself the deliberate act
- A workspace is re-validated against disk (path exists, `.creds.md` still present) immediately before every relay or provision, not just at registration time — a deleted workspace or one with its marker removed fails closed instead of silently operating on a stale path
- Every `claude` process this feature launches (naming, workspace sessions, the executor handoff) passes an explicit `--model` pinned to `config.WORKSPACE_SESSION_MODEL`/`config.NLU_MODEL` — Sonnet or Haiku only, never left to the CLI's own default, never Opus

## Project layout

```
hub/
  config.py                env vars: bot token, allowlist, monitor interval, registry/workspace paths, agent shared secret, NLU/workspace-session models
  registry.py               session registry (load/save sessions.json)
  workspace_registry.py     workspace registry (load/save var/workspaces.json), `.creds.md` walk-up resolver
  workspace_provision.py    workspace -> live session resolution and auto-provisioning; launch-prompt guidance for the PRD-first flow
  naming.py                 one-shot Haiku call that turns a triggering message into a short kebab-case session name
  matching.py               shared normalization/substring-match helper (session ids and workspace names alike)
  tmux.py                   local tmux wrapper: send-keys / capture-pane / new-session / kill-session
  transport.py              routes a command to local tmux.py, or an HTTP call to that session's agent
  monitor.py                poll-and-diff loop, classifies state transitions
  discovery.py              auto-registers new local tmux sessions (and their owning workspace) and auto-prunes dead ones, every 15s
  nlu.py                    sandboxed one-shot `claude -p` call behind the general-assistant fallback
  pane_format.py            strips decorative tmux border lines/padding (including mixed label+border lines) before truncating a pane for a reply
  security.py               allowlist gate — runs before every other handler
  ratelimit.py              per-user sliding-window rate limit (second line of defense)
  confirm.py                generic "reply /confirm" gate for destructive commands and free-text auto-provisioning
  activity.py               structured log line + sqlite audit row per command
  errors.py                 turns a transport exception into a readable Telegram reply
  lock.py                   single-instance guard (flock on ./hub.lock)
  logging_setup.py          stdout logging, secrets redacted from every line
  state.py                  process-wide registry/workspaces/monitor singletons
  handlers/                 one module per command (help, sessions, workspaces, status, ask, new, request, approve, kill, resume, confirm, select, attachments) plus the plain-text fallback
  __main__.py               entrypoint — builds the Application, wires everything above, polls Telegram
agent/
  config.py      env vars: shared secret, listen port
  app.py         Flask app: thin HTTP wrapper around hub/tmux.py, for non-hub PCs
  __main__.py    entrypoint — run this on every PC except the hub
docs/
  technical-concept.md          full design doc, decisions, out-of-scope items
  prd.md                        product requirements
  prd-workspace-mapping.md      PRD for workspace discovery, natural-language resolution, and on-demand session provisioning — implemented
  backlog.md                    per-item build status (base fleet controller)
  backlog-workspace-mapping.md  per-item build status (workspace mapping)
  agent-runbook.md              bringing up `agent/` on a new PC
  secrets-rotation.md           rotating TELEGRAM_BOT_TOKEN / AGENT_SHARED_SECRET
var/                            gitignored runtime state this feature adds: workspaces.json, uploads/<session_id>/
```

## Setup & run (hub)

Only two things are required: a Telegram bot and `startup.sh`.

1. **Create a Telegram bot.** Message [@BotFather](https://t.me/BotFather)
   on Telegram, send `/newbot`, follow the prompts, and copy the bot token
   it gives you. Then message [@userinfobot](https://t.me/userinfobot) (or
   any similar bot) to get your own numeric Telegram user ID — this is the
   only ID that will be allowed to control the hub.
2. **Configure.**
   ```bash
   cp .env.template .env
   chmod 600 .env   # holds live credentials — owner-read-write only
   ```
   Fill in `.env`:
   - `TELEGRAM_BOT_TOKEN` — from BotFather
   - `TELEGRAM_ALLOWED_USER_IDS` — your numeric user ID (comma-separate for more than one)
   - `AGENT_SHARED_SECRET` — only needed if you'll register a session on another PC (see below); generate with `python -c "import secrets; print(secrets.token_hex(32))"`
3. **Start it.**
   ```bash
   ./startup.sh
   ```
   This creates/activates `.venv`, installs dependencies, and runs
   `python -m hub` in the foreground. Stop with Ctrl-C.

That's it — message your bot on Telegram and send `/help`.

### Keep it running across reboots (optional)

To have the hub start automatically whenever the PC turns on, run it as a
systemd user service:

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/telegram-hub.service <<EOF
[Unit]
Description=Telegram-to-orchestrate-agents hub
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/startup.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

loginctl enable-linger "$USER"             # starts the service even when nobody is logged in
systemctl --user daemon-reload
systemctl --user enable --now telegram-hub.service
```

Useful afterwards:
```bash
systemctl --user status telegram-hub    # is it running?
systemctl --user restart telegram-hub   # restart (e.g. after editing .env)
journalctl --user -u telegram-hub -f    # tail logs
```

### Other PCs (optional)

Only needed if you want to control Claude Code sessions on more than one
machine. On every PC that isn't the hub: same clone, same `.env` (same
`AGENT_SHARED_SECRET`, pick a free `AGENT_PORT`), run `python -m agent`
instead of `./startup.sh`.

## Current status

Running live. Beyond the base backlog (`docs/backlog.md`: all commands,
allowlist/rate-limit gates, single-instance guard, structured+audit
logging, `/kill` confirmation, monitor → notifications), live usage
surfaced and closed several real gaps:

- Local tmux sessions auto-register and auto-prune, no restart needed
- `/sessions` has tap-to-select buttons; `/new`/`/resume` auto-select too,
  so a plain message reaches the right session with no `/ask <id>` typing
- Plain text with nothing selected goes to a general assistant
  (`hub/nlu.py`) instead of silence or a static reply — genuinely
  sandboxed (no tools, no MCP, neutral cwd), not just told not to act
- That assistant keeps short-term memory of the last few exchanges, so a
  follow-up reply to its own question resolves instead of landing orphaned
- Replies are sized for a phone and end with a next step, not a raw
  terminal dump — including the periodic monitor's proactive notifications,
  which used to send a raw, unfiltered pane capture (box-drawing borders
  and all) and now run through the same cleanup `/status`/`/ask` use
- `/help`

`docs/prd-workspace-mapping.md` (workspace discovery, natural-language
resolution, on-demand provisioning, PRD-first planning for feature-shaped
requests) is implemented end to end — `docs/backlog-workspace-mapping.md`
tracks it item by item.

Still open, and not doable from this one machine: a multi-PC smoke test
against a second physical PC (D1), a noise-level review of real
notifications after a few days of use (E4), and a live smoke test of the
workspace-mapping flow against a real `.creds.md`-marked project —
registration, natural-language resolution, confirm-gated provisioning,
and the `/approve` planner→executor handoff haven't been exercised
against the live Telegram/tmux stack yet, only import/compile-checked.

## Out of scope (for now)

- Controlling IDE-extension-spawned sessions directly (no stdio hook available) — transcript files only
- A web UI — Telegram chat is the only interface for v1
- Multi-user support — single authorized operator only
- Multiple concurrent sessions per workspace — one live session per workspace, same as the base one-tmux-session-per-id model
- Proactively scanning the filesystem for `.creds.md` — workspace discovery only happens as a side effect of a session being created
- Non-image attachments (video, audio, documents) — v1 only proves the mechanism works for photos
- Remote-host workspace discovery — local-only for v1, matching `discovery.py`'s existing local-only limitation
