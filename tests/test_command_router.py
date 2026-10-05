"""Regression coverage for real headset transcripts and consumed routing."""
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.voice.notes import parse_voice_note
from dcs_ai_copilot.voice.router import apply_case3_command, normalize_command, parse_command
from test_voice_ptt import FakeRecorder, FakeTranscriber, _build_service


class CommandRouterTests(unittest.TestCase):
    def test_normalization(self):
        examples = {
            "  Marshal,  crossing now 10. ? ": "marshal crossing now 10",
            "Marshal crossing now, one-zero.": "marshal crossing now one zero",
            "This three.": "this three",
            "E-A-T 14:32": "eat 14:32",
            " E A T three two ": "eat three two",
        }
        for raw, expected in examples.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_command(raw), expected)

    def test_view_and_theme_aliases(self):
        examples = {
            "CASE3_VIEW": ["This three.", "this 3", "Case three.", "case 3", "case tree",
                           "case free", "show case three", "show case 3", "case III"],
            "NOTES_VIEW": ["notes", "show notes", "back to notes"],
            "DAY_MODE": ["day mode", "Daytime."],
            "NIGHT_MODE": ["night mode", "Nighttime."],
        }
        for route, texts in examples.items():
            for text in texts:
                with self.subTest(text=text):
                    self.assertEqual(parse_command(text).route_name, route)

    def test_crossing_aliases_use_system_now_not_suffix(self):
        texts = ["marshal", "marshall", "marshal now", "marshall now", "marshal cross",
                 "marshall cross", "marshal crossing", "marshall crossing", "marshal crossing now",
                 "marshall crossing now", "crossing marshal", "crossing marshal now",
                 "marshal crossing now one zero", "marshal crossing now 10",
                 "Marshal crossing now, one-zero.", "Marshal, crossing now 10.",
                 "marshal crossing now extra words", "marshal cross ten"]
        now = datetime(2026, 9, 14, 13, 20, 20)
        for text in texts:
            with self.subTest(text=text):
                state = KneeboardState()
                state.set_view("case3")
                command = parse_command(text, active_view="case3")
                self.assertEqual(command.route_name, "CASE3_CROSSING")
                apply_case3_command(command, state, now)
                self.assertEqual(state.case3.as_json_data(now)["marshal_crossing_time"], now.isoformat())

    def test_bounded_matching_and_context(self):
        for text in ["marshal", "marshall", "marshal cross", "crossing marshal"]:
            self.assertEqual(parse_command(text, active_view="notes").route_name, "NONE")
        for view in ["notes", "case3"]:
            for text in ["three", "three.", "marshal aircraft at ten", "marshal crossingway",
                         "this three aircraft", "daytime flight", "nighttime flight"]:
                with self.subTest(text=text, view=view):
                    self.assertEqual(parse_command(text, active_view=view).route_name, "NONE")
        # Original explicit commands still work in NOTES.
        self.assertEqual(parse_command("marshal crossing now").route_name, "CASE3_CROSSING")

    def test_notes_keep_priority_and_legacy_text(self):
        for text in ["note marshal crossing at ten", "note Marshal, crossing now 10.",
                     "note This three.", "note Daytime.", "note Nighttime.",
                     "note E-A-T 14:32", "note tanker twenty miles north", "notes case free"]:
            with self.subTest(text=text):
                state = KneeboardState()
                state.set_view("case3")
                service = _build_service(state=state, transcriber=FakeTranscriber(text))
                with patch("dcs_ai_copilot.voice.ptt.parse_coordinate_message") as coordinates:
                    service._transcribe_and_parse(FakeRecorder().stop())
                coordinates.assert_not_called()
                self.assertEqual(state.snapshot().notes[0].text, parse_voice_note(text))
                self.assertEqual(state.snapshot().voice["last_transcript"], text)
                self.assertIsNone(state.case3.as_json_data()["marshal_crossing_time"])
                self.assertIsNone(state.case3.as_json_data()["eat"])
                self.assertEqual(state.snapshot().app["active_view"], "case3")
                self.assertEqual(state.snapshot().app["theme"], "night")

    def test_eat_spelling_preserves_whole_minutes(self):
        now = datetime(2026, 9, 14, 13, 20, 20)
        for text, hour in [("eat three two", 13), ("eat 32", 13),
                           ("eat one four three two", 14), ("eat 1432", 14),
                           ("eat 14:32", 14), ("E A T 14:32", 14), ("E-A-T 14:32", 14)]:
            state = KneeboardState()
            command = parse_command(text)
            self.assertEqual(command.route_name, "CASE3_EAT")
            apply_case3_command(command, state, now)
            self.assertEqual(state.case3.as_json_data(now)["eat"],
                             now.replace(hour=hour, minute=32, second=0).isoformat())

    def test_consumed_commands_never_reach_coordinate_parser(self):
        for text in ["This three.", "Case three.", "case free", "Daytime.", "Nighttime.",
                     "Marshal crossing now, one-zero.", "Marshal, crossing now 10.", "marshal",
                     "eat three two", "E-A-T", "eat 9960", "notes", "reset case three"]:
            with self.subTest(text=text):
                state = KneeboardState()
                state.set_view("case3")
                service = _build_service(state=state, transcriber=FakeTranscriber(text))
                with patch("dcs_ai_copilot.voice.ptt.parse_coordinate_message") as coordinates:
                    service._transcribe_and_parse(FakeRecorder().stop())
                coordinates.assert_not_called()
                self.assertEqual(state.snapshot().notes, [])
                self.assertEqual(state.snapshot().voice["status"],
                                 "COMMAND ERROR" if text in {"E-A-T", "eat 9960"} else "READY")

    def test_raw_normalized_and_route_logged_for_every_transcript(self):
        for text, normalized, route, view in [
            ("Marshal, crossing now 10.", "marshal crossing now 10", "CASE3_CROSSING", "case3"),
            ("This three.", "this three", "CASE3_VIEW", "notes"),
            ("marshal", "marshal", "NONE", "notes"),
            ("note Marshal at ten.", "note marshal at ten", "NOTE", "notes"),
        ]:
            state = KneeboardState()
            state.set_view(view)
            service = _build_service(state=state, transcriber=FakeTranscriber(text))
            with self.assertLogs(service._logger, level="INFO") as captured:
                service._transcribe_and_parse(FakeRecorder().stop())
            output = "\n".join(captured.output)
            self.assertIn(f'STT RAW: "{text}"', output)
            self.assertIn(f'NORMALIZED: "{normalized}"', output)
            self.assertIn(f"ROUTED: {route}", output)
            self.assertEqual(state.snapshot().voice["last_transcript"], text)
            if route == "NONE":
                self.assertIn("Transcript did not parse as coordinate", output)
                self.assertIsNone(state.case3.as_json_data()["marshal_crossing_time"])


if __name__ == "__main__":
    unittest.main()
