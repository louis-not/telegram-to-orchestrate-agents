"""Shared helpers for turning a raw tmux pane capture into something worth
reading on a phone — wide panes (~200+ cols) mean a naive "last N chars"
is mostly box-drawing border lines, not actual content.
"""

import re

_BORDER_CHARS = set("─━│┃—-=_ ")
# A line can mix border chars with a real label (e.g. a titled box's header
# row: "[id] ──── TITLE ──") — not fully decorative, but the dash runs
# inside it are still just framing. Box-drawing characters never appear in
# real text, so any run of them collapses unconditionally; plain ASCII
# look-alikes (-=_) only collapse at 4+ in a row, so normal hyphenated
# words/flags ("shift-tab", "--model") survive untouched.
_BOX_DRAWING_RUN_RE = re.compile(r"[─━│┃—]+")
_ASCII_BORDER_RUN_RE = re.compile(r"[=_-]{4,}")


def _is_decorative(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and set(stripped) <= _BORDER_CHARS


def clean_snippet(pane: str, max_chars: int) -> str:
    """Drops decorative border lines/runs and padding, then returns the last max_chars."""
    content_lines = [line.strip() for line in pane.splitlines() if not _is_decorative(line)]
    content_lines = [_BOX_DRAWING_RUN_RE.sub(" ", line) for line in content_lines]
    content_lines = [_ASCII_BORDER_RUN_RE.sub(" ", line).strip() for line in content_lines]
    content_lines = [line for line in content_lines if line]
    cleaned = "\n".join(content_lines)
    return cleaned[-max_chars:] if len(cleaned) > max_chars else cleaned
