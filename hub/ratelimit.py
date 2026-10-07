"""Per-user sliding-window rate limit (C3): a second line of defense if the
allowlisted account is ever compromised, independent of the allowlist gate.
"""

import time
from collections import defaultdict, deque

WINDOW_SECONDS = 60.0
MAX_COMMANDS_PER_WINDOW = 20

_history: dict[int, deque] = defaultdict(deque)


def allow(user_id: int) -> bool:
    now = time.time()
    history = _history[user_id]
    while history and now - history[0] > WINDOW_SECONDS:
        history.popleft()
    if len(history) >= MAX_COMMANDS_PER_WINDOW:
        return False
    history.append(now)
    return True
