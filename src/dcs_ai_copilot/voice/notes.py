from __future__ import annotations

import re


_NOTE_RE = re.compile(
    r"^\s*(?:note|notes|notera|anteckna|anteckning)\b\s*:?\s*(?P<text>.+?)\s*$",
    re.IGNORECASE,
)

_CLEAR_NOTES_RE = re.compile(
    r"^\s*(?:clear|clear note|clear notes|rensa|rensa notes|rensa anteckningar|radera notes|radera anteckningar)\s*[.!?]?\s*$",
    re.IGNORECASE,
)


def parse_voice_note(text: str) -> str | None:
    match = _NOTE_RE.match(text)
    if not match:
        return None

    note_text = re.sub(r"\s+", " ", match.group("text")).strip(" .")
    return note_text or None


def is_clear_notes_command(text: str) -> bool:
    cleaned_text = re.sub(r"\s+", " ", text).strip()
    return bool(_CLEAR_NOTES_RE.match(cleaned_text))
