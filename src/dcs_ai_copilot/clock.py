"""The clock CASE III times against: DCS mission time when DCS-BIOS sends it.

DCS-BIOS CommonData exports LoGetMissionStartTime() (seconds after midnight)
and LoGetModelTime() (simulated seconds, in hundredths). Their sum is the time
shown on the cockpit clock. It stops while DCS is paused, which is what a
push time flown in the sim needs. There is deliberately no extrapolation
between packets: DCS-BIOS updates many times per second, and extrapolating
would keep the clock running during a pause.

Without mission data the local PC clock is used. Every reading carries a key
naming its time base, so times recorded against one base are never compared
with another, including a restarted mission whose model time began again.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Callable

STALE_AFTER_SECONDS = 5.0
# A drop smaller than this is treated as a torn high/low word, not a restart.
RESTART_DROP_SECONDS = 2.0


@dataclass(frozen=True)
class ClockReading:
    time: datetime
    source: str  # "MISSION" or "PC"
    key: tuple
    live: bool = True


class MissionClock:
    def __init__(self, monotonic: Callable[[], float] = time.monotonic,
                 wall: Callable[[], datetime] = datetime.now) -> None:
        self._lock = RLock()
        self._monotonic = monotonic
        self._wall = wall
        self._start_seconds: int | None = None
        self._model_hundredths = 0
        self._received_at = 0.0
        self._epoch = 0
        self._base: datetime | None = None
        self._pending_drop: tuple[int, int] | None = None

    def update(self, start_seconds: int, model_hundredths: int) -> None:
        with self._lock:
            restarted = self._start_seconds is None or start_seconds != self._start_seconds
            if not restarted and model_hundredths < self._model_hundredths - RESTART_DROP_SECONDS * 100:
                # A new mission restarts model time. Require the drop twice in a
                # row so one torn packet cannot throw away a running session.
                if self._pending_drop is None:
                    self._pending_drop = (start_seconds, model_hundredths)
                    return
                restarted = True
            self._pending_drop = None
            if restarted:
                self._epoch += 1
                today = self._wall()
                self._base = today.replace(hour=0, minute=0, second=0, microsecond=0)
            self._start_seconds = start_seconds
            self._model_hundredths = model_hundredths
            self._received_at = self._monotonic()

    def reading(self) -> ClockReading:
        with self._lock:
            if self._start_seconds is None or self._base is None:
                return ClockReading(self._wall().replace(microsecond=0), "PC", ("PC",))
            mission = self._base + timedelta(seconds=self._start_seconds,
                                             milliseconds=self._model_hundredths * 10)
            live = self._monotonic() - self._received_at <= STALE_AFTER_SECONDS
            return ClockReading(mission.replace(microsecond=0), "MISSION",
                                ("MISSION", self._epoch), live)


def pc_clock() -> ClockReading:
    return ClockReading(datetime.now().replace(microsecond=0), "PC", ("PC",))
