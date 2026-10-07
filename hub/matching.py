"""Normalization + substring-match helper shared by the fallback assistant
(matching mentioned sessions) and workspace resolution (matching mentioned
workspace names) — same logic, generalized over whatever list of known ids
is passed in.
"""

import re


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def mentioned(message: str, known_ids: list[str]) -> list[str]:
    normalized_message = normalize(message)
    return [kid for kid in known_ids if normalize(kid) and normalize(kid) in normalized_message]
