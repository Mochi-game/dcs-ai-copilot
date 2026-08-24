from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


class CoordinateParseError(ValueError):
    """Raised when a spoken or typed coordinate message cannot be parsed."""


_COORDINATE_RE = re.compile(
    r"""
    \b(?P<kind>target|waypoint|tanker|bullseye)\b
    .*?
    \b(?P<lat_hemi>north|south|n|s)\b
    \s+(?P<lat_deg>\d{1,2})
    \s+(?P<lat_min>\d{1,2}(?:\.\d+)?)
    .*?
    \b(?P<lon_hemi>east|west|e|w)\b
    \s+(?P<lon_deg>\d{1,3})
    \s+(?P<lon_min>\d{1,2}(?:\.\d+)?)
    .*?
    \b(?:elevation|elev|altitude|alt)\b
    \s*:?\s*(?P<elevation>-?\d+)
    """,
    re.IGNORECASE | re.VERBOSE,
)

_FLEX_COORDINATE_RE = re.compile(
    r"""
    (?:(?P<kind>target|waypoint|tanker|bullseye)\b.*?)?
    \b(?P<lat_hemi>north|northern|south|southern|norf|morf|morph|n|s)\b
    (?:\s+\b(?:north|northern|south|southern|norf|morf|morph|n|s)\b)?
    \s+(?P<lat_coord>\d+(?:\.\d+)?(?:\s+(?:\d+(?:\.\d+)?|\.\d+))?)
    .*?
    \b(?P<lon_hemi>east|eastern|west|western|e|w)\b
    \s+(?P<lon_coord>\d+(?:\.\d+)?(?:\s+(?:\d+(?:\.\d+)?|\.\d+))?)
    .*?
    \b(?:elevation|elev|altitude|alt)\b
    \s*:?\s*(?P<elevation>-?\d+)
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class CapturedCoordinate:
    kind: str
    index: int
    lat_hemisphere: str
    lat_degrees: int
    lat_minutes: Decimal
    lon_hemisphere: str
    lon_degrees: int
    lon_minutes: Decimal
    elevation_ft: int

    def format_latitude(self) -> str:
        return f"{self.lat_hemisphere}{self.lat_degrees:02d}°{_format_minutes(self.lat_minutes)}'"

    def format_longitude(self) -> str:
        return f"{self.lon_hemisphere}{self.lon_degrees:03d}°{_format_minutes(self.lon_minutes)}'"

    def format_elevation(self) -> str:
        return f"ELEV {self.elevation_ft} FT"


def parse_coordinate_message(text: str, index: int = 1) -> CapturedCoordinate:
    cleaned_text = _normalize_transcript_text(text)
    match = _COORDINATE_RE.search(cleaned_text)
    if match:
        return _capture_from_strict_match(match, index)

    match = _FLEX_COORDINATE_RE.search(cleaned_text)
    if not match:
        if re.search(r"\b(?:elevation|elev|altitude|alt)\b", cleaned_text, re.IGNORECASE):
            raise CoordinateParseError("elevation number is missing")
        raise CoordinateParseError(
            "expected text like: target north 42 15.732 east 041 38.219 elevation 428"
        )

    lat_degrees, lat_minutes = _parse_coordinate_parts(match.group("lat_coord"), degree_digits=2)
    lon_degrees, lon_minutes = _parse_coordinate_parts(match.group("lon_coord"), degree_digits=3)
    capture = CapturedCoordinate(
        kind=(match.group("kind") or "target").lower(),
        index=index,
        lat_hemisphere=_normalize_hemisphere(match.group("lat_hemi")),
        lat_degrees=lat_degrees,
        lat_minutes=lat_minutes,
        lon_hemisphere=_normalize_hemisphere(match.group("lon_hemi")),
        lon_degrees=lon_degrees,
        lon_minutes=lon_minutes,
        elevation_ft=int(match.group("elevation")),
    )
    _validate_capture(capture)
    return capture


def _capture_from_strict_match(match: re.Match[str], index: int) -> CapturedCoordinate:
    try:
        lat_minutes = Decimal(match.group("lat_min"))
        lon_minutes = Decimal(match.group("lon_min"))
    except InvalidOperation as exc:
        raise CoordinateParseError("minutes must be numeric") from exc

    capture = CapturedCoordinate(
        kind=match.group("kind").lower(),
        index=index,
        lat_hemisphere=_normalize_hemisphere(match.group("lat_hemi")),
        lat_degrees=int(match.group("lat_deg")),
        lat_minutes=lat_minutes,
        lon_hemisphere=_normalize_hemisphere(match.group("lon_hemi")),
        lon_degrees=int(match.group("lon_deg")),
        lon_minutes=lon_minutes,
        elevation_ft=int(match.group("elevation")),
    )
    _validate_capture(capture)
    return capture


def _normalize_transcript_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(
        r"(?<=\d)\s*\.\s*decimal\s*",
        ".",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?<=\d)\s+decimal\s+",
        ".",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\bdecimal\s+(?P<fraction>\d+)\b",
        r".\g<fraction>",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\bdecimal(?P<fraction>\d+)\b",
        r".\g<fraction>",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?P<deg>\d{2,3})(?P<min>\d{2}),\s*(?P<fraction>\d{3,5})\b",
        r"\g<deg>\g<min>.\g<fraction>",
        cleaned,
    )
    cleaned = re.sub(
        r"\b(?P<deg>\d{2,3}),\s*(?P<minutes>\d{4,5})\b",
        r"\g<deg>.\g<minutes>",
        cleaned,
    )
    return re.sub(r"[,.](?=\s|$)", " ", cleaned)


def _parse_coordinate_parts(raw_value: str, degree_digits: int) -> tuple[int, Decimal]:
    parts = raw_value.split()
    if len(parts) == 2:
        whole = parts[0]
        minutes = parts[1]
        if minutes.startswith(".") and len(whole) > degree_digits:
            degrees = int(whole[:degree_digits])
            minutes = f"{whole[degree_digits:]}{minutes}"
        elif minutes.startswith(".") and len(minutes) >= 5:
            degrees = int(whole)
            minutes = f"{minutes[1:3]}.{minutes[3:]}"
        else:
            degrees = int(whole)
        if "." not in minutes and len(minutes) >= 4:
            minutes = f"{minutes[:2]}.{minutes[2:]}"
        return degrees, Decimal(minutes)

    value = parts[0]
    if "." not in value:
        if len(value) <= degree_digits:
            raise CoordinateParseError("coordinate minutes are missing")
        return int(value[:degree_digits]), Decimal(value[degree_digits:])

    whole, fraction = value.split(".", 1)
    if len(whole) > degree_digits:
        degrees = int(whole[:degree_digits])
        minutes = Decimal(f"{whole[degree_digits:]}.{fraction}")
        return degrees, minutes

    if len(whole) == degree_digits and len(fraction) >= 4:
        degrees = int(whole)
        minutes = Decimal(f"{fraction[:2]}.{fraction[2:]}")
        return degrees, minutes

    raise CoordinateParseError("coordinate minutes are missing")


def _normalize_hemisphere(raw_value: str) -> str:
    value = raw_value.lower()
    if value in {"north", "northern", "norf", "morf", "morph", "n"}:
        return "N"
    if value in {"south", "southern", "s"}:
        return "S"
    if value in {"east", "eastern", "e"}:
        return "E"
    if value in {"west", "western", "w"}:
        return "W"
    raise CoordinateParseError(f"unknown hemisphere: {raw_value}")


def _validate_capture(capture: CapturedCoordinate) -> None:
    if not 0 <= capture.lat_degrees <= 90:
        raise CoordinateParseError("latitude degrees must be between 0 and 90")
    if not 0 <= capture.lon_degrees <= 180:
        raise CoordinateParseError("longitude degrees must be between 0 and 180")
    if not Decimal("0") <= capture.lat_minutes < Decimal("60"):
        raise CoordinateParseError("latitude minutes must be between 0 and 59.999")
    if not Decimal("0") <= capture.lon_minutes < Decimal("60"):
        raise CoordinateParseError("longitude minutes must be between 0 and 59.999")


def _format_minutes(minutes: Decimal) -> str:
    return f"{minutes.quantize(Decimal('0.001')):06.3f}"
