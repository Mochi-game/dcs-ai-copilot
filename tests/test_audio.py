from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.voice.audio import _parse_input_device, list_audio_input_devices


class AudioDeviceTests(unittest.TestCase):
    def test_parse_input_device_allows_default_index_or_name(self) -> None:
        self.assertIsNone(_parse_input_device(""))
        self.assertIsNone(_parse_input_device("default"))
        self.assertEqual(_parse_input_device("2"), 2)
        self.assertEqual(_parse_input_device("USB Microphone"), "USB Microphone")

    def test_list_audio_input_devices_filters_outputs_and_marks_default(self) -> None:
        raw_devices = [
            {"name": "Speakers", "max_input_channels": 0, "default_samplerate": 48000},
            {"name": "VR Headset Mic", "max_input_channels": 1, "default_samplerate": 48000},
            {"name": "USB Microphone", "max_input_channels": 2, "default_samplerate": 16000},
        ]

        devices = list_audio_input_devices(query_devices=lambda: raw_devices, default_device=(2, 0))

        self.assertEqual([device.name for device in devices], ["VR Headset Mic", "USB Microphone"])
        self.assertFalse(devices[0].is_default)
        self.assertTrue(devices[1].is_default)
        self.assertEqual(devices[1].index, 2)
        self.assertEqual(devices[1].max_input_channels, 2)
        self.assertEqual(devices[1].default_sample_rate, 16000)


if __name__ == "__main__":
    unittest.main()
