"""Mission clock, spoken EAT forms, bare crossing, lap gauge and turn-inbound cue."""
import json
import logging
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dcs_ai_copilot.case3 import (HOLD_SPEED_KT, Case3State,
                                  calculate_hold_plan, hold_lengths)
from dcs_ai_copilot.clock import MissionClock
from dcs_ai_copilot.dcs_bios.reader import DcsBiosReader, DcsBiosReaderConfig
from dcs_ai_copilot.dcs_bios.reference import load_reference_data
from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.voice.router import apply_case3_command, parse_command

TODAY = datetime(2026, 9, 26, 19, 0, 0)
TWENTY_TWO = 22 * 3600


class FakeTime:
    def __init__(self):
        self.mono = 100.0

    def monotonic(self):
        return self.mono


def mission_clock():
    fake = FakeTime()
    return MissionClock(monotonic=fake.monotonic, wall=lambda: TODAY), fake


class MissionClockTests(unittest.TestCase):
    def test_pc_clock_until_mission_time_arrives(self):
        clock, _ = mission_clock()
        reading = clock.reading()
        self.assertEqual((reading.source, reading.key, reading.time), ("PC", ("PC",), TODAY))

    def test_start_plus_model_time_is_the_cockpit_clock(self):
        clock, _ = mission_clock()
        clock.update(TWENTY_TWO, 12345 * 100 + 67)
        reading = clock.reading()
        self.assertEqual(reading.source, "MISSION")
        self.assertEqual(reading.time, datetime(2026, 9, 26, 22, 0) + timedelta(seconds=12345))

    def test_no_extrapolation_so_a_pause_freezes_the_clock(self):
        clock, fake = mission_clock()
        clock.update(TWENTY_TWO, 6000)
        first = clock.reading()
        fake.mono += 4
        self.assertEqual(clock.reading().time, first.time)
        self.assertTrue(clock.reading().live)
        fake.mono += 2
        self.assertFalse(clock.reading().live)
        self.assertEqual(clock.reading().key, first.key)

    def test_past_midnight_rolls_the_date(self):
        clock, _ = mission_clock()
        clock.update(23 * 3600 + 3590, 20 * 100)
        self.assertEqual(clock.reading().time, datetime(2026, 9, 27, 0, 0, 10))

    def test_restart_needs_the_drop_twice_and_a_torn_packet_is_ignored(self):
        clock, _ = mission_clock()
        clock.update(TWENTY_TWO, 70000 * 100)
        key = clock.reading().key
        clock.update(TWENTY_TWO, 5 * 100)          # one torn / odd packet
        self.assertEqual(clock.reading().key, key)
        clock.update(TWENTY_TWO, 70001 * 100)
        self.assertEqual(clock.reading().key, key)
        clock.update(TWENTY_TWO, 3 * 100)           # a real restart repeats
        clock.update(TWENTY_TWO, 4 * 100)
        self.assertNotEqual(clock.reading().key, key)
        self.assertEqual(clock.reading().time, datetime(2026, 9, 26, 22, 0, 4))

    def test_new_start_time_is_a_new_mission_at_once(self):
        clock, _ = mission_clock()
        clock.update(TWENTY_TWO, 100)
        key = clock.reading().key
        clock.update(TWENTY_TWO - 3600, 100)
        self.assertNotEqual(clock.reading().key, key)


class MissionTimedCase3Tests(unittest.TestCase):
    def test_eat_and_crossing_follow_the_mission_clock(self):
        clock, _ = mission_clock()
        state = Case3State(clock.reading)
        clock.update(TWENTY_TWO, 20 * 60 * 100 + 20 * 100)    # 22:20:20
        state.set_eat("32")
        state.set_crossing()
        data = state.as_json_data()
        self.assertEqual(data["clock_source"], "MISSION")
        self.assertEqual(data["eat"], "2026-09-26T22:32:00")
        self.assertEqual(data["marshal_crossing_time"], "2026-09-26T22:20:20")
        self.assertEqual(data["crossing_to_eat_seconds"], 700)
        clock.update(TWENTY_TWO, 22 * 60 * 100 + 20 * 100)    # two minutes later
        self.assertEqual(state.as_json_data()["current_phase"], "OUTBOUND")

    def test_restarted_mission_clears_the_old_session(self):
        clock, _ = mission_clock()
        state = Case3State(clock.reading)
        clock.update(TWENTY_TWO, 600 * 100)
        state.set_eat("32")
        clock.update(TWENTY_TWO, 1 * 100)
        clock.update(TWENTY_TWO, 2 * 100)
        data = state.as_json_data()
        self.assertIsNone(data["eat"])
        self.assertEqual(data["status"], "READY")

    def test_times_on_the_pc_clock_are_dropped_when_mission_time_starts(self):
        clock, _ = mission_clock()
        state = Case3State(clock.reading)
        state.set_eat("32")
        self.assertEqual(state.as_json_data()["clock_source"], "PC")
        clock.update(TWENTY_TWO, 100)
        self.assertIsNone(state.as_json_data()["eat"])
        state.set_eat("10")
        self.assertEqual(state.as_json_data()["eat"], "2026-09-26T22:10:00")

    def test_reader_feeds_the_state_clock(self):
        state = KneeboardState()
        reader = DcsBiosReader(DcsBiosReaderConfig(False, "239.255.50.10", 5010), state,
                               logging.getLogger("test"))
        start, model = TWENTY_TWO, 75000 * 100
        reader._publish_mission_time({
            "TIME_START_HIGH": {"raw": start // 65536}, "TIME_START_LOW": {"raw": start % 65536},
            "TIME_MODEL_HIGH": {"raw": model // 65536}, "TIME_MODEL_LOW": {"raw": model % 65536}})
        reading = state.mission_clock.reading()
        self.assertEqual(reading.source, "MISSION")
        self.assertEqual(reading.time.time().isoformat(), "18:50:00")    # 22:00 + 20:50 h
        reader._publish_mission_time({"TIME_START_HIGH": {"raw": 0}})     # incomplete: ignored
        self.assertEqual(state.mission_clock.reading().time, reading.time)

    def test_common_data_json_supplies_the_time_words(self):
        document = {"Time": {name: {"identifier": name, "outputs": [
            {"type": "integer", "address": address, "mask": 65535, "shift_by": 0}]}
            for name, address in (("TIME_START_HIGH", 1094), ("TIME_START_LOW", 1096),
                                  ("TIME_MODEL_HIGH", 1098), ("TIME_MODEL_LOW", 1100))}}
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "CommonData.json").write_text(json.dumps(document), encoding="utf-8")
            controls = load_reference_data([Path(folder)]).controls
        self.assertEqual(controls["TIME_MODEL_LOW"].address, 1100)
        self.assertEqual(len([name for name in controls if name.startswith("TIME_")]), 4)


class SpokenCommandTests(unittest.TestCase):
    now = datetime(2026, 9, 26, 13, 20, 20)

    def eat(self, text):
        state = KneeboardState()
        command = parse_command(text)
        self.assertEqual(command.kind, "eat", text)
        apply_case3_command(command, state, self.now)
        return datetime.fromisoformat(state.case3.as_json_data(self.now)["eat"])

    def test_minute_one_to_sixty_in_every_spoken_form(self):
        for text, expected in (
                ("EAT five", (13, 5 + 0)), ("eat 5", (13, 5)), ("eat one", (13, 1)),
                ("EAT three two", (13, 32)), ("E A T three two", (13, 32)), ("E.A.T. 32", (13, 32)),
                ("eat thirty two", (13, 32)), ("eat thirty-two", (13, 32)), ("eat forty", (13, 40)),
                ("eat fifteen", (13, 15)), ("eat three to", (13, 32)), ("eat at 45", (13, 45)),
                ("eat sixty", (14, 0)), ("eat 60", (14, 0)),
                ("eat fourteen thirty two", (14, 32)), ("eat one four three two", (14, 32))):
            with self.subTest(text=text):
                eat = self.eat(text)
                expected_time = self.now.replace(hour=expected[0], minute=expected[1], second=0)
                if expected_time < self.now:
                    expected_time += timedelta(hours=1)
                self.assertEqual(eat, expected_time)

    def test_bare_crossing_in_either_view(self):
        for text in ("crossing", "Crossing.", "crossing now"):
            self.assertEqual(parse_command(text, active_view="case3").kind, "crossing", text)
            self.assertEqual(parse_command(text, active_view="notes").kind, "crossing", text)
        state = KneeboardState()
        state.set_view("case3")
        apply_case3_command(parse_command("crossing", "case3"), state, self.now)
        self.assertEqual(state.case3.as_json_data(self.now)["marshal_crossing_time"],
                         self.now.isoformat())

    def test_case_three_still_opens_the_page(self):
        self.assertEqual(parse_command("case three").value, "case3")


class LapGaugeAndCueTests(unittest.TestCase):
    crossing = datetime(2026, 9, 26, 22, 0, 0)

    def data(self, total, elapsed):
        state = Case3State()
        eat = self.crossing + timedelta(seconds=total)
        state.set_eat(eat.strftime("%H%M"), self.crossing)
        state.set_crossing(self.crossing)
        return state.as_json_data(self.crossing + timedelta(seconds=elapsed))

    def test_short_remainder_extends_the_last_lap_never_shortens_turns(self):
        self.assertEqual(hold_lengths(calculate_hold_plan(self.crossing, self.crossing + timedelta(minutes=8))), [480])
        for total, lengths in ((360, [360]), (480, [480]), (660, [360, 300]), (780, [360, 420]),
                               (840, [420, 420]), (900, [300, 300, 300]),
                               (1080, [360, 360, 360]), (1200, [400, 400, 400])):
            plan = calculate_hold_plan(self.crossing, self.crossing + timedelta(seconds=total))
            self.assertEqual(hold_lengths(plan), lengths, total)
            self.assertTrue(all(p.duration_seconds == 120 for p in plan.phases if p.name.startswith("TURN")))

    def test_gauge_says_how_many_laps_are_left(self):
        cases = [
            (1080, 0, "TWO MORE LAPS · NEXT 6:00"),
            (1080, 400, "ONE MORE LAP · NEXT 6:00"),
            (1080, 800, "LAST LAP · COMMENCE AT MARSHAL"),
            (780, 10, "ONE MORE LAP · NEXT 7:00 EXTENDED"),
            (660, 10, "ONE MORE LAP · NEXT 5:00 SHORT LEGS"),
            (480, 10, "LAST LAP · COMMENCE AT MARSHAL"),
        ]
        for total, elapsed, advice in cases:
            with self.subTest(total=total, elapsed=elapsed):
                self.assertEqual(self.data(total, elapsed)["lap_advice"], advice)

    def test_turn_inbound_cue_and_warning(self):
        # 6:00 lap: TURN 1 0–120, OUTBOUND 120–180, TURN 2 180–300, INBOUND 300–360.
        for elapsed, cue, seconds, urgent in ((10, "OUTBOUND TURN", 110, False),
                                              (130, "TURN INBOUND IN", 50, False),
                                              (164, "TURN INBOUND IN", 16, False),
                                              (165, "TURN INBOUND IN", 15, True),
                                              (200, "INBOUND TURN", 100, False),
                                              (330, "COMMENCE IN", 30, False)):
            with self.subTest(elapsed=elapsed):
                data = self.data(360, elapsed)
                self.assertEqual((data["cue"], data["cue_seconds"], data["cue_urgent"]),
                                 (cue, seconds, urgent))
        self.assertEqual(self.data(720, 330)["cue"], "NEXT LAP IN")
        self.assertIsNone(self.data(720, 720)["cue"])

    def test_preview_before_crossing(self):
        state = Case3State()
        now = datetime(2026, 9, 26, 22, 20, 20)
        state.set_eat("32", now)
        self.assertEqual(state.as_json_data(now)["crossing_preview"], "IF CROSSING NOW: 2 LAPS · 6:00 + 5:40")
        self.assertEqual(state.as_json_data(now.replace(minute=24, second=20))["crossing_preview"],
                         "IF CROSSING NOW: 1 LAP · 7:40")
        self.assertEqual(state.as_json_data(now.replace(minute=29))["crossing_preview"],
                         "IF CROSSING NOW: UNDER 4:00 · NO LAP")
        state.set_crossing(now)
        self.assertIsNone(state.as_json_data(now)["crossing_preview"])

    def test_commence_fix_is_published(self):
        data = self.data(360, 0)
        self.assertIsNone(data["commence_dme"])
        self.assertIsNone(data["marshal_altitude_ft"])
        self.assertEqual(data["hold_speed_kt"], HOLD_SPEED_KT)


if __name__ == "__main__":
    unittest.main()
