from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dcs_ai_copilot.case3 import Case3State, calculate_hold_plan, resolve_eat
from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.voice.notes import parse_voice_note
from dcs_ai_copilot.voice.router import apply_case3_command, parse_command
from test_voice_ptt import FakeRecorder, SequenceTranscriber, _build_service


class Case3Tests(unittest.TestCase):
    def test_a_partial_hold(self):
        plan = calculate_hold_plan(datetime(2026, 9, 13, 13, 20, 20), datetime(2026, 9, 13, 13, 32))
        self.assertEqual(plan.time_to_eat, timedelta(minutes=11, seconds=40))
        self.assertEqual(plan.full_holds, 1)
        self.assertEqual(plan.remaining_time, timedelta(minutes=5, seconds=40))
        self.assertEqual(plan.final_hold_adjustment, timedelta(seconds=-20))

    def test_b_hour_boundary(self):
        plan = calculate_hold_plan(datetime(2026, 9, 13, 13, 58), datetime(2026, 9, 13, 14, 4))
        self.assertEqual(plan.time_to_eat, timedelta(minutes=6))
        self.assertEqual((plan.full_holds, plan.remaining_time, plan.final_hold_adjustment),
                         (1, timedelta(0), timedelta(0)))

    def test_c_midnight(self):
        now = datetime(2026, 9, 13, 23, 58)
        eat = resolve_eat("0004", now)
        self.assertEqual(eat, datetime(2026, 9, 14, 0, 4))
        self.assertEqual(calculate_hold_plan(now, eat).time_to_eat, timedelta(minutes=6))

    def test_d_notes_preserve_legacy_body(self):
        for text in ("note tanker twenty miles north", "note case three", "note eat three two",
                     "note reset case three", "notes tanker north", "Notera fuel 4200"):
            with self.subTest(text=text):
                command = parse_command(text)
                self.assertEqual(command.kind, "note")
                self.assertEqual(command.value, parse_voice_note(text))

    def test_e_f_navigation_and_reset_isolation(self):
        state = KneeboardState()
        state.add_note("keep this")
        for text, expected in (("case three", "case3"), ("notes", "notes"),
                               ("Show CASE III!", "case3"), ("back to notes.", "notes")):
            self.assertTrue(apply_case3_command(parse_command(text), state))
            self.assertEqual(state.as_json_data()["active_view"], expected)
        state.case3.set_eat("32", datetime(2026, 9, 13, 13, 20))
        apply_case3_command(parse_command("reset case three"), state)
        self.assertIsNone(state.case3.as_json_data()["eat"])
        self.assertEqual(state.snapshot().notes[0].text, "keep this")

    def test_g_eat_formats_and_next_occurrence(self):
        now = datetime(2026, 9, 13, 13, 20)
        for text, expected in (("eat three two", "32"), ("eat 32", "32"),
                               ("eat one four three two", "1432"), ("eat 1432", "1432"),
                               ("E.A.T. 14:32!", "1432")):
            self.assertEqual(parse_command(text).value, expected)
            state = KneeboardState()
            crossing = now.replace(second=20, microsecond=123456)
            apply_case3_command(parse_command(text), state, crossing)
            state.case3.set_crossing(crossing)
            data = state.case3.as_json_data(crossing)
            eat = datetime.fromisoformat(data["eat"])
            self.assertEqual(eat, datetime(2026, 9, 13, 14 if expected == "1432" else 13, 32))
            self.assertEqual(data["marshal_crossing_time"], "2026-09-13T13:20:20")
            self.assertEqual(data["crossing_to_eat_seconds"], 4300 if expected == "1432" else 700)
        self.assertEqual(resolve_eat("32", now), now.replace(minute=32))
        self.assertEqual(resolve_eat("32", now.replace(minute=33)), now.replace(hour=14, minute=32))
        self.assertEqual(resolve_eat("32", now.replace(minute=32)), now.replace(minute=32))
        self.assertEqual(resolve_eat("32", now.replace(minute=32, second=1)), now.replace(hour=14, minute=32))
        # Minutes 1–60 are valid on their own since the MA CASE 3 work; 60 is the top of the hour.
        self.assertEqual(resolve_eat("60", now), datetime(2026, 9, 13, 14, 0))
        self.assertEqual(resolve_eat("1", now), datetime(2026, 9, 13, 14, 1))
        for invalid in ("61", "2400", "1260", "12345", "garbage", ""):
            with self.assertRaises(ValueError):
                resolve_eat(invalid, now)

    def test_h_crossing_aliases(self):
        now = datetime(2026, 9, 13, 13, 20, 20)
        for text in ("marshal crossing now", "crossing marshal now", "marshal now"):
            state = KneeboardState()
            apply_case3_command(parse_command(text), state, now)
            self.assertEqual(state.case3.as_json_data(now)["marshal_crossing_time"], now.isoformat())

    def test_clock_status_and_plan_remain_distinct(self):
        state = Case3State()
        crossing = datetime(2026, 9, 13, 13, 20, 20)
        state.set_crossing(crossing)
        state.set_eat("32", crossing)
        for minute, second, status in ((31, 59, "EARLY"), (32, 0, "ON TIME"), (32, 1, "LATE")):
            data = state.as_json_data(crossing.replace(minute=minute, second=second))
            self.assertEqual(data["status"], status)
            self.assertEqual(data["full_holds"], 1)
            self.assertEqual(data["remaining_time_seconds"], 340)
        plan = calculate_hold_plan(crossing + timedelta(minutes=20), crossing)
        self.assertEqual(plan.full_holds, 0)
        self.assertEqual(plan.remaining_time, timedelta(0))
        with self.assertRaises(ValueError):
            calculate_hold_plan(crossing, crossing, timedelta(0))

    def test_transcription_pipeline_preserves_notes_and_routes_case3(self):
        state = KneeboardState()
        texts = ["note tanker twenty miles north", "case three", "eat three two",
                 "marshal crossing now", "case three status", "notes", "reset case three"]
        service = _build_service(state=state, transcriber=SequenceTranscriber(texts))
        for text in texts:
            service._transcribe_and_parse(FakeRecorder().stop())
            self.assertFalse(state.snapshot().voice["last_error"], text)
            if text == "case three":
                self.assertEqual(state.as_json_data()["active_view"], "case3")
            if text == "marshal crossing now":
                self.assertIsNotNone(state.case3.as_json_data()["marshal_crossing_time"])
        self.assertEqual(state.snapshot().notes[0].text, "tanker twenty miles north")
        self.assertEqual(state.as_json_data()["active_view"], "case3")
        self.assertIsNone(state.case3.as_json_data()["eat"])

    def test_theme_commands_through_transcription_and_view_switches(self):
        state = KneeboardState()
        self.assertEqual(state.as_json_data()["theme"], "night")
        commands = [("case three", "night", "case3"), ("notes", "night", "notes"),
                    ("day mode", "day", "notes"), ("case three", "day", "case3"),
                    ("notes", "day", "notes"), ("night mode", "night", "notes"),
                    ("note day mode", "night", "notes")]
        service = _build_service(state=state, transcriber=SequenceTranscriber([x[0] for x in commands]))
        for text, theme, view in commands:
            service._transcribe_and_parse(FakeRecorder().stop())
            self.assertEqual(state.as_json_data()["theme"], theme, text)
            self.assertEqual(state.as_json_data()["active_view"], view, text)
        self.assertEqual(state.snapshot().notes[0].text, "day mode")


if __name__ == "__main__":
    unittest.main()
