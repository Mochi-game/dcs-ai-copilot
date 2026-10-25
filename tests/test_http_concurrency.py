from __future__ import annotations

import socket
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.web.server import build_request_handler, start_kneeboard_server


class HTTPConcurrencyTests(unittest.TestCase):
    def test_idle_browser_connection_does_not_block_dashboard(self):
        state = KneeboardState()
        accepted = threading.Event()
        handler = build_request_handler(state)

        class ObservedHandler(handler):
            def setup(self):
                super().setup()
                accepted.set()

        with patch("dcs_ai_copilot.web.server.build_request_handler", return_value=ObservedHandler):
            server, thread = start_kneeboard_server(state, port=0)
        idle = socket.create_connection(server.server_address, timeout=2)
        try:
            self.assertTrue(accepted.wait(1))
            with urlopen(f"http://127.0.0.1:{server.server_port}/api/state", timeout=1) as response:
                self.assertEqual(response.status, 200)
        finally:
            idle.close()
            server.shutdown()
            server.server_close()
            thread.join(2)

    def test_slow_microphone_query_does_not_block_state_requests(self):
        entered, release = threading.Event(), threading.Event()

        class SlowDevices:
            def list_microphones(self):
                entered.set()
                release.wait(3)
                return {"devices": [], "selected": ""}

        server, thread = start_kneeboard_server(KneeboardState(), port=0, voice_service=SlowDevices())
        url = f"http://127.0.0.1:{server.server_port}"
        errors = []

        def request_devices():
            try:
                with urlopen(url + "/api/microphones", timeout=4) as response:
                    response.read()
            except Exception as exc:
                errors.append(exc)

        query = threading.Thread(target=request_devices)
        query.start()
        try:
            self.assertTrue(entered.wait(1))
            with urlopen(url + "/api/state", timeout=1) as response:
                self.assertEqual(response.status, 200)
        finally:
            release.set()
            query.join(5)
            server.shutdown()
            server.server_close()
            thread.join(2)
        self.assertEqual(errors, [])

    def test_idle_connection_times_out(self):
        server, thread = start_kneeboard_server(KneeboardState(), port=0)
        server.connection_timeout = 0.05
        try:
            with socket.create_connection(server.server_address, timeout=1) as idle:
                idle.settimeout(1)
                self.assertEqual(idle.recv(1), b"")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


if __name__ == "__main__":
    unittest.main()
