from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from dcs_ai_copilot.case3 import Case3State
from dcs_ai_copilot.clock import MissionClock

from dcs_ai_copilot.voice.parser import CapturedCoordinate


VISIBLE_NOTE_LIMIT = 6


@dataclass(frozen=True)
class VoiceNote:
    index: int
    text: str


@dataclass(frozen=True)
class KneeboardSnapshot:
    revision: int
    captures: list[CapturedCoordinate]
    notes: list[VoiceNote]
    app: dict[str, object]
    dcs_bios: dict[str, object]
    voice: dict[str, object]


class KneeboardState:
    def __init__(self) -> None:
        self._lock = RLock()
        self.mission_clock = MissionClock()
        self.case3 = Case3State(self.mission_clock.reading)
        self._captures: list[CapturedCoordinate] = []
        self._notes: list[VoiceNote] = []
        self._revision = 0
        self._app: dict[str, object] = {
            "active_view": "notes",
            "theme": "night",
            "buy_me_a_coffee_url": "",
        }
        self._dcs_bios: dict[str, object] = {
            "status": "STARTING",
            "installed": False,
            "install_path": "",
            "reference_loaded": False,
            "reference_dir": "",
            "listening": False,
            "last_packet_time": 0.0,
            "aircraft": "",
            "is_fa18c": False,
            "values": {},
            "missing_controls": [],
        }
        self._voice: dict[str, object] = {
            "enabled": False,
            "status": "DISABLED",
            "is_recording": False,
            "last_transcript": "",
            "last_error": "",
            "ptt_key": "",
            "ptt_mode": "",
            "ptt_source": "",
            "joystick_backend": "",
            "joystick_name": "",
            "joystick_button": "",
            "joystick_status": "",
            "joystick_detail": "",
            "model": "",
        }

    def next_index(self) -> int:
        with self._lock:
            return len(self._captures) + 1

    def set_view(self, view: str) -> KneeboardSnapshot:
        if view not in {"notes", "case3"}:
            raise ValueError("view must be notes or case3")
        return self.update_app(active_view=view)

    def reset_case3(self) -> KneeboardSnapshot:
        with self._lock:
            self.case3.reset()
            self._app["active_view"] = "case3"
            self._revision += 1
            return self.snapshot()

    def set_theme(self, theme: str) -> KneeboardSnapshot:
        if theme not in {"night", "day"}:
            raise ValueError("theme must be night or day")
        return self.update_app(theme=theme)

    def next_note_index(self) -> int:
        with self._lock:
            return len(self._notes) + 1

    def add_capture(self, capture: CapturedCoordinate) -> KneeboardSnapshot:
        with self._lock:
            self._captures.append(capture)
            self._revision += 1
            return self.snapshot()

    def add_note(self, text: str) -> KneeboardSnapshot:
        with self._lock:
            self._notes.append(VoiceNote(index=len(self._notes) + 1, text=text))
            self._revision += 1
            return self.snapshot()

    def clear_notes(self) -> KneeboardSnapshot:
        with self._lock:
            if self._notes:
                self._notes.clear()
                self._revision += 1
            return self.snapshot()

    def snapshot(self) -> KneeboardSnapshot:
        with self._lock:
            return KneeboardSnapshot(
                revision=self._revision,
                captures=list(self._captures),
                notes=list(self._notes),
                app=dict(self._app),
                dcs_bios=dict(self._dcs_bios),
                voice=dict(self._voice),
            )

    def update_app(self, **updates: object) -> KneeboardSnapshot:
        with self._lock:
            changed = any(self._app.get(key) != value for key, value in updates.items())
            self._app.update(updates)
            if changed:
                self._revision += 1
            return self.snapshot()

    def update_dcs_bios(self, **updates: object) -> KneeboardSnapshot:
        with self._lock:
            changed = any(self._dcs_bios.get(key) != value for key, value in updates.items())
            self._dcs_bios.update(updates)
            if changed:
                self._revision += 1
            return self.snapshot()

    def update_voice(self, **updates: object) -> KneeboardSnapshot:
        with self._lock:
            changed = any(self._voice.get(key) != value for key, value in updates.items())
            self._voice.update(updates)
            if changed:
                self._revision += 1
            return self.snapshot()

    def as_json_data(self) -> dict[str, object]:
        snapshot = self.snapshot()
        return {
            "active_view": snapshot.app["active_view"],
            "theme": snapshot.app["theme"],
            "case3": self.case3.as_json_data(),
            "revision": snapshot.revision,
            "captures": [
                {
                    "kind": capture.kind,
                    "index": capture.index,
                    "title": f"{capture.kind.upper()} {capture.index}",
                    "latitude": capture.format_latitude(),
                    "longitude": capture.format_longitude(),
                    "elevation": capture.format_elevation(),
                }
                for capture in snapshot.captures
            ],
            "notes": [
                {
                    "index": note.index,
                    "title": f"NOTE {note.index}",
                    "text": note.text,
                }
                for note in snapshot.notes[-VISIBLE_NOTE_LIMIT:]
            ],
            "note_history_count": max(0, len(snapshot.notes) - VISIBLE_NOTE_LIMIT),
            "note_total_count": len(snapshot.notes),
            "app": snapshot.app,
            "dcs_bios": snapshot.dcs_bios,
            "voice": snapshot.voice,
        }
