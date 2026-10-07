"""Shared helpers for turning a raw tmux pane capture into something worth
reading on a phone — wide panes (~200+ cols) mean a naive "last N chars"
is mostly box-drawing border lines, not actual content.
"""

_BORDER_CHARS = set("─━│┃—-=_ ")


def _is_decorative(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and set(stripped) <= _BORDER_CHARS


def clean_snippet(pane: str, max_chars: int) -> str:
    """Drops decorative border lines and padding, then returns the last max_chars."""
    content_lines = [line.strip() for line in pane.splitlines() if not _is_decorative(line)]
    content_lines = [line for line in content_lines if line]
    cleaned = "\n".join(content_lines)
    return cleaned[-max_chars:] if len(cleaned) > max_chars else cleaned
