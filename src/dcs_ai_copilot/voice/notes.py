from __future__ import annotations

import re


_NOTE_RE = re.compile(
    r"^\s*(?:note|notes|notera|anteckna|anteckning)\b\s*:?\s*(?P<text>.+?)\s*$",
    re.IGNORECASE,
)


def parse_voice_note(text: str) -> str | None:
    match = _NOTE_RE.match(text)
    if not match:
        return None

    note_text = re.sub(r"\s+", " ", match.group("text")).strip(" .")
    return note_text or None
