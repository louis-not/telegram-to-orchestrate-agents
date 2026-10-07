# Secrets Rotation Runbook

Two secrets live in `.env`: `TELEGRAM_BOT_TOKEN` (hub only) and
`AGENT_SHARED_SECRET` (hub + every agent PC, must match exactly). Rotate
each as follows.

## Rotating `TELEGRAM_BOT_TOKEN`

1. In Telegram, talk to **@BotFather** and request a new token for the bot
   (`/revoke` or `/token`). This invalidates the old token immediately —
   there is no overlap period where both work.
2. Update `TELEGRAM_BOT_TOKEN` in the hub's `.env`.
3. Restart the hub process. `hub/lock.py` enforces a single instance via an
   `flock` on `./hub.lock`, so the **old process must fully exit before the
   new one starts** — the new process will fail fast with "another hub
   process is already running" if the old one is still holding the lock.
   A clean exit (Ctrl-C, `kill`, crash) releases the lock automatically
   since `flock` is tied to the process's file descriptors, so there's no
   stale-lock cleanup step needed afterward.
4. Expect a brief window where the bot is offline between stopping the old
   process and the new one coming up — this is unavoidable with
   long-polling (no second instance can hold the connection), so don't try
   to engineer a zero-downtime swap here; just do it at a low-traffic time.

## Rotating `AGENT_SHARED_SECRET`

This secret must be identical across the hub and every registered agent
PC's `.env`, so a naive one-at-a-time rotation will 401 everything in
between. Sequence it instead:

1. **Before restarting anything**, update `AGENT_SHARED_SECRET` in the
   hub's `.env` *and* in every agent PC's `.env` to the same new value.
   At this point all `.env` files are in sync again, but the running
   processes are still using the old value in memory.
2. Restart the hub and each agent process. Order doesn't matter: there's no
   live negotiation between hub and agent (see `hub/transport.py`, which
   sends `Authorization: Bearer {AGENT_SHARED_SECRET}` on every call, and
   `agent/app.py`'s `_check_auth`, which checks the request header against
   its own `config.SHARED_SECRET` on every request) — each side just reads
   its own `.env` on startup and validates independently.
3. The risk is forgetting to update one agent PC's `.env` before restarting
   it: that agent will come back up with the old secret and start
   401-ing every request from the hub. After rotating, do a quick check —
   run `/status` against one session on each host and confirm none of them
   come back with a 401.

## Handling secrets generally

Never commit `.env` — it's already covered by `.gitignore` (`.env` and
`.env.*`, with `.env.template` explicitly excepted). Never log these
values either; `hub/logging_setup.py` already installs a
`_RedactSecretsFilter` that strips `TELEGRAM_BOT_TOKEN` and
`AGENT_SHARED_SECRET` out of all log output before it's written.
