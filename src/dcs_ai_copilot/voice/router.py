"""Deterministic routing after STT; note bodies are never normalized."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.voice.notes import is_clear_notes_command, parse_voice_note

_DIGITS = dict(zip(
    "zero one two three four five six seven eight nine".split(), "0123456789"))
_DIGITS.update({"oh": "0", "niner": "9"})
# Only after EAT: words STT substitutes for spoken digits in a time.
_EAT_DIGITS = {**_DIGITS, "to": "2", "too": "2", "tree": "3", "for": "4", "fife": "5", "won": "1"}
_TEENS = dict(zip("ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
                  "eighteen nineteen".split(), (str(n) for n in range(10, 20))))
_TENS = dict(zip("twenty thirty forty fifty sixty".split(), "23456"))
_EAT_FILLER = {"at", "is", "time", "the", "minute", "minutes"}


def _eat_digits(words: list[str]) -> str:
    """'three two', 'thirty two', '32', 'sixty' and 'fourteen thirty two' all read as digits."""
    out = []
    index = 0
    while index < len(words):
        word = words[index]
        following = words[index + 1] if index + 1 < len(words) else ""
        if word in _EAT_FILLER:
            pass
        elif word in _TENS:
            unit = _EAT_DIGITS.get(following, following if following.isdigit() else "")
            if len(unit) == 1 and unit != "0":
                out.append(_TENS[word] + unit)
                index += 1
            else:
                out.append(_TENS[word] + "0")
        elif word == "hundred":
            out.append("00")
        else:
            out.append(_TEENS.get(word, _EAT_DIGITS.get(word, word)))
        index += 1
    return "".join(out)


@dataclass(frozen=True)
class Command:
    kind: str
    value: str = ""
    data: dict[str, object] | None = None

    @property
    def route_name(self) -> str:
        if self.kind == "view":
            return "CASE3_VIEW" if self.value == "case3" else "NOTES_VIEW"
        if self.kind == "theme":
            return "DAY_MODE" if self.value == "day" else "NIGHT_MODE"
        return {"note": "NOTE", "clear_notes": "CLEAR_NOTES",
                "crossing": "CASE3_CROSSING", "eat": "CASE3_EAT",
                "reset_case3": "CASE3_RESET", "assignment": "CASE3_ASSIGNMENT",
                "commence": "CASE3_COMMENCE", "clock_sync": "CASE3_CLOCK_SYNC",
                "invalid_case3": "CASE3_INVALID"}.get(self.kind, "NONE")


def normalize_command(text: str) -> str:
    """Normalize a matching copy only; raw transcripts and note bodies stay intact."""
    cleaned = re.sub(r"[^\w\s:]", " ", text.lower())
    cleaned = " ".join(cleaned.split())
    cleaned = re.sub(r"\be\s+a\s+t\b", "eat", cleaned)
    cleaned = re.sub(r"\bd\s+m\s+e\b", "dme", cleaned)
    cleaned = re.sub(r"\bf\s+b\b", "fb", cleaned)
    return cleaned


_FIELD = re.compile(r"\b(?:marshal radial|marshal dme|expected approach time|approach button|"
                    r"push time|final bearing|radial|marshal|dme|angels|time|eat|button|"
                    r"fb|tacan|icls)\b")
_FIELD_NAMES = {"marshal": "radial", "marshal radial": "radial", "radial": "radial",
                "marshal dme": "dme", "dme": "dme", "angels": "angels",
                "time": "eat", "push time": "eat", "expected approach time": "eat",
                "eat": "eat", "button": "button", "approach button": "button",
                "final bearing": "fb", "fb": "fb", "tacan": "tacan", "icls": "icls"}


def _number(words: str) -> int:
    tokens = words.split()
    if not tokens:
        raise ValueError("Missing CASE III assignment value")
    digits = _eat_digits(tokens)
    if not digits.isascii() or not digits.isdigit():
        raise ValueError("Invalid CASE III assignment value")
    return int(digits)


def parse_assignment(cleaned: str) -> dict[str, object] | None:
    """Parse one or several labeled readback fields as one transaction."""
    cleaned = re.sub(r"^(?:case3|case (?:three|tree|free|iii|3))\s+", "", cleaned)
    matches = list(_FIELD.finditer(cleaned))
    if not matches or matches[0].start() != 0:
        return None
    values: dict[str, object] = {}
    for index, match in enumerate(matches):
        name = _FIELD_NAMES[match.group()]
        if name in values:
            raise ValueError("Duplicate CASE III assignment field")
        raw = cleaned[match.end(): matches[index + 1].start() if index + 1 < len(matches) else None].strip()
        if match.group() == "marshal":
            digits = _eat_digits(raw.split())
            if not digits.isdigit() or len(digits) not in {3, 5, 6}:
                raise ValueError("Marshal needs a three-digit radial and optional distance")
            values["radial"] = int(digits[:3])
            if len(digits) > 3:
                values["dme"] = int(digits[3:])
            if not 0 <= values["radial"] <= 359 or ("dme" in values and not 1 <= values["dme"] <= 100):
                raise ValueError("Invalid marshal radial or distance")
            continue
        if name == "tacan":
            channel = re.fullmatch(r"(.*?)\s*([xy])", raw)
            if channel is None:
                raise ValueError("TACAN must include X or Y")
            number = _number(channel.group(1))
            if not 1 <= number <= 126:
                raise ValueError("Invalid TACAN channel")
            values[name] = f"{number}{channel.group(2).upper()}"
            continue
        if name == "eat":
            digits = _eat_digits(raw.replace(":", " ").split())
            if not digits.isascii() or not digits.isdigit() or not 1 <= len(digits) <= 4:
                raise ValueError("Invalid Push / EAT")
            values[name] = digits
            continue
        number = _number(raw)
        limits = {"radial": (0, 359), "fb": (0, 359), "dme": (1, 100),
                  "angels": (1, 30), "button": (1, 30), "icls": (1, 20)}
        low, high = limits[name]
        if not low <= number <= high:
            raise ValueError(f"Invalid {name.upper()}")
        values[name] = number
    return values


def _has_prefix(text: str, prefixes: set[str]) -> bool:
    return any(text == prefix or text.startswith(prefix + " ") for prefix in prefixes)


def parse_command(text: str, active_view: str = "notes") -> Command:
    cleaned = normalize_command(text)
    # Bare plural is navigation; every note with a body keeps legacy parsing.
    if cleaned == "notes":
        return Command("view", "notes")
    if is_clear_notes_command(text):
        return Command("clear_notes")
    note = parse_voice_note(text)
    if note is not None:
        return Command("note", note)
    if cleaned in {"night mode", "nighttime"}:
        return Command("theme", "night")
    if cleaned in {"day mode", "daytime"}:
        return Command("theme", "day")
    if cleaned in {"show notes", "back to notes"}:
        return Command("view", "notes")
    if cleaned in {"this three", "this 3"}:
        return Command("view", "case3")
    cleaned = re.sub(r"\bcase (?:three|tree|free|iii|3)\b", "case3", cleaned)
    if cleaned in {"case3", "show case3", "case3 status"}:
        return Command("view", "case3")
    if cleaned in {"reset case3", "clear case3", "clear case", "reset this three", "reset this 3",
                   "clear this three", "clear this 3"}:
        return Command("reset_case3")
    if cleaned in {"commencing", "commence", "commence now"}:
        return Command("commence")
    if cleaned in {"crossing", "crossing now"}:
        return Command("crossing")
    if cleaned.startswith("sync clock "):
        return Command("clock_sync", _eat_digits(cleaned[11:].replace(":", " ").split()))
    # Keep existing explicit commands available in either view. Once the full
    # phrase matches, STT suffixes cannot be interpreted as a crossing time.
    if _has_prefix(cleaned, {"marshal crossing now", "crossing marshal now", "marshal now",
                            "marshall crossing now", "crossing marshall now", "marshall now"}):
        return Command("crossing")
    # Only CASE III enables abbreviated cockpit commands. A lone marshal is
    # exact, so arbitrary sentences beginning with that noun are not commands.
    if active_view == "case3" and (
        cleaned in {"marshal", "marshall", "crossing", "crossing now"} or
        _has_prefix(cleaned, {"marshal cross", "marshall cross", "marshal crossing",
                              "marshall crossing", "crossing marshal", "crossing marshall"})
    ):
        return Command("crossing")
    if cleaned == "eat":
        return Command("eat", "")
    if cleaned == "marshal" and active_view != "case3":
        return Command("coordinate", text)
    if cleaned.startswith("marshal ") and not re.match(
        r"marshal (?:radial|dme|\d|zero|one|two|three|four|five|six|seven|eight|nine|niner)", cleaned
    ):
        return Command("coordinate", text)
    try:
        assignment = parse_assignment(cleaned)
    except ValueError as exc:
        return Command("invalid_case3", str(exc))
    if assignment:
        if set(assignment) == {"eat"}:
            return Command("eat", str(assignment["eat"]))
        return Command("assignment", data=assignment)
    return Command("coordinate", text)


def apply_case3_command(command: Command, state: KneeboardState,
                        now: datetime | None = None) -> bool:
    if command.kind == "view":
        state.set_view(command.value)
    elif command.kind == "theme":
        state.set_theme(command.value)
    elif command.kind == "eat":
        state.case3.set_eat(command.value, now)
    elif command.kind == "crossing":
        state.case3.set_crossing(now)
        state.set_view("case3")
    elif command.kind == "assignment":
        state.case3.set_assignment(command.data or {}, now)
        state.set_view("case3")
    elif command.kind == "commence":
        state.case3.commence(now)
        state.set_view("case3")
    elif command.kind == "clock_sync":
        state.case3.sync_pc_time(command.value)
    elif command.kind == "reset_case3":
        state.reset_case3()
    elif command.kind == "invalid_case3":
        raise ValueError(command.value)
    else:
        return False
    return True
