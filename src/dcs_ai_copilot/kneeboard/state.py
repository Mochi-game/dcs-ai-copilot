from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

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
        self._captures: list[CapturedCoordinate] = []
        self._notes: list[VoiceNote] = []
        self._revision = 0
        self._app: dict[str, object] = {
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
