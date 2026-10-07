# PRD — Workspace Mapping & On-Demand Session Provisioning

**Status:** approved for backlog — see §10 for how the open decisions in
the prior draft were resolved (operator approved moving to backlog
without specifying each one individually; defaults below were picked to
match this repo's existing conventions and security posture — flag any
that are wrong and they'll be revised)
**Owner:** admin.agentic@ismayagroup.com
**Related:** [prd.md](prd.md) (base fleet-controller PRD), [technical-concept.md](technical-concept.md)

## 1. Summary

Today, every session the hub controls has to already exist (`/new`) before
the operator can talk to it — you need to know the id, host, and cwd up
front. This feature lets the hub learn which directories on disk are
legitimate, hub-integrable **workspaces** (project checkouts it's allowed
to operate in) purely by observing sessions as they get created, and then
lets the operator start working in a workspace by name alone — "I'd like
to add X to oliv-workspace" — without ever having typed `/new`. The hub
resolves the workspace, spins up a tmux session with `claude
--permission-mode auto` in that workspace's path if one isn't already
running, gives it a short descriptive name, and relays the message (and
any future messages/images) into it.

## 2. Problem

- `/new <id> <host> <cwd>` requires the operator to remember and type an
  exact path every time, from a phone, for every project they might want
  to poke at. That's friction that defeats the "control everything from
  Telegram" goal of the base PRD.
- There's no durable notion of "projects I'm allowed to touch" — only
  "sessions that happen to exist right now." A session that gets killed
  loses the hub's memory of where that project even lives.
- The operator wants to describe a task in natural language ("modify
  oliv-workspace to...") and have the right session simply exist,
  rather than first provisioning it by hand.

## 3. Goals

- G1: Automatically learn workspace → path mappings from sessions that
  already get created (manually via `/new`, or auto-discovered local tmux
  sessions), with no separate registration step
- G2: Only register directories that opt in to being hub-integrable (not
  every directory a session happens to be `cd`'d into)
- G3: Let the operator list known workspaces and pick one explicitly
  (`/workspaces`, `/request <workspace>`)
- G4: Let the operator reach a workspace purely through natural language,
  mentioning it by name in a plain message, with no command at all
- G5: Reuse a workspace's existing live session instead of spawning a
  duplicate one every time it's referenced
- G6: Give auto-provisioned sessions a short, descriptive, human-readable
  name instead of an opaque id
- G7: Support passing non-text content (at minimum: images) into a
  workspace session, not just text
- G8: Every model this feature invokes (name generation, workspace-mention
  detection) is Sonnet or Haiku — never Opus (cost; project-wide rule)
- G9: A feature-shaped request (as opposed to a quick scoped task) gets
  planned before it gets built: PRD drafted and sent to the operator,
  discussed in chat, backlog generated from it, *then* a separate session
  executes the backlog — mirroring the workflow this repo's own CLAUDE.md
  already asks of this assistant

## 4. Non-goals

- Multiple concurrent sessions per workspace (v1 is one live session per
  workspace, same as today's one-tmux-session-per-id model)
- Auto-discovering workspaces by scanning the filesystem proactively —
  discovery only happens as a side effect of a session being created
- Any change to the existing `/new`/`/resume`/`/ask` id-based flow — this
  is an additive convenience layer, not a replacement
- Video/audio/document attachments beyond images (can follow the same
  mechanism later, but v1 only has to prove it works for images)

## 5. How workspace discovery works (proposed)

**Opt-in marker:** a workspace root is any directory containing a
`.creds.md` file. This repo already has two real examples:
`/home/lsnt/Repositories/oliv-v2/.creds.md` and
`/home/lsnt/Repositories/oliv-workspace/.creds.md`. Presence of this file
is the *only* signal the hub uses to decide a directory is hub-integrable
— no marker, no registration, even if a session's cwd is one of its
subdirectories.

**When discovery runs:** every time a session is created or observed —
`/new`, and `discovery.sync_local_sessions()`'s periodic auto-registration
of local tmux sessions — the hub walks upward from that session's `cwd`
toward `/` looking for the nearest `.creds.md`. If found, it registers
`workspace_name = <that directory's basename>` → `{path, host,
discovered_from: <session_id>}` in a new workspace registry (own JSON
file, same pattern as `sessions.json`).

**Naming collisions:** two different absolute paths with the same
basename (e.g. two checkouts both named `oliv-workspace` on different
hosts) — open question, see §9.

## 6. Functional requirements

### 6.1 Discovery & registry

- FR1: A new `WorkspaceRegistry` (mirrors `hub/registry.py`'s
  `SessionRegistry` shape) persists `{name: {path, host, discovered_from,
  registered_at}}` to `./var/workspaces.json` (see §10 — kept out of the
  repo root, unlike the pre-existing `sessions.json`/`audit.sqlite3`/
  `hub.lock`, which stay where they are rather than being moved as part of
  this feature)
- FR2: After any session creation (`/new`) or auto-discovery
  (`discovery.sync_local_sessions`), the hub checks for the nearest
  `.creds.md` walking up from that session's `cwd` and registers/updates
  the workspace entry if found
- FR3: Registration is silent by default (matches "auto-registered new
  local session" style discovery notifications already sent for sessions)

### 6.2 Listing & explicit selection

- FR4: `/workspaces` lists every registered workspace (name, path, host,
  and whether it currently has a live session), with tap-to-select buttons
  mirroring `/sessions`
- FR5: `/request <workspace>` resolves a workspace by name. If it has a
  live session, that session becomes the chat's active session (same
  mechanism as tapping a session button today). If not, it provisions one
  (§6.3) and makes *that* active.

### 6.3 Natural-language resolution & auto-provisioning

- FR6: A plain-text message that names a known workspace (fuzzy match,
  same normalization approach as `fallback.py`'s `_mentioned_sessions`) is
  resolved to that workspace without requiring `/request` first
- FR7: If the resolved workspace has a live session, the message is
  relayed into it exactly like today's active-session relay
- FR8: If it does not, the hub provisions a new tmux session in that
  workspace's path running `claude --permission-mode auto --model
  <configured sonnet/haiku model>`, names it (§6.4), registers it, and
  relays the message into it once it's up
- FR9: One live session per workspace — if a session already exists for a
  workspace, never spin up a second one; reuse/select the existing one
  instead

### 6.4 Session naming

- FR10: Auto-provisioned sessions get a short, descriptive name derived
  from the triggering message (e.g. "add-auth-middleware"), generated by a
  one-shot Haiku call in the same sandboxed, no-tools style as
  `hub/nlu.py`, not a plain id counter
- FR11: A name collision with an existing session id gets a numeric
  suffix rather than failing

### 6.5 Attachments

- FR12: An incoming Telegram photo directed at an active session (or a
  workspace resolved per FR6) is downloaded, saved under
  `./var/uploads/<workspace>/` **in the hub's own repo/working directory**
  (decided — see §10), and relayed as a text message referencing the
  saved file's absolute path, so the Claude Code session inside tmux can
  read it like any other file argument

### 6.6 Model constraints

- FR13: Every `claude` process this feature launches (naming calls,
  workspace-session launches) is configurable but defaults to and is
  restricted to a Sonnet or Haiku model id — enforced the same way
  `hub/nlu.py` already pins `NLU_MODEL`

### 6.7 PRD-first workflow for feature-shaped requests (planner / executor split)

A workspace session created to do a quick, scoped task (fix this bug, add
this one function) can just do it. But when the triggering message reads
as a **feature** request — new functionality, multiple moving pieces,
something with real design decisions in it, not a one-liner — the
provisioned session must not go straight to editing files. Instead:

- FR14: The hub-provisioned session classifies the triggering request as
  "simple task" vs. "feature" (open question: who decides this — the
  session's own judgment via its system prompt, matching how this very
  repo's `CLAUDE.md` already tells *this* assistant to work from specs, or
  an explicit operator signal like a `/feature` prefix — see §9.6)
- FR15: For a feature-shaped request, the session drafts a PRD (same
  shape as this document: Summary, Problem, Goals, Non-goals, FR/SR/NFR,
  Open decisions) and sends it back to the operator over Telegram — via
  the normal tmux pane relay, so it shows up as that session's reply, not
  a separate bot message
- FR16: The operator can reply in that same chat (same active-session
  relay already in place) to discuss and revise the PRD — no new command
  needed, this reuses FR6/FR7's existing message relay
- FR17: Once the operator signals the PRD is settled (exact signal is an
  open question, §9.7), the session generates a backlog from it (same
  shape as this repo's `docs/backlog.md`: per-item checklist referencing
  the PRD's FR/SR/NFR ids)
- FR18: Execution against that backlog happens in a **second** session —
  not the planning session continuing in the same context. The hub
  provisions a second tmux+`claude` session in the same workspace path,
  named to pair with the planner (e.g. `<workspace-slug>-plan` and
  `<workspace-slug>-build`), handed the approved PRD + backlog (as files
  on disk in the workspace, or pasted into its first prompt), and that
  session is the one that becomes active for implementation follow-ups
- FR19: Both the planning and execution sessions are subject to FR13 —
  Sonnet or Haiku only, no exception for "this one needs to think harder"

## 7. Security requirements

This feature turns a natural-language message into an action that
provisions a new always-on, `--permission-mode auto` Claude Code session
in a real project directory — meaningfully more powerful than today's
`/new`, which requires an explicit, deliberate command. The base PRD's
security principles (§7 of prd.md) apply in full, plus:

- SR1: Auto-provisioning (FR8) only ever targets a directory already
  carrying the `.creds.md` marker — never an arbitrary path inferred from
  conversation text
- SR2: Workspace resolution from free text (FR6) still runs behind the
  existing allowlist/rate-limit gates — no new bypass path
- SR3: (open decision, see §9) whether first-time auto-provisioning from
  free text additionally requires an explicit confirm step, the way `/kill`
  does today
- SR4: The workspace registry is re-validated against disk at use time
  (path still exists, `.creds.md` still present) before relaying into it —
  a workspace that's been deleted or had its marker removed fails closed,
  not silently stale

## 8. Non-functional requirements

- NFR1: Workspace lookup (by name, fuzzy-matched from free text) must be
  fast enough to run on every plain-text message without noticeable lag,
  same budget as today's `_mentioned_sessions` scan
- NFR2: `workspaces.json` survives a hub restart, same guarantee as
  `sessions.json` (NFR2 of the base PRD)

## 9. Open decisions

None remaining — all resolved by default per §10 below.

## 10. Decisions taken

- **Where uploads and the workspace registry live (decided):** both live
  in the hub's own repo/working directory, under a single `./var/`
  directory — `var/workspaces.json` and `var/uploads/<workspace>/` — not
  scattered as loose files at the repo root the way `sessions.json`,
  `audit.sqlite3`, and `hub.lock` currently are, and not written into each
  target workspace's repo either. One `var/` entry in `.gitignore` covers
  both, instead of a growing list of individually-ignored root-level
  files. (The pre-existing root-level state files are left as they are —
  this is a convention for *new* state this feature adds, not a retroactive
  cleanup of what's already there.)
- **Naming collisions across hosts (decided, default):** first-registered
  wins the bare name; a later registration with the same basename on a
  different host gets suffixed as `<name>@<host>`. Revisit if multi-PC use
  makes this confusing in practice (D1 in the base backlog is still open
  anyway, so this is untested beyond local-host for now).
- **Confirmation before auto-provisioning from free text (decided,
  default — resolves SR3):** **yes**, required. The first time a workspace
  is auto-provisioned from a plain message (not via `/request`), the hub
  asks for confirmation before launching the new session, same mechanism
  `/kill` already uses (`hub/confirm.py`). `/request <workspace>` is
  already an explicit, deliberate command and does **not** need this
  extra step. Rationale: this repo's own CLAUDE.md requires an explicit
  confirmation step for anything resembling remote code execution, and
  spinning up a new unattended `--permission-mode auto` agent from
  inferred intent qualifies.
- **Default model for provisioned sessions (decided, default):** Sonnet
  for sessions that actually write code (workspace sessions, planner,
  executor); Haiku for the lightweight one-shot calls (name generation,
  workspace-mention matching if it ever needs a model rather than plain
  string matching).
- **Discovery scope (decided, default):** local-only for v1, matching
  `discovery.py`'s existing local-only limitation. Revisit once D1 (second
  physical PC smoke test) happens for the base fleet controller.
- **Attachments beyond images (decided, default):** out of scope for v1,
  per §4.
- **Simple-vs-feature classification (decided, default — resolves
  FR14):** the provisioned session's own judgment, steered by its launch
  prompt/system context, decides whether a request is feature-shaped —
  no new operator-facing command for v1. Mirrors how this repo's own
  CLAUDE.md already governs this assistant's behavior with no special
  trigger syntax.
- **"PRD settled" signal (decided, default — resolves FR17):** an explicit
  `/approve` command, sent while the planning session is active, triggers
  backlog generation and the handoff to the executor session. Every PRD
  the planning session sends ends with "reply /approve when this looks
  right" so the signal is always visible, not just discoverable.

## 11. Out of scope (for now)

- Multiple concurrent sessions per workspace
- Proactive filesystem scanning for `.creds.md` files
- Remote-host workspace discovery (pending open decision §9.4)
- Non-image attachments
