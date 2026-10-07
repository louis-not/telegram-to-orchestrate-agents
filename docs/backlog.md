# Development Backlog — Telegram Fleet Controller

Derived from [prd.md](prd.md) and [technical-concept.md](technical-concept.md).
Each item references the FR/SR/NFR it implements. Status reflects what's
already scaffolded in the repo vs. what's still to build.

**2026-10-07:** Epics A–C, and D2/D3/E1–E3/F1–F3 implemented and smoke-tested
locally (real tmux session, sqlite audit log, confirm/rate-limit logic — see
commit history on `feat/bot-core`). Still genuinely open, and not doable from
a single dev box: **D1** (needs a second physical LAN machine), **D4**
(stretch, deferred), **E4** (needs days of real production traffic to judge
notification noise), and **F4** (needs a live, resumable `claude` session to
test against — the registry/tmux mechanics are verified, the end-to-end
`claude --resume` behavior is not).

## Epic A — Telegram bot core

Nothing here exists yet; this is the actual bot process the rest of the repo is scaffolding for.

- [x] **A1. Bot process skeleton** — wire up `python-telegram-bot`'s
  `Application`, long-polling `getUpdates`, inside `hub/__main__.py`.
  (FR... / foundation for all of Epic B)
- [x] **A2. Allowlist gate** — a single `before`/filter hook that checks
  `update.effective_user.id` against `config.ALLOWED_USER_IDS` before any
  handler runs; non-matching updates are dropped with no reply.
  (SR1, SR2, SR3 — do this first, every other handler depends on it being correct)
- [x] **A3. Single-instance guard** — fail fast on startup (or acquire a
  lock file) if another hub process is already polling, instead of
  silently racing `getUpdates` with it. (SR5)
- [x] **A4. Structured logging** — one log line per inbound update (user id,
  command, target session) and per outbound action, with
  token/secret values redacted. (SR8)

## Epic B — Session control commands

Registry (`hub/registry.py`) and transport (`hub/transport.py`) already
exist; this epic is the command handlers that call them.

- [x] **B1. `/sessions`** — list every registered session with its last-known
  state, grouped/labeled by host. (FR9)
- [x] **B2. `/status <id>`** — capture and return the current pane content
  for one session. (FR3, FR4)
- [x] **B3. `/ask <id> <message>`** — send text into a session via
  `transport.send_keys`, then poll `capture_pane` until output stops
  changing (debounce window) before replying. (FR10)
- [x] **B4. `/new <id> <host> <cwd>`** — register a session and call
  `transport.new_session` to create the tmux pane (local) or hit the
  agent's `/new` endpoint (remote), launching
  `claude --permission-mode auto`. (FR11, FR14)
- [x] **B5. `/kill <id>`** — call `transport.kill_session`. Gate behind the
  confirmation flow from C3 before it actually executes. (FR12)
- [x] **B6. `/resume <id>`** — recreate the tmux pane and run
  `claude --resume=<claude_session_id>` using the id stored in the
  registry. (FR13)
- [x] **B7. Clear error surfacing** — any transport failure (agent
  unreachable, tmux session missing, timeout) becomes a readable Telegram
  reply, never a hang or a silent drop. (FR4)

## Epic C — Safety rails

- [x] **C1. Destructive-command confirmation** — `/kill` (and any future
  command that resembles it) asks for an explicit "yes" reply or a
  `/confirm` before executing. Mechanics are an implementation detail
  (PRD §11 decided this is required, not how). (SR7)
- [x] **C2. Audit log** — append one row per command (who, what, target,
  result) to a local sqlite file, matching the single-writer pattern used
  in `bangkax-agent-api`. (SR8)
- [x] **C3. Rate limiting** — basic per-user command rate limit as a second
  line of defense if the allowlisted account is ever compromised.

## Epic D — Agent service (multi-PC)

`agent/app.py` already has the four endpoints; this epic is making it a
real deployable piece and hardening it.

- [ ] **D1. Smoke test the agent end-to-end** — run `python -m agent` on a
  second machine on the LAN, register it in `sessions.json` with its
  `http://<lan-ip>:<port>` host, and exercise `/ask`, `/status`, `/new`,
  `/kill` against it from the hub. (FR1, FR2, FR3)
- [x] **D2. Timeouts and clear failures** — confirm `hub/transport.py`'s
  10s timeout produces a sane error (not a stack trace) when an agent is
  down, and that one unreachable PC doesn't block commands to others.
  (FR4, NFR3)
- [x] **D3. Agent startup docs** — short runbook: how to install/run the
  agent on a new PC (clone, `.env` with matching `AGENT_SHARED_SECRET`,
  `python -m agent`), how to register it with the hub.
- [ ] **D4. (stretch) Agent as a service** — currently `python -m agent` is
  manual; consider the same "dedicated tmux session" pattern the hub uses
  (PRD §11) so an agent survives a PC reboot too.

## Epic E — Monitor loop & proactive notifications

`hub/monitor.py` has the tick/diff skeleton; this epic wires it to Telegram
and to the real scheduler.

- [x] **E1. Scheduler wiring** — run `Monitor.tick()` on a repeating timer
  (`MONITOR_INTERVAL_SECONDS`, default 600s) inside the same
  `python-telegram-bot` event loop (e.g. `JobQueue`), not a separate thread
  fighting over the registry. (FR5, NFR1)
- [x] **E2. Push notifications** — turn each `Monitor.tick()` result into
  an actual `sendMessage` call to the allowlisted user's chat id. (FR7, G3)
- [x] **E3. State classification v1** — ship the simple "pane changed since
  last tick" diff that's already in `monitor.py`; explicitly skip the
  richer working/idle/errored classification for v1 (PRD §11 decided to
  defer this). (FR6, FR8)
- [ ] **E4. Noise check** — after a few days of real use, review what
  actually got notified vs. what should have been silent, and only then
  consider refining the heuristic (the deferred half of FR6).

## Epic F — Hardening & ops

- [x] **F1. Registry persistence sanity** — confirm `sessions.json` survives
  a hub restart (kill `-9` the tmux pane, restart, check registry intact).
  (NFR2)
- [x] **F2. `.env` permissions** — `chmod 600 .env` on every machine running
  hub or agent, matching the `bangkax-agent-api` convention. (SR4)
- [x] **F3. Secrets rotation runbook** — one paragraph on how to rotate
  `TELEGRAM_BOT_TOKEN` or `AGENT_SHARED_SECRET` without downtime surprises.
- [ ] **F4. Resume-after-crash test** — kill a managed Claude session's
  tmux pane directly, then confirm `/resume` brings it back with history
  via `claude --resume`. (FR13)

## Suggested order

1. **A2** (allowlist) before anything else touches a live token — security first, always.
2. **A1 → B1 → B2** to get a usable read-only bot (`/sessions`, `/status`) end to end on local-only sessions.
3. **B3, B4, B6** to round out control commands; **B5 + C1** together since `/kill` shouldn't ship without its confirmation step.
4. **D1** as soon as a second PC is available to test against — don't let the multi-PC path go untested until the end.
5. **E1–E3** once commands are stable — proactive notifications are the payoff feature, but they're noise without a solid base.
6. **A3, A4, C2, C3, F1–F4** as hardening, interleaved wherever convenient rather than saved entirely for last.
