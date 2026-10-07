from hub import pane_format, transport
from hub.registry import SessionRegistry

# Mobile-sized, matching /status's PANE_REPLY_CHARS: a readable snippet,
# not a wall of raw terminal output (border lines, blank padding).
NOTIFICATION_CHARS = 500


class Monitor:
    """Polls registered panes and detects state transitions worth notifying on."""

    def __init__(self, registry: SessionRegistry):
        self._registry = registry
        self._last_snapshot: dict[str, str] = {}

    def last_known(self, session_id: str) -> str | None:
        """Most recent captured pane content for session_id, or None if never polled."""
        return self._last_snapshot.get(session_id)

    def tick(self) -> list[tuple[str, str]]:
        """Returns (session_id, notification_text) pairs for sessions worth surfacing."""
        notifications = []
        for session_id, session in self._registry.all().items():
            try:
                pane = transport.capture_pane(session)
            except Exception as exc:
                notifications.append((session_id, f"failed to capture pane: {exc}"))
                continue

            previous = self._last_snapshot.get(session_id)
            self._last_snapshot[session_id] = pane
            if previous is not None and pane != previous:
                notifications.append((session_id, pane_format.clean_snippet(pane, NOTIFICATION_CHARS)))
        return notifications
