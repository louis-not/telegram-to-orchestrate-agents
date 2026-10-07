# PRD — Telegram Fleet Controller for Claude Code Sessions

**Status:** draft
**Owner:** admin.agentic@ismayagroup.com
**Related:** [technical-concept.md](technical-concept.md), prior art: `bangkax-agent-api` (same org, a Telegram/WhatsApp bot in front of headless `claude -p`)

> **Resolved risk (was blocking):** this repo's `.env` originally had the
> same `TELEGRAM_BOT_TOKEN` as `bangkax-agent-api`'s `.env`, which would
> have caused `getUpdates` to split/lose updates between the two pollers
> (§4 of technical-concept.md, SR5 below). A new, dedicated token has since
> been created via @BotFather and is now in `.env` — SR9 is satisfied.

## 1. Summary

A Telegram bot that gives one authorized operator a single remote surface to
monitor and control Claude Code sessions running across multiple PCs, from
anywhere, without being at the keyboard.

## 2. Problem

Claude Code sessions run unattended, in tmux, on one or more machines. Right
now there is no way to check on them or steer them without physically sitting
at the machine running them. A session that finishes, errors, or gets stuck
waiting on something goes unnoticed until someone happens to look.

## 3. Goals

- G1: See the status of every registered session, across every registered PC, from one place
- G2: Send a message into any specific session remotely and get its resulting output back
- G3: Get proactively notified in Telegram when a session needs attention (finished / errored / stuck / unexpected prompt)
- G4: Spawn and kill sessions remotely
- G5: Support more than one PC from day one — this is a fleet controller, not a single-machine tool
- G6: Be unusable by anyone except the one authorized operator

## 4. Non-goals

- A web UI (Telegram chat is the only interface)
- Multi-user / multi-operator support
- Controlling IDE-extension-spawned sessions directly (observe-only via transcript files)
- Running tasks that aren't inside a Claude Code session

## 5. Users

Single operator (the authorized Telegram user). No other audience.

## 6. Functional requirements

### 6.1 Multi-PC support

All PCs are on the same local network. No SSH anywhere in this design.

- FR1: The hub runs on exactly one machine ("main") and reaches every other
  registered PC over a direct HTTP call to a small **agent** process running
  on that PC (see technical-concept.md §5.3); no SSH keys, no remote shell
- FR2: A session registry entry identifies `host` (`local`, or the agent's
  `http://<lan-ip>:<port>` base URL), `tmux_session` name, `cwd`, and the
  Claude session id for resume
- FR3: Every command (`/sessions`, `/ask`, `/status`, `/new`, `/kill`,
  `/resume`) works identically regardless of which host the target session
  lives on — the operator never needs to know or care how the hub reaches it
- FR4: If an agent is unreachable (connection refused, timeout, auth
  failure), the bot reports that clearly instead of hanging or silently
  dropping the command

### 6.2 Monitoring

- FR5: A monitor loop ticks on a configurable interval, capturing every
  registered pane and diffing it against its last-seen snapshot
- FR6: Each pane is classified into one of: working, idle (no new content),
  idle (new content since last check), awaiting-input / unexpected prompt,
  errored
- FR7: On a state transition worth surfacing, the bot pushes a Telegram
  message with enough context to act on without needing to run `/status`
  first (which session, what changed, tail of the output)
- FR8: Pure "still working" ticks with no state change produce no message —
  noise is a failure mode, not a feature
- FR9: `/sessions` returns the live state of every registered session in one
  message, grouped or labeled by host

### 6.3 Control

- FR10: `/ask <id> <message>` sends `<message>` into session `<id>` and
  replies once the session's pane output settles (i.e. stops changing for a
  short debounce window), not immediately after sending
- FR11: `/new <id> <host> <cwd>` creates a tmux session on `<host>`, launches
  `claude --permission-mode auto` in `<cwd>`, and registers it
- FR12: `/kill <id>` kills the session's tmux pane
- FR13: `/resume <id>` recreates the tmux pane and runs
  `claude --resume=<claude_session_id>` using the id stored in the registry
- FR14: All managed sessions run with `--permission-mode auto` since no
  human is present to approve prompts

## 7. Security requirements (non-negotiable)

Same principle as `bangkax-agent-api`: the bot must be structurally incapable
of acting for anyone but the operator — not just prompted to refuse.

| Layer | Mechanism | What it stops |
|---|---|---|
| 1. Chat allowlist | `TELEGRAM_ALLOWED_USER_IDS`, checked by numeric user id before any parsing | Strangers, forwarded messages, group chatter |
| 2. Dedicated token | This hub gets its own `TELEGRAM_BOT_TOKEN`, never shared with another service | `getUpdates` split/loss between two pollers (see risk note in §1) |
| 3. Destructive-action confirmation | `/kill` and similar require an explicit confirm step | A mistaken command with no second human to catch it |
| 4. Agent auth | Shared-secret bearer token on every hub→agent HTTP call, even on the trusted LAN | A compromised/misconfigured device on the same network calling an agent directly |
| 5. Audit log | Every command + target + action logged locally | After-the-fact review; detects a compromised allowlisted account |

- SR1: Every inbound Telegram update is checked against
  `TELEGRAM_ALLOWED_USER_IDS` by numeric Telegram user ID — **before** any
  command parsing or dispatch happens. This check has no bypass path.
- SR2: Messages from any user ID not on the allowlist are silently ignored
  (no error reply) — do not confirm to an unauthorized sender that the bot
  is listening or why their message was rejected
- SR3: The allowlist check gates on user ID, not chat ID — a group chat or
  forwarded message must not be able to smuggle commands through
- SR4: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USER_IDS` are read from
  `.env` only; `.env` is gitignored and never logged, echoed back in a
  Telegram message, or included in error output
- SR5: Exactly one process polls the bot token at a time (`getUpdates`
  deliveries are split unpredictably across concurrent pollers) — the hub
  enforces single-instance operation
- SR6: Every hub→agent HTTP request carries a shared-secret bearer token
  (set in each agent's own `.env`, matching a value the hub holds per
  registered PC); an agent rejects any request without a valid token —
  "same LAN" is not treated as "trusted"
- SR7: Destructive commands (`/kill`, and any future command that resembles
  `rm`, force-push, or similar) require an explicit confirmation step
  (e.g. reply "yes" or a second `/confirm`) before executing
- SR8: All actions taken (command received, session targeted, action
  executed) are logged locally for audit, with the token/credentials
  redacted from logs
- SR9: This hub uses its own `TELEGRAM_BOT_TOKEN`, created fresh via
  @BotFather, never reused from another bot/service — **done**, see §11

## 8. Non-functional requirements

- NFR1: Monitor loop interval is configurable (`MONITOR_INTERVAL_SECONDS`,
  default `600`); balances responsiveness against Telegram API rate limits
  and per-tick HTTP round-trip cost to other PCs' agents
- NFR2: The hub must survive a restart without losing the session registry
  (persisted to disk). Recoverable via a dedicated tmux session on the main
  PC (decided, §11) — not a one-off foreground process with no restart path
- NFR3: A single remote PC being unreachable must not block monitoring or
  control of sessions on other PCs
- NFR4: Latency for `/status` and `/ask` should be dominated by the actual
  HTTP/tmux round-trip to the target agent, not by hub overhead

## 9. Success criteria

- Operator can, from a phone with only Telegram installed, see the state of
  every session across all registered PCs within one `/sessions` call
- Operator is notified of a finished/stuck/errored session without having
  polled for it
- Zero commands executed from a non-allowlisted user ID in testing or
  production
- A remote PC going offline and coming back is handled without manual hub
  restart

## 10. Conventions carried over from `bangkax-agent-api`

That project is the closest prior art (same org, same credential pattern)
and is worth matching unless there's a reason not to:

- Python + `uv` for dependency management, not raw `pip`/`venv`
- `python-telegram-bot` for the bot layer, long polling only, no public ingress
- A small sqlite file as the single-writer audit/state store (here: command log, not conversation sessions)
- `.env` mode `600`, owned by the service user, same as `TELEGRAM_BOT_TOKEN` handling there

Deploy differs from bangkax-agent-api on one point (decided below): the hub
runs inside its own **dedicated tmux session** rather than a systemd
service, matching how the sessions it manages are already run.

## 11. Decisions taken

- **Scope for v1 (decided):** multi-PC from the start, not local-only-first.
  All PCs are on the same local network — see §6.1's local-agent-over-HTTP
  model (no SSH, no off-LAN machines in scope).
- **Hub persistence (decided):** a dedicated tmux session on the "main" PC,
  not a systemd service. Consistent with how every managed session already
  runs; `tmux attach` is the operator's own escape hatch if the hub itself
  misbehaves.
- **Monitor loop interval (decided):** `MONITOR_INTERVAL_SECONDS=600` (10
  minutes) is the default, set in `.env`.
- **Notification heuristics (decided, deferred):** no precise
  working/idle/errored classification logic for v1 — ship the simplest
  "pane changed since last tick" diff first (FR5–FR8 as written) and refine
  heuristics once real noise/signal patterns are observed in use.
- **Confirmation flow for destructive commands (decided):** yes, required
  (SR7 stands) — exact mechanics (reply "yes" vs. a `/confirm` command) are
  an implementation detail, not a product decision; default to whichever is
  less code unless it proves confusing in practice.
- **Bot token (decided, done):** a new, dedicated `TELEGRAM_BOT_TOKEN` has
  been created via @BotFather and is in `.env` — SR9 is satisfied.

## 12. Out of scope (for now)

- Controlling IDE-extension-spawned sessions directly
- A web UI
- Multi-user support
