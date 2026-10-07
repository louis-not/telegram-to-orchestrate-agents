# Telegram-to-Orchestrate-Agents — Technical Concept

## 1. Problem

Multiple Claude Code sessions run concurrently across one or more PCs (VS Code
extension sessions, terminal sessions, tmux sessions). There is currently no
way to:

- See all live sessions and their status (idle / working / stuck) from one place
- Send a prompt to a specific session without physically switching windows/machines
- Get proactively notified when a session finishes a task, errors, or stalls
- Do any of the above remotely (away from the PC), e.g. from a phone

## 2. Goal

Build a Telegram bot that acts as a remote control surface for a fleet of
Claude Code sessions, with **this session (the orchestrator)** able to:

1. List all known sessions across all registered machines
2. Inspect a session's current state/output
3. Send a message/instruction into a specific session
4. Be told, unprompted, when a session needs attention
5. Spawn/kill sessions
6. Operate across multiple PCs, not just the local one

All managed sessions run with `--permission-mode auto` (no manual approval
prompts) since there's no human sitting at the keyboard to click "allow."

## 3. Why tmux is the integration point

Claude Code sessions launched directly by the VS Code extension communicate
over stdio pipes owned by the extension — there is no external hook into
them. Sessions launched inside **tmux**, however, expose a stable interface:

- `tmux send-keys` — inject text/keystrokes into the session as if typed
- `tmux capture-pane` — read the current rendered screen content
- `tmux list-sessions` / `display-message` — enumerate sessions, get cwd, etc.

This requires no modification to Claude Code itself and works identically
whether it's run on the local machine or wrapped by a small HTTP agent on
another PC (§5.3). **Constraint: only tmux-hosted sessions are
controllable.** VS Code-extension-spawned sessions
remain observable only (via their on-disk transcripts in
`~/.claude/projects/**/*.jsonl`), not controllable.

## 4. Why Telegram's Bot API works as the cross-PC transport

Telegram's Bot API is cloud-hosted. Any machine with outbound internet access
can poll `getUpdates` or receive a webhook — no inbound ports, VPN, or port
forwarding needed on either PC. This sidesteps NAT/firewall issues that would
otherwise complicate a "control PC A from PC B" design.

**Important constraint:** Telegram guarantees exactly-once delivery per
poller. If two processes poll the same bot token with `getUpdates`
simultaneously, updates get split/lost between them unpredictably. Therefore
there must be exactly **one** poller process for the bot (the "hub"); it is
responsible for fanning commands out to whichever machine/session they target.

## 5. Proposed architecture

```
                         Telegram Bot API (cloud)
                                   |
                         long-poll getUpdates
                                   |
                     +-------------------------+
                     |     Hub process         |   <- single long-running process
                     |  (runs on PC A, "main")  |
                     |                          |
                     |  - session registry      |
                     |  - command router        |
                     |  - monitor loop          |
                     +------------+-------------+
                            |            |
                   local tmux         HTTP, same LAN
                   send-keys/          (no SSH)
                   capture-pane             |
                            |            v
                  +---------------+  +----------------+
                  | tmux: sessA   |  | agent (PC B)   |
                  | claude --perm |  | tiny HTTP svc  |
                  | -mode auto    |  | wraps local    |
                  +---------------+  | tmux           |
                                     +-------+--------+
                                             |
                                       local tmux
                                       send-keys/capture-pane
                                             |
                                     +---------------+
                                     | tmux: sessX    |
                                     | claude --perm  |
                                     | -mode auto     |
                                     +---------------+
```

All machines are on the same local network — there is no remote/off-network
PC in scope, and no SSH anywhere in the design. Each non-hub PC runs a small
long-lived **agent** process (same repo, different entrypoint) that wraps
*its own* tmux only; the hub reaches it over a plain HTTP call to
`http://<pc-b-lan-ip>:<port>/...`. The hub remains the only process that
talks to Telegram — agents never touch the Telegram API, so the
one-poller-per-token constraint (§4) is unaffected by how many PCs are
registered.

### 5.1 Hub process

A single persistent process, Python + `python-telegram-bot` (decided — see
PRD §10), running inside its own dedicated tmux session on the main PC
(decided — see PRD §11), responsible for:

- Long-polling Telegram for new messages from the **authorized user only**
  (hard filter on Telegram numeric user ID — this is remote code execution on
  real machines, so this check is non-negotiable and happens before any
  command is parsed)
- Parsing commands and routing them to the right session/machine
- Running a periodic monitor tick (e.g. every N seconds) that captures each
  registered pane, diffs it against last-seen content, and classifies state
  (idle / working / awaiting-input / errored) using simple heuristics (prompt
  glyph `❯` idle vs spinner/"Worked for Ns" lines vs tmux pane activity flag)
- Pushing a Telegram message proactively when a session's state changes in a
  way that matters (task finished, error surfaced, unexpected prompt)

### 5.2 Session registry

A small persisted list (JSON/YAML) of known sessions:

```json
{
  "sessions": {
    "ask-wilson": {
      "host": "local",
      "tmux_session": "ask-wilson",
      "cwd": "/home/lsnt/Repositories/nexus-workspace/nexus-dashboard",
      "claude_session_id": "07e72f69-ee9f-4c3f-be6c-48693f80aa6a"
    },
    "pc-b-builder": {
      "host": "http://192.168.1.42:8787",
      "tmux_session": "builder",
      "cwd": "/home/user/project",
      "claude_session_id": "..."
    }
  }
}
```

Storing `claude_session_id` lets a killed/crashed tmux pane be revived with
`claude --resume=<id>` without losing conversation history (as already
demonstrated manually in this session).

### 5.3 Non-hub machines (local agent)

No SSH anywhere. Each non-hub PC runs a small long-lived **agent** process
(same repo, separate entrypoint, its own dedicated tmux session like the
hub) that exposes a minimal HTTP API over the LAN:

- `POST /sessions/<id>/send-keys` — inject text/keystrokes into a local tmux pane
- `GET /sessions/<id>/capture` — return the current rendered pane content
- `POST /sessions/<id>/new` — create a tmux session, launch `claude --permission-mode auto` in it
- `POST /sessions/<id>/kill` — kill the tmux session

The hub's registry stores that agent's base URL as the session's `host`
instead of `ssh://...`. Since this is a private LAN, the agent still
requires a shared-secret bearer token (set via its own `.env`, matching a
value the hub also holds) on every request — "same network" is not the
same as "trusted," and this is still remote code execution if the LAN has
any other device on it.

### 5.4 Commands (initial set)

| Command | Effect |
|---|---|
| `/sessions` | List all registered sessions + current state |
| `/ask <id> <message>` | Send `<message>` into session `<id>`, reply with captured output once settled |
| `/status <id>` | Capture and return current pane content |
| `/new <id> <host> <cwd>` | Create a new tmux session + launch `claude --permission-mode auto` in it, register it |
| `/kill <id>` | Kill the tmux session |
| `/resume <id>` | Recreate tmux session and `claude --resume=<claude_session_id>` |

### 5.5 Monitor loop

Runs independently of incoming commands:

1. For each registered session, capture pane
2. Compare to last captured snapshot
3. Classify: still working (spinner/"Worked for Ns" present) / idle at prompt
   with new content since last check / idle with no change (nothing to
   report) / looks like an error or unexpected permission prompt
4. On a state transition worth surfacing, send a Telegram message summarizing
   what changed, so the user doesn't have to poll manually

## 6. Security considerations

- Telegram bot token is a credential — store in an env var or local-only
  config file, never commit to the repo, never log it
- Hard allowlist on Telegram **user ID** (not just chat ID) before executing
  any command
- Because this grants effectively arbitrary command execution on real
  machines (via whatever the Claude sessions are told to do), no "open to
  anyone who finds the bot" mode should ever exist
- Hub → agent HTTP calls require a shared-secret bearer token (§5.3); no
  unauthenticated endpoint on an agent, even on a trusted LAN
- Consider rate limiting / confirmation step for destructive commands
  (`/kill`, anything that resembles `rm`, force pushes, etc.) issued
  remotely over Telegram, since there's no second human in the loop to catch
  a mistaken command the way there is in an interactive terminal session

## 7. Decisions taken

All items that used to be open here are now decided — see
[prd.md](prd.md) §11 for the authoritative record:

- Telegram bot token: created via @BotFather, dedicated to this project (not shared with any other bot)
- No SSH anywhere: all PCs are on the same LAN; non-hub PCs run a local HTTP agent instead (§5.3)
- Scope for v1: multi-PC from the start
- Hub persistence: dedicated tmux session on the main PC
- Hub language/runtime: Python (`python-telegram-bot`)
- Monitor loop interval: 600 seconds default
- Proactive-notification heuristics: deferred — ship the simple "pane changed since last tick" diff first, tune later

## 8. Out of scope (for now)

- Controlling VS Code-extension-spawned sessions directly (no stdio hook
  available) — these remain observable via transcript files only
- A web UI — Telegram chat is the only interface for v1
- Multi-user support — single authorized operator only
