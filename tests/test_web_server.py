from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.voice.parser import parse_coordinate_message
from dcs_ai_copilot.web.server import start_kneeboard_server


class WebServerTests(unittest.TestCase):
    def test_serves_dashboard_html(self) -> None:
        state = KneeboardState()
        server, thread = start_kneeboard_server(state, port=0)
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            with urlopen(url, timeout=2) as response:
                html = response.read().decode("utf-8")

            self.assertIn("<title>AI COPILOT</title>", html)
            self.assertIn("/api/state", html)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_serves_coordinate_state_json(self) -> None:
        state = KneeboardState()
        state.update_dcs_bios(
            status="CONNECTED",
            installed=True,
            aircraft="FA-18C_hornet",
            values={"MASTER_ARM_SW": {"raw": 1, "display": "ARM"}},
        )
        state.update_voice(
            enabled=True,
            status="RECORDING",
            is_recording=True,
            last_transcript="target north 42 15.732 east 041 38.219 elevation 428",
            ptt_key="F13",
            model="gpt-4o-mini-transcribe",
        )
        state.add_capture(
            parse_coordinate_message(
                "target north 42 15.732 east 041 38.219 elevation 428"
            )
        )
        server, thread = start_kneeboard_server(state, port=0)
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/api/state"
            with urlopen(url, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(payload["revision"], 3)
            self.assertEqual(payload["captures"][0]["title"], "TARGET 1")
            self.assertEqual(payload["captures"][0]["latitude"], "N42°15.732'")
            self.assertEqual(payload["captures"][0]["longitude"], "E041°38.219'")
            self.assertEqual(payload["captures"][0]["elevation"], "ELEV 428 FT")
            self.assertEqual(payload["dcs_bios"]["status"], "CONNECTED")
            self.assertEqual(payload["dcs_bios"]["aircraft"], "FA-18C_hornet")
            self.assertEqual(
                payload["dcs_bios"]["values"]["MASTER_ARM_SW"]["display"],
                "ARM",
            )
            self.assertEqual(payload["voice"]["status"], "RECORDING")
            self.assertTrue(payload["voice"]["is_recording"])
            self.assertEqual(payload["voice"]["ptt_key"], "F13")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_state_json_shows_only_six_latest_notes(self) -> None:
        state = KneeboardState()
        for index in range(1, 9):
            state.add_note(f"note {index}")

        payload = state.as_json_data()

        self.assertEqual(payload["note_total_count"], 8)
        self.assertEqual(payload["note_history_count"], 2)
        self.assertEqual([note["title"] for note in payload["notes"]], [
            "NOTE 3",
            "NOTE 4",
            "NOTE 5",
            "NOTE 6",
            "NOTE 7",
            "NOTE 8",
        ])

    def test_rejects_non_loopback_bind_address(self) -> None:
        with self.assertRaises(ValueError):
            start_kneeboard_server(KneeboardState(), host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()
