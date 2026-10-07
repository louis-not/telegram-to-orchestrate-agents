"""Generic "are you sure" gate for destructive commands (C1).

A handler that wants confirmation calls request() instead of acting
immediately; a later /confirm from the same user pops and runs the pending
action. Single pending action per user by design — a second destructive
command simply replaces the first rather than queuing.
"""

import time
from dataclasses import dataclass
from typing import Awaitable, Callable

TTL_SECONDS = 30.0

Action = Callable[[], Awaitable[str]]


@dataclass
class _Pending:
    description: str
    action: Action
    expires_at: float


_PENDING: dict[int, _Pending] = {}


def request(user_id: int, description: str, action: Action) -> None:
    _PENDING[user_id] = _Pending(description, action, time.time() + TTL_SECONDS)


async def resolve(user_id: int) -> str | None:
    """Pops and runs the pending action for user_id, returning its result.

    Returns None (nothing run) if there was no pending action or it expired.
    """
    pending = _PENDING.pop(user_id, None)
    if pending is None or time.time() > pending.expires_at:
        return None
    return await pending.action()


def pending_description(user_id: int) -> str | None:
    pending = _PENDING.get(user_id)
    if pending is None or time.time() > pending.expires_at:
        return None
    return pending.description
