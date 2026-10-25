from __future__ import annotations

import sys
import unittest
import io
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.voice.audio import MicrophoneRecorder, _parse_input_device, list_audio_input_devices


class AudioDeviceTests(unittest.TestCase):
    def test_sounddevice_pair_marks_actual_default_microphone(self) -> None:
        class DevicePair:
            def __getitem__(self, index):
                return (1, 3)[index]

        devices = list_audio_input_devices(
            query_devices=lambda: [
                {"name": "Webcam", "max_input_channels": 1},
                {"name": "Headset", "max_input_channels": 1},
            ],
            default_device=DevicePair(),
        )
        self.assertFalse(devices[0].is_default)
        self.assertTrue(devices[1].is_default)

    def test_raw_pcm_recording_stops_and_can_start_again(self) -> None:
        stream = MagicMock()
        factory = MagicMock(return_value=stream)
        with patch.dict(sys.modules, {"sounddevice": SimpleNamespace(RawInputStream=factory)}):
            recorder = MicrophoneRecorder()
            recorder.start()
            callback = factory.call_args.kwargs["callback"]
            pcm = b"\x01\x00\x02\x00" * 40
            callback(pcm, 80, None, None)
            clip = recorder.stop()
            self.assertFalse(recorder.is_recording)
            stream.stop.assert_called_once()
            stream.close.assert_called_once()
            with wave.open(io.BytesIO(clip.wav_bytes), "rb") as wav:
                self.assertEqual(wav.getframerate(), 16000)
                self.assertEqual(wav.getnchannels(), 1)
                self.assertEqual(wav.readframes(80), pcm)
            self.assertEqual(clip.duration_seconds, 80 / 16000)
            recorder.start()
            empty_clip = recorder.stop()
            with wave.open(io.BytesIO(empty_clip.wav_bytes), "rb") as wav:
                self.assertEqual(wav.getnframes(), 0)
            self.assertEqual(empty_clip.duration_seconds, 0)

    def test_failed_stream_start_closes_device_and_allows_retry(self) -> None:
        stream = MagicMock()
        stream.start.side_effect = [RuntimeError("device busy"), None]
        with patch.dict(sys.modules, {"sounddevice": SimpleNamespace(RawInputStream=lambda **kw: stream)}):
            recorder = MicrophoneRecorder()
            with self.assertRaisesRegex(RuntimeError, "device busy"):
                recorder.start()
            stream.close.assert_called_once()
            self.assertFalse(recorder.is_recording)
            recorder.start()
            self.assertTrue(recorder.is_recording)
            recorder.stop()

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
