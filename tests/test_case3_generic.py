"""Standalone CASE III assignments, hold origins and command isolation."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dcs_ai_copilot.case3 import Case3State, calculate_hold_plan, hold_lengths
from dcs_ai_copilot.clock import ClockReading
from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.voice.router import apply_case3_command, parse_command


class GenericCase3Tests(unittest.TestCase):
    now = datetime(2026, 9, 30, 20, 18, 0)

    def test_combined_readback_and_reciprocal(self):
        command = parse_command(
            "case three marshal two zero zero, two two, angels seven, "
            "time three two, button one five, final bearing one seven zero, "
            "TACAN seven two X, ICLS one")
        self.assertEqual(command.route_name, "CASE3_ASSIGNMENT")
        state = KneeboardState()
        apply_case3_command(command, state, self.now)
        data = state.case3.as_json_data(self.now)
        self.assertEqual(data["assignment"], {"radial": 200, "dme": 22, "angels": 7,
                                              "button": 15, "fb": 170, "tacan": "72X", "icls": 1})
        self.assertEqual(data["inbound_course"], 20)
        self.assertEqual(data["eat"], self.now.replace(minute=32).isoformat())

    def test_spaced_punctuation_and_explicit_labels(self):
        command = parse_command("MARSHAL... TWO... ERO... ERO")
        self.assertEqual(command.route_name, "CASE3_INVALID")
        command = parse_command("radial two eight zero, D M E two one, angels six, "
                                "push time three two, approach button one seven")
        state = KneeboardState()
        apply_case3_command(command, state, self.now)
        data = state.case3.as_json_data(self.now)
        self.assertEqual(data["inbound_course"], 100)
        self.assertEqual(data["assignment"]["dme"], 21)
        self.assertEqual(data["assignment"]["button"], 17)

    def test_repeated_crossing_replans_without_changing_eat(self):
        state = Case3State()
        state.set_eat("32", self.now)
        state.set_crossing(self.now)
        first = state.as_json_data(self.now)
        later = self.now.replace(minute=26, second=17)
        state.set_crossing(later)
        second = state.as_json_data(later)
        self.assertEqual(second["eat"], first["eat"])
        self.assertEqual(second["marshal_crossing_time"], later.isoformat())
        self.assertEqual(second["crossing_to_eat_seconds"], 343)
        self.assertEqual(sum(second["hold_lengths_seconds"]), 343)

    def test_hold_examples_end_inbound_at_fix(self):
        for minutes, lengths in ((6, [360]), (11, [360, 300]), (14, [420, 420])):
            with self.subTest(minutes=minutes):
                plan = calculate_hold_plan(self.now, self.now + timedelta(minutes=minutes))
                self.assertEqual(hold_lengths(plan), lengths)
                self.assertEqual(plan.phases[-1].name, "INBOUND")
                self.assertEqual(plan.phases[-1].end, self.now + timedelta(minutes=minutes))
                for lap in range(1, len(lengths) + 1):
                    phases = [p for p in plan.phases if p.hold_index == lap]
                    self.assertEqual([p.duration_seconds for p in phases if p.name.startswith("TURN")], [120, 120])
                    self.assertEqual(phases[1].duration_seconds + phases[3].duration_seconds,
                                     lengths[lap - 1] - 240)
        too_short = calculate_hold_plan(self.now, self.now + timedelta(seconds=239))
        self.assertFalse(too_short.feasible)
        self.assertEqual(too_short.phases, ())

    def test_silence_does_not_commence_and_spoken_command_does(self):
        state = KneeboardState()
        state.case3.set_eat("32", self.now)
        state.case3.set_crossing(self.now)
        self.assertEqual(state.case3.as_json_data(self.now.replace(minute=32))["phase"], "HOLD")
        apply_case3_command(parse_command("commencing"), state, self.now.replace(minute=32))
        data = state.case3.as_json_data(self.now.replace(minute=32))
        self.assertEqual(data["phase"], "COMMENCE")
        self.assertEqual(len(data["approach_guidance"]), 5)
        old_crossing = data["marshal_crossing_time"]
        state.case3.set_crossing(self.now.replace(minute=33))
        self.assertEqual(state.case3.as_json_data(self.now.replace(minute=33))["marshal_crossing_time"], old_crossing)

    def test_clear_isolation_and_malformed_readback(self):
        state = KneeboardState()
        state.set_theme("day")
        state.add_note("keep")
        apply_case3_command(parse_command("marshal two zero zero two two angels seven time three two button one five"),
                            state, self.now)
        before = state.case3.as_json_data(self.now)
        bad = parse_command("marshal four hundred, angels")
        self.assertEqual(bad.route_name, "CASE3_INVALID")
        with self.assertRaises(ValueError):
            apply_case3_command(bad, state, self.now)
        self.assertEqual(state.case3.as_json_data(self.now)["assignment"], before["assignment"])
        apply_case3_command(parse_command("clear case"), state)
        self.assertEqual(state.case3.as_json_data(self.now)["assignment"], {})
        self.assertIsNone(state.case3.as_json_data(self.now)["eat"])
        self.assertEqual(state.snapshot().notes[0].text, "keep")
        self.assertEqual(state.snapshot().app["theme"], "day")
        state.clear_notes()
        self.assertEqual(state.snapshot().notes, [])
        self.assertEqual(state.snapshot().app["theme"], "day")

    def test_manual_pc_clock_sync_is_session_scoped(self):
        self.assertEqual(parse_command("sync clock 10:21").value, "1021")
        reading = ClockReading(self.now, "PC", ("PC",))
        case3 = Case3State(lambda: reading)
        case3.sync_pc_time("1021")
        self.assertEqual(case3.as_json_data()["clock_source"], "MANUAL")
        self.assertEqual(case3.as_json_data()["current_time"][11:19], "10:21:00")
        case3.set_eat("32")
        self.assertEqual(case3.as_json_data()["eat"][11:19], "10:32:00")
        case3.reset()
        self.assertEqual(case3.as_json_data()["clock_source"], "PC")

    def test_time_source_change_clears_commence_but_late_fb_does_not(self):
        readings = [ClockReading(self.now, "PC", ("PC",))]
        case3 = Case3State(lambda: readings[0])
        case3.set_eat("32")
        case3.commence()
        case3.set_assignment({"fb": 170})
        self.assertEqual(case3.as_json_data()["phase"], "COMMENCE")
        self.assertIn("170", case3.as_json_data()["approach_guidance"][2])
        readings[0] = ClockReading(self.now, "MISSION", ("MISSION", 1))
        data = case3.as_json_data()
        self.assertEqual(data["phase"], "HOLD")
        self.assertIsNone(data["eat"])
        self.assertIsNone(data["commenced_at"])


if __name__ == "__main__":
    unittest.main()
