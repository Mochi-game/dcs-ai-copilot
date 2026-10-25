from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dcs_ai_copilot.voice.joystick import (
    JoystickPttListener, WinmmJoystickPttListener, WinmmJoystickDeviceInfo,
)


class JoystickDisconnectTests(unittest.TestCase):
    def test_winmm_disconnect_releases_held_ptt_once(self):
        events = []

        def status(name, detail):
            if name == "JOYSTICK ERROR":
                listener._stop_event.set()

        listener = WinmmJoystickPttListener(
            device_name="Test panel", device_id="auto", button=0,
            on_press=lambda: events.append("press"),
            on_release=lambda: events.append("release"), on_status=status,
        )
        listener._find_device = lambda: WinmmJoystickDeviceInfo(0, "Test panel", 0, 32, 32, 0)
        with patch("dcs_ai_copilot.voice.joystick.sys.platform", "win32"), patch(
            "dcs_ai_copilot.voice.joystick.ctypes.WinDLL", create=True,
        ), patch(
            "dcs_ai_copilot.voice.joystick._read_winmm_buttons",
            side_effect=[1, RuntimeError("USB disconnected")],
        ), patch("dcs_ai_copilot.voice.joystick.time.sleep"):
            listener._run()
        self.assertEqual(events, ["press", "release"])

    def test_pygame_disconnect_releases_held_ptt_once(self):
        events = []

        def status(name, detail):
            if name == "JOYSTICK ERROR":
                listener._stop_event.set()

        listener = JoystickPttListener(
            device_name="Test panel", button=0,
            on_press=lambda: events.append("press"),
            on_release=lambda: events.append("release"), on_status=status,
        )
        device = MagicMock()
        device.get_name.return_value = "Test panel"
        device.get_button.side_effect = [1, RuntimeError("USB disconnected")]
        listener._find_joystick = lambda pygame: device
        with patch("dcs_ai_copilot.voice.joystick._load_pygame"), patch(
            "dcs_ai_copilot.voice.joystick.time.sleep",
        ):
            listener._run()
        self.assertEqual(events, ["press", "release"])


if __name__ == "__main__":
    unittest.main()
