from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import patch

from test_voice_ptt import FakeRecorder, SequenceTranscriber, _build_service
from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.voice.router import parse_command


def wait_until(predicate):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("Condition did not become true")


class PausedTranscriber(SequenceTranscriber):
    def __init__(self, texts):
        super().__init__(texts)
        self.entered = threading.Event()
        self.release = threading.Event()

    def transcribe(self, clip):
        if self.calls == 0:
            self.entered.set()
            if not self.release.wait(3):
                raise RuntimeError("Test provider was not released")
        return super().transcribe(clip)


class VoiceReliabilityTests(unittest.TestCase):
    def build(self, texts, recorder=None, paused=False):
        state = KneeboardState()
        transcriber = PausedTranscriber(texts) if paused else SequenceTranscriber(texts)
        recorder = recorder or FakeRecorder()
        service = _build_service(state=state, recorder=recorder, transcriber=transcriber)
        service._render_snapshot = lambda snapshot: None
        self.addCleanup(service.stop)
        if paused:
            self.addCleanup(transcriber.release.set)
        return service, state, recorder, transcriber

    def speak(self, service):
        service.begin_recording("JOYSTICK")
        service.finish_recording("PTT RELEASED", source="JOYSTICK")

    def test_slow_note_clear_and_new_note_apply_in_spoken_order(self):
        service, state, recorder, provider = self.build(
            ["note old", "clear notes", "note new"], paused=True,
        )
        self.speak(service)
        self.assertTrue(provider.entered.wait(1))
        self.speak(service)
        self.speak(service)
        self.assertEqual(provider.calls, 0)
        self.assertEqual(state.snapshot().voice["pending_count"], 3)
        provider.release.set()
        wait_until(lambda: service._worker is None)
        self.assertEqual([note.text for note in state.snapshot().notes], ["new"])
        self.assertEqual(recorder.start_calls, 3)
        self.assertEqual(recorder.stop_calls, 3)
        self.assertEqual(state.snapshot().voice["pending_count"], 0)

    def test_old_result_does_not_clear_new_recording_indicator(self):
        service, state, recorder, provider = self.build(["note first", "note second"], paused=True)
        self.speak(service)
        self.assertTrue(provider.entered.wait(1))
        service.begin_recording("JOYSTICK")
        provider.release.set()
        wait_until(lambda: service._worker is None)
        self.assertEqual(len(state.snapshot().notes), 1)
        self.assertTrue(state.snapshot().voice["is_recording"])
        self.assertEqual(state.snapshot().voice["status"], "RECORDING")
        service.finish_recording("PTT RELEASED", source="JOYSTICK")
        wait_until(lambda: service._worker is None)
        self.assertEqual(recorder.stop_calls, 2)
        self.assertEqual(len(state.snapshot().notes), 2)

    def test_stop_discards_late_result_and_pending_audio(self):
        service, state, recorder, provider = self.build(["note late", "note queued"], paused=True)
        self.speak(service)
        self.assertTrue(provider.entered.wait(1))
        self.speak(service)
        service.stop()
        provider.release.set()
        wait_until(lambda: service._worker is None)
        self.assertEqual(state.snapshot().notes, [])
        self.assertEqual(state.snapshot().voice["status"], "STOPPED")
        self.assertEqual(provider.calls, 1)
        service.begin_recording("JOYSTICK")
        self.assertEqual(recorder.start_calls, 2)

    def test_router_exception_is_reported_and_next_recording_works(self):
        service, state, recorder, provider = self.build(["note broken", "note recovered"])
        with patch("dcs_ai_copilot.voice.ptt.parse_command", side_effect=RuntimeError("test router error")):
            self.speak(service)
            wait_until(lambda: service._worker is None)
        self.assertEqual(state.snapshot().voice["status"], "VOICE ERROR")
        self.assertIn("test router error", state.snapshot().voice["last_error"])
        self.speak(service)
        wait_until(lambda: service._worker is None)
        self.assertEqual([note.text for note in state.snapshot().notes], ["recovered"])
        self.assertEqual(recorder.stop_calls, 2)

    def test_timeout_requires_release_and_old_timeout_cannot_stop_new_clip(self):
        service, state, recorder, provider = self.build(["note first", "note second"])
        service.on_press("Key.f13")
        old_id = service._recording_id
        service._on_recording_timeout(old_id)
        service.on_press("Key.f13")
        self.assertEqual(recorder.start_calls, 1)
        service.on_release("Key.f13")
        service.on_press("Key.f13")
        service._on_recording_timeout(old_id)
        self.assertTrue(state.snapshot().voice["is_recording"])
        self.assertEqual(recorder.stop_calls, 1)
        service.on_release("Key.f13")
        wait_until(lambda: service._worker is None)
        self.assertEqual(recorder.stop_calls, 2)

    def test_keyboard_release_does_not_stop_joystick_recording(self):
        service, state, recorder, provider = self.build(["note joystick"])
        service.begin_recording("JOYSTICK")
        service.on_press("Key.f13")
        service.on_release("Key.f13")
        self.assertEqual(recorder.stop_calls, 0)
        self.assertTrue(state.snapshot().voice["is_recording"])
        service.finish_recording("PTT RELEASED", source="JOYSTICK")
        wait_until(lambda: service._worker is None)
        self.assertEqual(recorder.stop_calls, 1)

    def test_release_during_microphone_open_does_not_leave_it_recording(self):
        entered, release = threading.Event(), threading.Event()

        class SlowRecorder(FakeRecorder):
            def start(self):
                super().start()
                entered.set()
                release.wait(2)

        service, state, recorder, provider = self.build(["note quick"], recorder=SlowRecorder())
        opening = threading.Thread(target=service.begin_recording, args=("JOYSTICK",))
        closing = threading.Thread(target=service.finish_recording, args=("PTT RELEASED", "JOYSTICK"))
        opening.start()
        try:
            self.assertTrue(entered.wait(1))
            closing.start()
        finally:
            release.set()
            opening.join(2)
            if closing.ident is not None:
                closing.join(2)
        wait_until(lambda: service._worker is None)
        self.assertFalse(state.snapshot().voice["is_recording"])
        self.assertEqual(recorder.stop_calls, 1)

    def test_backlog_is_bounded_and_recording_recovers_when_drained(self):
        texts = [f"note {i}" for i in range(10)]
        service, state, recorder, provider = self.build(texts, paused=True)
        self.speak(service)
        self.assertTrue(provider.entered.wait(1))
        for _ in range(service.MAX_PENDING_CLIPS):
            self.speak(service)
        service.begin_recording("JOYSTICK")
        self.assertEqual(state.snapshot().voice["status"], "VOICE BUSY")
        self.assertEqual(recorder.start_calls, 9)
        provider.release.set()
        wait_until(lambda: service._worker is None)
        self.speak(service)
        wait_until(lambda: service._worker is None)
        self.assertEqual(len(state.snapshot().notes), 10)
        self.assertEqual(recorder.stop_calls, 10)

    def test_slow_render_does_not_block_ptt_release(self):
        service, state, recorder, provider = self.build(["note first", "note second"])
        rendering, release = threading.Event(), threading.Event()

        def slow_render(snapshot):
            rendering.set()
            release.wait(2)

        service._render_snapshot = slow_render
        self.addCleanup(release.set)
        self.speak(service)
        self.assertTrue(rendering.wait(1))
        service.begin_recording("JOYSTICK")
        stopped = threading.Event()

        def finish():
            service.finish_recording("PTT RELEASED", source="JOYSTICK")
            stopped.set()

        thread = threading.Thread(target=finish)
        thread.start()
        try:
            self.assertTrue(stopped.wait(0.5))
            self.assertEqual(recorder.stop_calls, 2)
        finally:
            release.set()
            thread.join(2)
        wait_until(lambda: service._worker is None)


if __name__ == "__main__":
    unittest.main()
