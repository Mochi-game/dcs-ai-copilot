"""Exact hold sums, absolute phase transitions and reset isolation."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dcs_ai_copilot.case3 import calculate_hold_plan, phase_at
from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.voice.router import apply_case3_command, parse_command
from test_voice_ptt import FakeRecorder, FakeTranscriber, _build_service


class HoldTimelineTests(unittest.TestCase):
    crossing = datetime(2026, 9, 14, 13, 20, 20)

    def plan(self, seconds):
        return calculate_hold_plan(self.crossing, self.crossing + timedelta(seconds=seconds))

    def test_requested_exact_plans(self):
        for seconds, full, final, outbound, inbound in [
            (360, 1, 0, None, None), (720, 2, 0, None, None), (1080, 3, 0, None, None),
            (660, 1, 300, 30, 30), (801, 1, 441, 100, 101), (740, 1, 380, 70, 70),
        ]:
            with self.subTest(seconds=seconds):
                plan = self.plan(seconds)
                self.assertEqual(plan.full_holds, full)
                self.assertEqual(plan.remaining_time, timedelta(seconds=final))
                self.assertEqual(plan.final_outbound_seconds, outbound)
                self.assertEqual(plan.final_inbound_seconds, inbound)
                self.assertEqual(sum(p.duration_seconds for p in plan.phases), seconds)
                self.assertEqual(plan.phases[-1].end, self.crossing + timedelta(seconds=seconds))
                self.assertEqual(sum(p.duration_seconds for p in plan.phases if not p.adjusted), full * 360)
                self.assertEqual(sum(p.duration_seconds for p in plan.phases if p.adjusted), final)

    def test_every_second_up_to_one_hour_conserves_time(self):
        for seconds in range(240, 3601):
            plan = self.plan(seconds)
            self.assertEqual(sum(p.duration_seconds for p in plan.phases), seconds)
            self.assertEqual(sum(p.duration_seconds for p in plan.phases), seconds)
            self.assertTrue(all(p.duration_seconds >= 0 for p in plan.phases))
            self.assertTrue(all(p.duration_seconds == 120 for p in plan.phases if p.name.startswith("TURN")))
            self.assertEqual(plan.phases[0].start, self.crossing)
            self.assertEqual(plan.phases[-1].end, self.crossing + timedelta(seconds=seconds))
            for previous, following in zip(plan.phases, plan.phases[1:]):
                self.assertEqual(previous.end, following.start)
            if plan.remaining_time:
                self.assertIn(plan.final_inbound_seconds - plan.final_outbound_seconds, (0, 1))

    def test_insufficient_and_negative_time_has_no_plan(self):
        for seconds in (-300, 0, 1, 239):
            plan = self.plan(seconds)
            self.assertFalse(plan.feasible)
            self.assertEqual(plan.phases, ())
            self.assertIsNone(plan.final_outbound_seconds)
            self.assertIsNone(phase_at(plan, self.crossing)["time_to_next_seconds"])

    def test_exact_four_minutes_skips_zero_length_legs(self):
        plan = self.plan(240)
        self.assertEqual([p.duration_seconds for p in plan.phases], [120, 0, 120, 0])
        self.assertEqual(phase_at(plan, self.crossing + timedelta(seconds=119))["next_event"], "LEFT 180°")
        self.assertEqual(phase_at(plan, self.crossing + timedelta(seconds=120))["current_phase"], "TURN 2")
        self.assertEqual(phase_at(plan, self.crossing + timedelta(seconds=239))["next_event"], "COMMENCE")
        self.assertEqual(phase_at(plan, self.crossing + timedelta(seconds=240))["time_to_next_seconds"], 0)

    def test_absolute_timeline_boundaries_and_irregular_polls(self):
        plan = self.plan(801)
        cases = [
            (0, "TURN 1", 120, "OUTBOUND", 1),
            (119, "TURN 1", 1, "OUTBOUND", 1),
            (120, "OUTBOUND", 60, "LEFT 180°", 1),
            (156, "OUTBOUND", 24, "LEFT 180°", 1),
            (180, "TURN 2", 120, "INBOUND", 1),
            (208, "TURN 2", 92, "INBOUND", 1),
            (300, "INBOUND", 60, "LEFT 180°", 1),
            (360, "TURN 1", 120, "OUTBOUND", 2),
            (480, "OUTBOUND", 100, "LEFT 180°", 2),
            (580, "TURN 2", 120, "INBOUND", 2),
            (700, "INBOUND", 101, "COMMENCE", 2),
            (800, "INBOUND", 1, "COMMENCE", 2),
        ]
        for elapsed, phase, remaining, event, hold in cases + list(reversed(cases)):
            now = self.crossing + timedelta(seconds=elapsed)
            timing = phase_at(plan, now)
            self.assertEqual((timing["current_phase"], timing["time_to_next_seconds"],
                              timing["next_event"], timing["current_hold"]), (phase, remaining, event, hold))
            self.assertEqual(datetime.fromisoformat(timing["next_event_time"]) - now, timedelta(seconds=remaining))
        for elapsed in (801, 802, 900):
            timing = phase_at(plan, self.crossing + timedelta(seconds=elapsed))
            self.assertIsNone(timing["current_phase"])
            self.assertIsNone(timing["next_event_time"])
            self.assertEqual(timing["next_event"], "COMMENCE")
            self.assertEqual(timing["time_to_next_seconds"], 0)

    def test_five_minute_adjusted_phase_boundaries(self):
        plan = self.plan(660)
        for elapsed, name, remaining in [(360, "TURN 1", 120), (480, "OUTBOUND", 30),
                                         (510, "TURN 2", 120), (630, "INBOUND", 30)]:
            timing = phase_at(plan, self.crossing + timedelta(seconds=elapsed))
            self.assertEqual(timing["current_phase"], name)
            self.assertEqual(timing["time_to_next_seconds"], remaining)
            self.assertTrue(timing["current_hold_adjusted"])

    def test_hour_and_day_boundaries(self):
        for crossing in (datetime(2026, 9, 14, 13, 58), datetime(2026, 9, 14, 23, 58)):
            eat = crossing + timedelta(minutes=6)
            plan = calculate_hold_plan(crossing, eat)
            self.assertEqual(sum(p.duration_seconds for p in plan.phases), 360)
            self.assertEqual(plan.phases[-1].end, eat)
            self.assertEqual(phase_at(plan, crossing + timedelta(minutes=2))["current_phase"], "OUTBOUND")

    def test_state_countdowns_stop_at_eat_and_update_without_revision(self):
        state = KneeboardState()
        crossing = datetime(2026, 9, 14, 13, 18, 39)
        state.case3.set_eat("32", crossing)
        state.case3.set_crossing(crossing)
        revision = state.snapshot().revision
        for seconds, expected in [(0, 120), (55, 65), (120, 60), (156, 24)]:
            data = state.case3.as_json_data(crossing + timedelta(seconds=seconds))
            self.assertEqual(data["time_to_next_seconds"], expected)
            self.assertEqual(data["time_to_commence_seconds"], 801 - seconds)
            self.assertEqual(state.snapshot().revision, revision)
        for seconds, status in [(801, "ON TIME"), (802, "LATE")]:
            data = state.case3.as_json_data(crossing + timedelta(seconds=seconds))
            self.assertEqual(data["time_to_commence_seconds"], 0)
            self.assertEqual(data["time_to_next_seconds"], 0)
            self.assertEqual(data["next_event"], "COMMENCE")
            self.assertIsNone(data["current_phase"])
            self.assertEqual(data["status"], status)

    def test_insufficient_state_keeps_commence_countdown(self):
        state = KneeboardState()
        crossing = datetime(2026, 9, 14, 13, 30)
        state.case3.set_eat("32", crossing)
        state.case3.set_crossing(crossing)
        data = state.case3.as_json_data(crossing)
        self.assertEqual(data["plan_status"], "INSUFFICIENT HOLD TIME")
        self.assertEqual(data["time_to_commence_seconds"], 120)
        self.assertEqual(data["timeline"], [])
        self.assertIsNone(data["full_holds"])
        self.assertIsNone(data["remaining_time_seconds"])
        self.assertIsNone(data["time_to_next_seconds"])

    def test_clear_reset_aliases_clear_all_derived_state_and_allow_restart(self):
        for text in ("clear case three", "clear case 3", "reset case three", "clear case tree",
                     "reset case free", "clear this three", "reset this 3"):
            with self.subTest(text=text):
                state = KneeboardState()
                for index in range(8):
                    state.add_note(f"keep {index}")
                state.set_theme("day")
                state.case3.set_eat("32", self.crossing)
                state.case3.set_crossing(self.crossing)
                old = state.case3.as_json_data(self.crossing)
                self.assertTrue(old["timeline"])
                self.assertEqual(old["current_phase"], "TURN 1")
                before = state.snapshot()
                service = _build_service(state=state, transcriber=FakeTranscriber(text))
                with patch("dcs_ai_copilot.voice.ptt.parse_coordinate_message") as coordinates:
                    service._transcribe_and_parse(FakeRecorder().stop())
                coordinates.assert_not_called()
                data = state.case3.as_json_data(self.crossing + timedelta(minutes=20))
                for field in ("eat", "marshal_crossing_time", "full_holds", "remaining_time_seconds",
                              "final_outbound_seconds", "final_inbound_seconds", "current_phase", "current_hold",
                              "current_hold_adjusted", "next_event", "next_event_time", "time_to_next_seconds",
                              "time_to_commence_seconds", "final_hold_adjustment_seconds", "crossing_to_eat_seconds"):
                    self.assertIsNone(data[field], field)
                self.assertEqual(data["timeline"], [])
                self.assertEqual(data["status"], "READY")
                self.assertEqual(data["plan_status"], "READY")
                self.assertEqual(state.snapshot().notes, before.notes)
                self.assertEqual(state.snapshot().app["theme"], "day")
                self.assertEqual(state.snapshot().app["active_view"], "case3")
                fresh = datetime(2026, 9, 14, 14, 21)
                apply_case3_command(parse_command("EAT three two"), state, fresh)
                apply_case3_command(parse_command("marshal", active_view="case3"), state, fresh)
                data = state.case3.as_json_data(fresh)
                self.assertEqual(data["crossing_to_eat_seconds"], 660)
                self.assertEqual(data["remaining_time_seconds"], 300)
                self.assertEqual(data["timeline"][0]["start"], fresh.isoformat())
                self.assertEqual(data["current_phase"], "TURN 1")

    def test_bare_clear_only_clears_notes(self):
        state = KneeboardState()
        state.set_view("case3")
        state.set_theme("day")
        state.add_note("delete")
        state.case3.set_eat("32", self.crossing)
        state.case3.set_crossing(self.crossing)
        before = state.case3.as_json_data(self.crossing)
        service = _build_service(state=state, transcriber=FakeTranscriber("clear"))
        service._transcribe_and_parse(FakeRecorder().stop())
        self.assertEqual(state.snapshot().notes, [])
        self.assertEqual(state.case3.as_json_data(self.crossing), before)
        self.assertEqual(state.snapshot().app["theme"], "day")
        self.assertEqual(state.snapshot().voice["status"], "NOTES CLEARED")
        self.assertEqual(parse_command("note clear case three").route_name, "NOTE")
