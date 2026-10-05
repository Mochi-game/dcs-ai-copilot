"""Manual CASE III timing against the DCS mission clock, or the PC clock
when DCS-BIOS sends no mission time (see clock.py).

The plan is anchored to crossing, not continuously re-created from now.
EARLY/ON TIME/LATE compare now with EAT at whole-second precision.
They do not describe aircraft position or flight-path conformance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Callable

from dcs_ai_copilot.clock import ClockReading, pc_clock

STANDARD_HOLD = timedelta(minutes=6)
TURN_SECONDS = 120
MINIMUM_HOLD_SECONDS = 2 * TURN_SECONDS
HOLD_SPEED_KT = 250
TURN_INBOUND_WARNING_SECONDS = 15


@dataclass(frozen=True)
class HoldPhase:
    name: str
    hold_index: int
    adjusted: bool
    start: datetime
    end: datetime

    @property
    def duration_seconds(self) -> int:
        return (self.end - self.start) // timedelta(seconds=1)


@dataclass(frozen=True)
class HoldPlan:
    time_to_eat: timedelta
    full_holds: int
    remaining_time: timedelta
    final_hold_adjustment: timedelta
    phases: tuple[HoldPhase, ...] = ()

    @property
    def feasible(self) -> bool:
        return bool(self.phases)

    @property
    def final_outbound_seconds(self) -> int | None:
        if not self.remaining_time:
            return None
        return (self.remaining_time // timedelta(seconds=1) - MINIMUM_HOLD_SECONDS) // 2

    @property
    def final_inbound_seconds(self) -> int | None:
        outbound = self.final_outbound_seconds
        if outbound is None:
            return None
        return self.remaining_time // timedelta(seconds=1) - MINIMUM_HOLD_SECONDS - outbound


def calculate_hold_plan(crossing: datetime, eat: datetime,
                        hold: timedelta = STANDARD_HOLD) -> HoldPlan:
    if hold != STANDARD_HOLD:
        raise ValueError("This model requires a 6-minute standard hold")
    duration = eat - crossing
    if duration % timedelta(seconds=1):
        raise ValueError("Hold duration must be a whole number of seconds")
    seconds = duration // timedelta(seconds=1)
    if seconds < MINIMUM_HOLD_SECONDS:
        return HoldPlan(duration, 0, timedelta(0), timedelta(0))
    full, final = divmod(seconds, 360)
    if final >= MINIMUM_HOLD_SECONDS:
        durations = [360] * full + [final]
    elif final == 0:
        durations = [360] * full
    elif final < 120:
        durations = [360] * (full - 1) + [360 + final]
    else:
        # The procedure's 14-minute example is 7+7, not 6+8. Compare
        # feasible lap counts and use the one closest to standard 6:00.
        choices = []
        for count in (full, full + 1):
            if count and seconds >= count * MINIMUM_HOLD_SECONDS:
                base, extra = divmod(seconds, count)
                lengths = [base + (1 if i < extra else 0) for i in range(count)]
                choices.append((max(abs(length - 360) for length in lengths), count, lengths))
        durations = min(choices)[2]
    full = sum(length == 360 for length in durations)
    final = durations[-1] if durations and durations[-1] != 360 else 0
    # Crossing begins TURN 1. Every hold ends at Marshal after INBOUND.
    phases = []
    cursor = crossing
    for index, hold_seconds in enumerate(durations, start=1):
        straight = hold_seconds - MINIMUM_HOLD_SECONDS
        outbound = straight // 2
        for name, length in (("TURN 1", TURN_SECONDS), ("OUTBOUND", outbound),
                             ("TURN 2", TURN_SECONDS), ("INBOUND", straight - outbound)):
            end = cursor + timedelta(seconds=length)
            phases.append(HoldPhase(name, index, hold_seconds != 360, cursor, end))
            cursor = end
    return HoldPlan(duration, full, timedelta(seconds=final),
                    timedelta(seconds=final - 360 if final else 0), tuple(phases))


def phase_at(plan: HoldPlan | None, now: datetime) -> dict[str, object]:
    """Read an absolute timeline; zero-length legs are skipped, never timed."""
    empty = {"current_phase": None, "current_hold": None, "current_hold_adjusted": None,
             "next_event": None, "next_event_time": None, "time_to_next_seconds": None}
    if not plan or not plan.feasible:
        return empty
    if now >= plan.phases[-1].end:
        return {**empty, "next_event": "COMMENCE", "time_to_next_seconds": 0}
    if now < plan.phases[0].start:
        return {**empty, "next_event": "LEFT 180°", "next_event_time": plan.phases[0].start.isoformat(),
                "time_to_next_seconds": (plan.phases[0].start - now) // timedelta(seconds=1)}
    for index, phase in enumerate(plan.phases):
        if phase.start <= now < phase.end:
            following = next((item for item in plan.phases[index + 1:] if item.duration_seconds), None)
            event = ("LEFT 180°" if following.name.startswith("TURN") else following.name) if following else "COMMENCE"
            return {"current_phase": phase.name, "current_hold": phase.hold_index,
                    "current_hold_adjusted": phase.adjusted, "next_event": event,
                    "next_event_time": phase.end.isoformat(),
                    "time_to_next_seconds": (phase.end - now) // timedelta(seconds=1)}
    return empty


def resolve_eat(digits: str, now: datetime) -> datetime:
    """M or MM (1–60) means next occurrence this/next hour; HMM/HHMM this/next day.

    Minute 60 is the top of the hour, the same as 00.
    """
    if not digits.isascii() or not digits.isdigit() or not 1 <= len(digits) <= 4:
        raise ValueError("EAT must be a minute 1–60 or HHMM, for example 5, 32 or 1432")
    minute = int(digits[-2:])
    hour = int(digits[:-2]) if len(digits) > 2 else now.hour
    if len(digits) <= 2 and minute == 60:
        minute = 0
    if minute > 59 or hour > 23:
        raise ValueError("EAT hour must be 00–23 and minute 00–59")
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate < now.replace(microsecond=0):
        candidate += timedelta(days=1) if len(digits) == 4 else timedelta(hours=1)
    return candidate


def hold_lengths(plan: HoldPlan | None) -> list[int]:
    """Seconds per lap, in flying order. A 4:00 lap still has its zero legs."""
    lengths: dict[int, int] = {}
    for phase in plan.phases if plan else ():
        lengths[phase.hold_index] = lengths.get(phase.hold_index, 0) + phase.duration_seconds
    return [lengths[index] for index in sorted(lengths)]


def _clock_text(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _lap_kind(seconds: int) -> str:
    return "STANDARD" if seconds == 360 else "EXTENDED" if seconds > 360 else "SHORT LEGS"


def _laps_text(lengths: list[int]) -> str:
    plural = "S" if len(lengths) != 1 else ""
    return f"{len(lengths)} LAP{plural} · " + " + ".join(_clock_text(length) for length in lengths)


_COUNT_WORDS = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE"}


def lap_gauge(plan: HoldPlan | None, current_hold: int | None) -> dict[str, object]:
    """What is left after the lap being flown: the pilot's one-more-lap gauge."""
    lengths = hold_lengths(plan) if plan and plan.feasible else []
    if not lengths or current_hold is None:
        return {"hold_lengths_seconds": lengths, "total_holds": len(lengths) or None,
                "holds_after_current": None, "next_hold_seconds": None,
                "next_hold_kind": None, "lap_advice": None}
    after = len(lengths) - current_hold
    if after <= 0:
        return {"hold_lengths_seconds": lengths, "total_holds": len(lengths),
                "holds_after_current": 0, "next_hold_seconds": None, "next_hold_kind": None,
                "lap_advice": "LAST LAP · COMMENCE AT MARSHAL"}
    following = lengths[current_hold]
    kind = _lap_kind(following)
    plural = "S" if after > 1 else ""
    advice = f"{_COUNT_WORDS.get(after, str(after))} MORE LAP{plural} · NEXT {_clock_text(following)}"
    if kind != "STANDARD":
        advice += f" {kind}"
    return {"hold_lengths_seconds": lengths, "total_holds": len(lengths),
            "holds_after_current": after, "next_hold_seconds": following,
            "next_hold_kind": kind, "lap_advice": advice}


def phase_cue(timing: dict[str, object], gauge: dict[str, object]) -> dict[str, object]:
    """The large instruction: above all, when to turn back inbound."""
    phase = timing.get("current_phase")
    seconds = timing.get("time_to_next_seconds")
    if phase == "TURN 1":
        cue = "OUTBOUND TURN"
    elif phase == "OUTBOUND":
        cue = "TURN INBOUND IN"
    elif phase == "TURN 2":
        cue = "INBOUND TURN"
    elif phase == "INBOUND":
        cue = "COMMENCE IN" if gauge.get("holds_after_current") == 0 else "NEXT LAP IN"
    else:
        cue = None
    urgent = (phase == "OUTBOUND" and seconds is not None
              and seconds <= TURN_INBOUND_WARNING_SECONDS)
    return {"cue": cue, "cue_seconds": seconds if cue else None, "cue_urgent": urgent}


class Case3State:
    def __init__(self, clock: Callable[[], ClockReading] = pc_clock) -> None:
        self._lock = RLock()
        self._clock = clock
        self._eat: datetime | None = None
        self._crossing: datetime | None = None
        self._commenced_at: datetime | None = None
        self._assignment: dict[str, object] = {}
        self._phase = "HOLD"
        self._manual_offset: timedelta | None = None
        self._manual_epoch = 0
        # Time base both stored times belong to. None when a caller supplied
        # the time explicitly (tests), which is then trusted as-is.
        self._key: tuple | None = None

    def _now(self, now: datetime | None) -> tuple[datetime, tuple | None]:
        if now is not None:
            return now.replace(microsecond=0), None
        reading = self._reading()
        return reading.time, reading.key

    def _reading(self) -> ClockReading:
        reading = self._clock()
        if reading.source == "PC" and self._manual_offset is not None:
            return ClockReading(reading.time + self._manual_offset, "MANUAL",
                                ("MANUAL", self._manual_epoch), reading.live)
        return reading

    def sync_pc_time(self, hhmm: str) -> None:
        if len(hhmm) != 4 or not hhmm.isascii() or not hhmm.isdigit():
            raise ValueError("Clock sync needs HHMM")
        hour, minute = int(hhmm[:2]), int(hhmm[2:])
        if hour > 23 or minute > 59:
            raise ValueError("Invalid clock time")
        reading = self._clock()
        if reading.source != "PC":
            raise ValueError("DCS mission clock is active; manual sync is unnecessary")
        target = reading.time.replace(hour=hour, minute=minute, second=0, microsecond=0)
        with self._lock:
            self._manual_offset = target - reading.time
            self._manual_epoch += 1
            self._eat = self._crossing = self._commenced_at = None
            self._phase = "HOLD"
            self._key = ("MANUAL", self._manual_epoch)

    def _adopt_key(self, key: tuple | None) -> None:
        # A time on another base (PC vs mission, or a restarted mission)
        # cannot be subtracted from the one already stored.
        if key is not None and self._key is not None and key != self._key:
            self._eat = self._crossing = None
            self._commenced_at = None
            self._phase = "HOLD"
        if key is not None and key[0] == "MISSION":
            self._manual_offset = None
        if key is not None:
            self._key = key

    def set_eat(self, digits: str, now: datetime | None = None) -> None:
        current, key = self._now(now)
        eat = resolve_eat(digits, current)
        with self._lock:
            self._adopt_key(key)
            self._eat = eat
            self._commenced_at = None
            self._phase = "HOLD"

    def set_crossing(self, now: datetime | None = None) -> None:
        current, key = self._now(now)
        with self._lock:
            self._adopt_key(key)
            if self._phase == "HOLD":
                self._crossing = current

    def set_assignment(self, values: dict[str, object], now: datetime | None = None) -> None:
        current, key = self._now(now)
        eat = resolve_eat(str(values["eat"]), current) if "eat" in values else None
        with self._lock:
            self._adopt_key(key)
            self._assignment.update({field: value for field, value in values.items() if field != "eat"})
            if eat is not None:
                self._eat = eat
                self._crossing = None
                self._commenced_at = None
                self._phase = "HOLD"

    def commence(self, now: datetime | None = None) -> None:
        current, key = self._now(now)
        with self._lock:
            self._adopt_key(key)
            self._commenced_at = current
            self._phase = "COMMENCE"

    def reset(self) -> None:
        with self._lock:
            self._eat = self._crossing = None
            self._commenced_at = None
            self._assignment.clear()
            self._phase = "HOLD"
            self._manual_offset = None
            self._key = None

    def as_json_data(self, now: datetime | None = None) -> dict[str, object]:
        reading = self._reading() if now is None else None
        now = reading.time if reading else now.replace(microsecond=0)
        with self._lock:
            if reading and self._key is not None and reading.key != self._key:
                self._eat = self._crossing = None
                self._commenced_at = None
                self._phase = "HOLD"
                self._key = None
                if reading.source == "MISSION":
                    self._manual_offset = None
            eat, crossing = self._eat, self._crossing
            assignment = dict(self._assignment)
            phase = self._phase
            commenced_at = self._commenced_at
        seconds = (eat - now) // timedelta(seconds=1) if eat else None
        plan = calculate_hold_plan(crossing, eat) if crossing and eat and phase == "HOLD" else None
        status = "READY" if seconds is None else (
            "EARLY" if seconds > 0 else "LATE" if seconds < 0 else "ON TIME")
        lengths = hold_lengths(plan)
        adjustment = lengths[-1] - 360 if lengths else None
        if plan is None:
            recommendation = "SET EAT AND MARSHAL CROSS"
        elif not plan.feasible:
            recommendation = "INSUFFICIENT TIME FOR FULL HOLD · VERIFY / PREPARE TO COMMENCE"
        elif adjustment:
            direction = "MORE" if adjustment > 0 else "LESS"
            recommendation = f"HOLD LEGS ADJUSTED · {abs(adjustment)} SEC {direction} THAN 6:00"
        else:
            recommendation = "NO FINAL HOLD ADJUSTMENT"
        timing = phase_at(plan, now)
        if seconds is not None and seconds <= 0:
            timing.update(current_phase=None, current_hold=None, current_hold_adjusted=None,
                          next_event="COMMENCE", next_event_time=None, time_to_next_seconds=0)
        gauge = lap_gauge(plan, timing["current_hold"])
        preview = None
        if eat and not crossing and seconds is not None and seconds > 0:
            if_now = calculate_hold_plan(now, eat)
            preview = ("IF CROSSING NOW: " + _laps_text(hold_lengths(if_now)) if if_now.feasible
                       else "IF CROSSING NOW: UNDER 4:00 · NO LAP")
        timeline = [{"phase": phase.name, "hold_index": phase.hold_index, "adjusted": phase.adjusted,
                     "start": phase.start.isoformat(), "end": phase.end.isoformat(),
                     "duration_seconds": phase.duration_seconds} for phase in plan.phases] if plan else []
        fb = f"{assignment['fb']:03d}" if "fb" in assignment else "ASSIGNED FB"
        radial = f"R{assignment['radial']:03d}" if "radial" in assignment else "MARSHAL RADIAL"
        button = str(assignment["button"]) if "button" in assignment else "ASSIGNED BUTTON"
        guidance = [
            f"COMMENCE · 250 KIAS · ~4000 FPM · STAY ON {radial} TO ~20 DME",
            f"PLATFORM · 5000 FT, THEN ~2000 FPM · SWITCH BUTTON {button}",
            f"20 DME · CORRECT TOWARD {fb}, SET CRS, INTERCEPT · LEVEL 1200 FT",
            "FINAL · ~8 DME GEAR/FLAPS, TRIM ON SPEED · 1200 FT TO GLIDESLOPE",
            "BALL · ~3/4 NM, TRANSITION TO THE BALL",
        ]
        return {
            **timing,
            **gauge,
            **phase_cue(timing, gauge),
            "crossing_preview": preview,
            "eat": eat.isoformat() if eat else None,
            "marshal_crossing_time": crossing.isoformat() if crossing else None,
            "assignment": assignment,
            "phase": phase,
            "commenced_at": commenced_at.isoformat() if commenced_at else None,
            "approach_guidance": guidance if phase != "HOLD" else [],
            "inbound_course": (assignment["radial"] + 180) % 360 if "radial" in assignment else None,
            "current_time": now.isoformat(),
            "clock_source": reading.source if reading else "SUPPLIED",
            "clock_live": reading.live if reading else True,
            "commence_dme": assignment.get("dme"),
            "marshal_altitude_ft": assignment.get("angels", 0) * 1000 if "angels" in assignment else None,
            "hold_speed_kt": HOLD_SPEED_KT,
            "standard_hold_seconds": int(STANDARD_HOLD.total_seconds()),
            "time_to_commence_seconds": max(0, seconds) if seconds is not None else None,
            "crossing_to_eat_seconds": plan.time_to_eat // timedelta(seconds=1) if plan else None,
            "full_holds": plan.full_holds if plan and plan.feasible else None,
            "remaining_time_seconds": plan.remaining_time // timedelta(seconds=1) if plan and plan.feasible else None,
            "final_outbound_seconds": plan.final_outbound_seconds if plan else None,
            "final_inbound_seconds": plan.final_inbound_seconds if plan else None,
            "turn_seconds": TURN_SECONDS,
            "timeline": timeline,
            "plan_status": "COMMENCED" if phase != "HOLD" else "READY" if plan is None else "PLANNED" if plan.feasible else "INSUFFICIENT HOLD TIME",
            "final_hold_adjustment_seconds": adjustment,
            "recommendation": recommendation,
            "status": status,
            "status_text": f"{status}. {recommendation}",
        }
