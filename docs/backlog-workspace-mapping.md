# Backlog — Workspace Mapping & On-Demand Session Provisioning

Derived from [prd-workspace-mapping.md](prd-workspace-mapping.md). Each
item references the FR/SR/NFR/G it implements. Nothing here is built yet —
this is the plan, not a status report (contrast with
[backlog.md](backlog.md), which tracks the base fleet controller that's
already shipped).

All new runtime state this backlog adds lives under `./var/` (one
`.gitignore` entry), not as loose files at the repo root — see
prd-workspace-mapping.md §10.

## Epic A — Workspace registry & discovery

New module, same shape as `hub/registry.py`.

- [ ] **A1. `WorkspaceRegistry`** (`hub/workspace_registry.py`) — a
  `Workspace` dataclass (`name`, `path`, `host`, `discovered_from`,
  `registered_at`) plus a JSON-backed registry class mirroring
  `SessionRegistry`'s `load/get/put/all` shape, persisted to
  `var/workspaces.json`. New `config.WORKSPACE_REGISTRY_PATH` env var,
  default `./var/workspaces.json`. Wire into `hub/state.py` alongside
  `registry`/`monitor` so handlers reach it as `state.workspaces`. (FR1)
- [ ] **A2. `.creds.md` walk-up resolver** — a function that, given a
  `cwd`, walks upward toward `/` and returns the nearest directory
  containing `.creds.md`, or `None`. Stop at the filesystem root or the
  user's home directory, whichever comes first, so it never walks past
  `/home/<user>`. (§5, FR2)
- [ ] **A3. Hook into `/new`** — after `cmd_new` successfully creates and
  registers a session, run A2 against its `cwd`; if it resolves, register
  (or refresh) the workspace entry via A1. (FR2)
- [ ] **A4. Hook into local discovery** — same check inside
  `discovery.sync_local_sessions()` for each newly auto-registered local
  session. (FR2)
- [ ] **A5. Naming-collision handling** — when A1 registers a workspace
  whose basename already maps to a *different* path, suffix the new one
  as `<name>@<host>` instead of overwriting the first registration.
  (§10 decision)
- [ ] **A6. Silent registration** — no Telegram notification on workspace
  registration/refresh (distinct from session auto-registration, which
  already notifies) — confirm this is still desired once A3/A4 are live,
  since over-notifying was explicitly called out as a failure mode
  elsewhere in this project (base PRD FR8). (FR3)

## Epic B — Listing & explicit selection

- [ ] **B1. `/workspaces`** (`hub/handlers/workspaces.py`) — lists every
  registered workspace: name, path, host, and whether it currently has a
  live session (cross-reference `state.registry` by looking for a session
  whose `cwd` matches the workspace path). Tap-to-select buttons, same
  `InlineKeyboardMarkup` pattern as `hub/handlers/sessions.py`. (FR4)
- [ ] **B2. `/request <workspace>`** (`hub/handlers/request.py`) — resolves
  a workspace by exact/fuzzy name (reuse the normalization helper from C1
  below). If a live session already exists for it, set it active (same
  mechanism `select.py` already uses). If not, provision one (Epic C) —
  no confirmation step needed here, since `/request` is itself the
  deliberate action (§10 decision on SR3). (FR5)
- [ ] **B3. Register `workspaces` and `request` handlers** in
  `hub/handlers/__init__.py`'s `register_all`, before `fallback` (same
  ordering rule as every other command). (consistency with existing code)

## Epic C — Natural-language resolution & auto-provisioning

- [ ] **C1. Workspace-mention matching** — extract the normalization +
  substring-match helper already in `fallback.py`'s `_mentioned_sessions`
  into something both session-matching and workspace-matching can share
  (`hub/matching.py` or similar), so workspace names get matched the same
  way session ids already do. (FR6, NFR1)
- [ ] **C2. Resolve-before-fallback in `cmd_fallback`** — when no session
  is active and the message matches exactly one known workspace (C1): if
  it has a live session, relay into it (existing `ask_session` path); if
  not, go to C3. Ambiguous matches (more than one workspace mentioned) —
  fall through to the general NLU assistant unchanged, don't guess. (FR6,
  FR7)
- [ ] **C3. Confirm-then-provision for free-text triggers** — reuse
  `hub/confirm.py`'s existing "/confirm" gate: reply asking to confirm
  spinning up a new session for `<workspace>`, store the pending
  message+workspace, and only provision (C4) once confirmed. This is the
  one new path that needs it — `/request` (B2) does not. (SR3 resolved,
  §10 decision)
- [ ] **C4. Provisioning** — `transport.new_session` with
  `claude --permission-mode auto --model <config.WORKSPACE_SESSION_MODEL>`
  in the workspace's path, register the new session (named per Epic D),
  set it active, then relay the original triggering message into it.
  (FR8, FR13)
- [ ] **C5. One-session-per-workspace enforcement** — before C4 runs,
  double-check (not just at B2/C2 time — a race between two fast messages
  is possible) that no live session already maps to this workspace's path;
  if one appeared in the meantime, use it instead of creating a second.
  (FR9)
- [ ] **C6. Fail-closed revalidation** — immediately before C2/C4 act on a
  workspace, re-check the path still exists and still contains
  `.creds.md`; if not, remove the stale registry entry and reply that the
  workspace is no longer available instead of operating on a dead/altered
  path. (SR4)

## Epic D — Session naming

- [ ] **D1. Slug-generation call** (`hub/naming.py`) — one-shot
  `claude -p` call, same sandboxed/no-tools/disallowed-tools shape as
  `hub/nlu.py`, prompted to turn the triggering message into a short
  kebab-case slug (2-4 words). Uses `config.NLU_MODEL` (Haiku) — no new
  model config needed, this is exactly the kind of lightweight call that
  default already covers. (FR10, FR13, G8)
- [ ] **D2. Collision suffixing** — if the generated slug collides with an
  existing session id, append `-2`, `-3`, etc. until free. (FR11)
- [ ] **D3. Fallback on naming failure** — if D1's call errors or times
  out (mirrors `hub/nlu.py`'s own failure handling), fall back to a
  timestamp- or counter-based id rather than blocking provisioning on it.
  (robustness — not a numbered FR, but C4 depends on D1 never hard-failing)

## Epic E — Attachments (images)

- [ ] **E1. Photo handler** — new `MessageHandler(filters.PHOTO, ...)` in
  a `hub/handlers/attachments.py`, registered before `fallback`'s catch-all
  text filter (which doesn't match photos anyway, but keep the ordering
  convention). (FR12)
- [ ] **E2. Resolve target + save** — same active-session-or-workspace
  resolution as C2 applies to a photo message too (an attachment can
  arrive with a caption that names a workspace, or while a session is
  already active). Download via `bot.get_file`, save under
  `var/uploads/<workspace-or-session-id>/<timestamp>-<file_id>.jpg`.
  (FR12, §10 decision on `var/` location)
- [ ] **E3. Relay as a path reference** — send a text message into the
  target session's pane referencing the saved file's absolute path (e.g.
  `"Image attached: {path}"` plus the photo's caption if any), reusing
  `ask_session`'s existing send+poll+reply flow rather than a parallel
  code path. (FR12)
- [ ] **E4. No target resolved** — if a photo arrives with no active
  session and no workspace mentioned in its caption, reply asking which
  session/workspace it's for rather than silently dropping it or guessing
  (same "no silent drop" principle as `hub/errors.py`). (robustness)

## Epic F — Model constraints

- [ ] **F1. `config.WORKSPACE_SESSION_MODEL`** — new env var, default a
  Sonnet model id, used by C4's `transport.new_session` call. (FR13, G8,
  §10 decision)
- [ ] **F2. Audit that nothing launched by this feature can reach Opus** —
  grep/review pass once C4, D1, and G-epic sessions (below) are all wired,
  confirming every `claude`/`claude -p` invocation this feature adds
  passes an explicit `--model` pinned to `config.NLU_MODEL` or
  `config.WORKSPACE_SESSION_MODEL`, never left to the CLI's own default.
  (FR13, FR19, G8)

## Epic G — PRD-first workflow for feature-shaped requests

The highest-uncertainty epic — build and validate C/D/E/F first, since G
depends on provisioned sessions already working end-to-end. Treat G as a
v1.1 slice, not blocking the rest of this backlog.

- [ ] **G1. Launch-prompt guidance** — the prompt/system context a
  provisioned session (C4) starts with instructs it: for a feature-shaped
  request, draft a PRD (same section shape as this repo's own
  `docs/prd.md`) and send it back as its reply instead of editing files;
  for a scoped task, just do it. Classification is the session's own
  judgment, no new command. (FR14, §10 decision)
- [ ] **G2. PRD reply ends with the approval prompt** — the launch
  guidance (G1) tells the session to end any PRD it sends with "reply
  `/approve` when this looks right," making the handoff signal visible
  every time rather than only documented here. (FR15, FR17, §10 decision)
- [ ] **G3. Discussion stays in the same session** — no new code needed
  here beyond what C2/B2 already give you: once a workspace session is
  active, the operator's replies already relay into it via the existing
  `ask_session` path. Verify this explicitly once G1 is in place — this
  item is a test, not new code. (FR16)
- [ ] **G4. `/approve` command** (`hub/handlers/approve.py`) — only valid
  while a workspace-provisioned planning session is active for this chat;
  sends a fixed instruction into that session telling it to generate the
  backlog from the PRD it just discussed (same file, same directory, same
  shape as this repo's own `docs/backlog.md`) and write it to disk in the
  workspace. (FR17, §10 decision)
- [ ] **G5. Executor session provisioning** — once the planning session
  confirms the backlog file exists (poll the pane, same debounce pattern
  `ask_session` already uses, or check the file directly on disk), the hub
  provisions a second tmux+`claude` session in the same workspace path,
  named `<planner-slug>-build` pairing with the planner's
  `<planner-slug>-plan` (rename the planner post-hoc if D1 didn't already
  produce a `-plan`-suffixed name), and makes the executor session active
  going forward. (FR18)
- [ ] **G6. Executor session handoff content** — the executor's first
  prompt references the PRD and backlog files on disk in the workspace
  (not pasted inline) — same "point at files, don't paste walls of text
  into `send-keys`" principle `ask_session`'s truncation logic already
  reflects. (FR18)
- [ ] **G7. Model check** — confirm G5's `transport.new_session` call
  passes `config.WORKSPACE_SESSION_MODEL`, same as C4 — no separate path
  that could accidentally default to Opus. (FR19)

## Suggested order

1. **A1–A4** first — nothing else in this backlog has anything to look up
   without the registry existing and populating itself.
2. **B1–B3** next for a read-only, low-risk way to see workspaces in
   Telegram and sanity-check discovery is working before wiring
   auto-provisioning.
3. **D1–D3** before C4, since C4 depends on naming to register the new
   session sensibly.
4. **C1–C6** — the core auto-provisioning path, including the confirm gate
   (C3) and the revalidation (C6) — don't ship C4 without C3 and C6 both
   in place, since that combination is exactly what SR1–SR4 exist for.
5. **F1–F2** interleaved with C/D rather than saved for the end — easiest
   to verify the model constraint while each call is still fresh in mind.
6. **E1–E4** once C is solid — attachments reuse C's resolution logic, so
   building them first would mean redoing that logic twice.
7. **G1–G7** last, as its own slice — explicitly lower confidence (this is
   the newest, least-precedented part of the design) and not required for
   the rest of the feature to be useful on its own.
