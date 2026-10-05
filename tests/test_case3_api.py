import json
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.web.server import start_kneeboard_server


class Case3ApiTests(unittest.TestCase):
    def setUp(self):
        self.state = KneeboardState()
        self.server, self.thread = start_kneeboard_server(self.state, port=0)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, path, body=None):
        req = Request(self.url + path, data=json.dumps(body).encode() if body is not None else None,
                      headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=2) as response:
            return json.load(response)

    def test_api_workflow_and_note_isolation(self):
        self.state.add_note("keep")
        self.assertEqual(self.request("/api/state")["active_view"], "notes")
        self.assertEqual(self.request("/api/view", {"view": "case3"})["active_view"], "case3")
        self.request("/api/case3/eat", {"eat": "1432"})
        self.request("/api/case3/crossing", {})
        data = self.request("/api/case3")
        self.assertIsNotNone(data["eat"])
        self.assertIsNotNone(data["marshal_crossing_time"])
        self.request("/api/case3/reset", {})
        cleared = self.request("/api/case3")
        self.assertIsNone(cleared["eat"])
        self.assertEqual(cleared["timeline"], [])
        self.assertIsNone(cleared["current_phase"])
        self.assertIsNone(cleared["time_to_next_seconds"])
        self.assertEqual(cleared["status"], "READY")
        self.assertEqual(self.request("/api/state")["active_view"], "case3")
        self.assertEqual(self.request("/api/state")["notes"][0]["text"], "keep")

    def test_invalid_commands_do_not_mutate(self):
        for path, body in (("/api/view", {"view": "invalid"}), ("/api/view", {"view": []}),
                           ("/api/case3/eat", {"eat": "2460"}), ("/api/case3/eat", {"eat": 32}),
                           ("/api/case3/eat", [])):
            with self.assertRaises(HTTPError) as error:
                self.request(path, body)
            self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.state.as_json_data()["active_view"], "notes")
        self.assertIsNone(self.state.case3.as_json_data()["eat"])

    def test_cross_origin_rejected(self):
        req = Request(self.url + "/api/case3/reset", data=b"{}",
                      headers={"Content-Type": "application/json", "Origin": "https://example.org"})
        with self.assertRaises(HTTPError) as error:
            urlopen(req, timeout=2)
        self.assertEqual(error.exception.code, 403)

    def test_theme_persists_across_views(self):
        self.assertEqual(self.request("/api/state")["theme"], "night")
        self.request("/api/theme", {"theme": "day"})
        self.assertEqual(self.request("/api/view", {"view": "case3"})["theme"], "day")
        self.assertEqual(self.request("/api/view", {"view": "notes"})["theme"], "day")
        self.assertEqual(self.request("/api/theme", {"theme": "night"})["theme"], "night")
        with self.assertRaises(HTTPError) as error:
            self.request("/api/theme", {"theme": "invalid"})
        self.assertEqual(error.exception.code, 400)
