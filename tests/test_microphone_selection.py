from __future__ import annotations

import configparser
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_voice_ptt import FakeRecorder, _build_service
from test_voice_reliability import PausedTranscriber, wait_until
from dcs_ai_copilot.config import save_voice_input
from dcs_ai_copilot.voice.audio import microphone_choices
from dcs_ai_copilot.web.server import start_kneeboard_server


CHOICES = [{"value": "", "label": "Windows default microphone"},
           {"value": "Headset, MME", "label": "Headset, MME"}]


class MicrophoneSelectionTests(unittest.TestCase):
    def setUp(self):
        self.service = _build_service()
        self.service._render_snapshot = lambda snapshot: None
        self.addCleanup(self.service.stop)
        self.old = self.service._recorder
        self.candidate = FakeRecorder()
        self.candidate.validate_input = Mock()
        self.candidate.describe_input = Mock(return_value="Headset (MME)")
        self.factory = patch("dcs_ai_copilot.voice.ptt.MicrophoneRecorder", return_value=self.candidate).start()
        self.choices = patch("dcs_ai_copilot.voice.ptt.microphone_choices", return_value=CHOICES).start()
        self.addCleanup(patch.stopall)
        self.saved = Mock()
        self.service._save_input_device = self.saved

    def test_switch_saves_name_and_next_ptt_uses_new_recorder(self):
        self.service.select_microphone("Headset, MME")
        self.saved.assert_called_once_with("Headset, MME")
        self.assertEqual(self.candidate.start_calls, 0)
        self.assertEqual(self.service._state.snapshot().voice["selected_input"], "Headset, MME")
        self.assertEqual(self.service.list_microphones()["selected"], "Headset, MME")
        self.service.begin_recording("JOYSTICK")
        self.service.finish_recording("PTT RELEASED", source="JOYSTICK")
        wait_until(lambda: self.service._worker is None)
        self.assertEqual(self.candidate.start_calls, 1)
        self.assertEqual(self.candidate.stop_calls, 1)
        self.assertEqual(self.old.start_calls, 0)

    def test_recording_cannot_be_interrupted_by_selection(self):
        self.service.begin_recording("JOYSTICK")
        with self.assertRaisesRegex(RuntimeError, "Release PTT"):
            self.service.select_microphone("Headset, MME")
        self.assertIs(self.service._recorder, self.old)
        self.saved.assert_not_called()
        self.assertEqual(self.old.stop_calls, 0)
        self.assertTrue(self.service._state.snapshot().voice["is_recording"])

    def test_ptt_start_during_validation_prevents_switch(self):
        self.candidate.validate_input.side_effect = lambda: self.service.begin_recording("KEYBOARD")
        with self.assertRaisesRegex(RuntimeError, "Release PTT"):
            self.service.select_microphone("Headset, MME")
        self.assertIs(self.service._recorder, self.old)
        self.saved.assert_not_called()

    def test_missing_device_keeps_previous_selection(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            self.service.select_microphone("unplugged")
        self.assertIs(self.service._recorder, self.old)
        self.saved.assert_not_called()
        self.assertIn("not found", self.service._state.snapshot().voice["last_error"])

    def test_unsupported_format_keeps_previous_selection(self):
        self.candidate.validate_input.side_effect = ValueError("Unsupported sample rate")
        with self.assertRaises(ValueError):
            self.service.select_microphone("Headset, MME")
        self.assertIs(self.service._recorder, self.old)
        self.saved.assert_not_called()

    def test_save_failure_keeps_previous_recorder_and_shows_error(self):
        self.saved.side_effect = OSError("Disk full")
        with self.assertRaises(OSError):
            self.service.select_microphone("Headset, MME")
        self.assertIs(self.service._recorder, self.old)
        self.assertEqual(self.service._config.input_device, "")
        self.assertIn("Disk full", self.service._state.snapshot().voice["last_error"])

    def test_switch_while_transcribing_preserves_pending_note(self):
        provider = PausedTranscriber(["note before", "note after"])
        self.service._transcriber = provider
        self.addCleanup(provider.release.set)
        self.service.on_press("Key.f13")
        self.service.on_release("Key.f13")
        self.assertTrue(provider.entered.wait(1))
        self.service.select_microphone("Headset, MME")
        self.service.on_press("Key.f13")
        self.service.on_release("Key.f13")
        provider.release.set()
        wait_until(lambda: self.service._worker is None)
        self.assertEqual([note.text for note in self.service._state.snapshot().notes], ["before", "after"])

    def test_default_selection_is_supported(self):
        self.service.select_microphone("")
        self.saved.assert_called_once_with("")
        self.factory.assert_called_once_with(sample_rate=16000, channels=1, input_device="")

    def test_http_switch_persists_and_changes_live_service(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.ini"
            config.write_text("[voice]\ninput_device = Old\n", encoding="utf-8")
            self.service._save_input_device = lambda value: save_voice_input(config, value)
            server, thread = start_kneeboard_server(self.service._state, port=0, voice_service=self.service)
            try:
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/voice/input",
                    data=json.dumps({"device": "Headset, MME"}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(request, timeout=2) as response:
                    self.assertEqual(json.load(response)["voice"]["selected_input"], "Headset, MME")
                parser = configparser.ConfigParser()
                parser.read(config, encoding="utf-8")
                self.assertEqual(parser["voice"]["input_device"], "Headset, MME")
                self.assertIs(self.service._recorder, self.candidate)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)


class MicrophoneConfigTests(unittest.TestCase):
    def test_save_preserves_other_settings_and_loads_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.ini"
            path.write_text("[voice]\ninput_device = Old\nkeyboard_ptt_key = f13\n"
                            "[web]\nport = 8765\n[custom]\nvalue = 100%\n", encoding="utf-8")
            save_voice_input(path, "Headset, MME")
            parser = configparser.ConfigParser(interpolation=None)
            parser.read(path, encoding="utf-8")
            self.assertEqual(parser["voice"]["input_device"], "Headset, MME")
            self.assertEqual(parser["voice"]["keyboard_ptt_key"], "f13")
            self.assertEqual(parser["web"]["port"], "8765")
            self.assertEqual(parser["custom"]["value"], "100%")
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_failed_atomic_replace_leaves_old_config_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.ini"
            original = "[voice]\ninput_device = Old\n"
            path.write_text(original, encoding="utf-8")
            with patch("dcs_ai_copilot.config.os.replace", side_effect=PermissionError("Read only")):
                with self.assertRaises(PermissionError):
                    save_voice_input(path, "Headset, MME")
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_enumeration_includes_host_api_without_recording(self):
        audio = SimpleNamespace(
            query_hostapis=lambda: [{"name": "MME"}, {"name": "WASAPI"}],
            query_devices=lambda: [
                {"name": "Headset", "hostapi": 0, "max_input_channels": 1},
                {"name": "Headset", "hostapi": 1, "max_input_channels": 1},
                {"name": "Speakers", "hostapi": 0, "max_input_channels": 0},
            ],
        )
        with patch.dict(sys.modules, {"sounddevice": audio}):
            self.assertEqual([item["value"] for item in microphone_choices()],
                             ["", "Headset, MME", "Headset, WASAPI"])


class MicrophoneHTTPTests(unittest.TestCase):
    def setUp(self):
        self.service = Mock()
        self.service.list_microphones.return_value = {"devices": CHOICES, "selected": ""}
        from dcs_ai_copilot.kneeboard.state import KneeboardState
        self.state = KneeboardState()
        self.server, self.thread = start_kneeboard_server(self.state, port=0, voice_service=self.service)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, path, body=None, headers=None):
        request = Request(self.url + path, data=None if body is None else json.dumps(body).encode(),
                          headers=headers or {"Content-Type": "application/json", "Origin": self.url})
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, response.read().decode()

    def test_list_and_switch(self):
        code, body = self.request("/api/microphones")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["devices"], CHOICES)
        code, _ = self.request("/api/voice/input", {"device": "Headset, MME"})
        self.assertEqual(code, 200)
        self.service.select_microphone.assert_called_once_with("Headset, MME")

    def test_errors_do_not_kill_http_server(self):
        for error, expected in [(ValueError("Missing"), 400), (RuntimeError("Release PTT"), 409), (OSError("Disk full"), 503)]:
            self.service.select_microphone.side_effect = error
            code, body = self.request("/api/voice/input", {"device": "Headset, MME"})
            self.assertEqual(code, expected)
            self.assertEqual(json.loads(body)["error"], str(error))
        self.assertEqual(self.request("/api/state")[0], 200)

    def test_rejects_cross_origin_and_non_json(self):
        for headers, expected in [
            ({"Content-Type": "application/json", "Origin": "https://example.com"}, 403),
            ({"Content-Type": "text/plain"}, 415),
            ({"Content-Type": "application/json", "Host": "example.com", "Origin": "http://example.com"}, 403),
        ]:
            self.assertEqual(self.request("/api/voice/input", {"device": ""}, headers)[0], expected)
        self.service.select_microphone.assert_not_called()

    def test_rejects_invalid_device_types_and_control_characters(self):
        for value in [None, 3, [], "bad\nname", "x" * 513]:
            self.assertEqual(self.request("/api/voice/input", {"device": value})[0], 400)
        self.service.select_microphone.assert_not_called()

    def test_enumeration_failure_is_reported(self):
        self.service.list_microphones.side_effect = OSError("Audio unavailable")
        code, body = self.request("/api/microphones")
        self.assertEqual(code, 503)
        self.assertEqual(json.loads(body)["error"], "Audio unavailable")


if __name__ == "__main__":
    unittest.main()
