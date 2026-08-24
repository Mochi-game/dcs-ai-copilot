from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.voice.audio import AudioClip
from dcs_ai_copilot.voice.transcriber import (
    FallbackTranscriber,
    TranscriptionResult,
    create_transcriber,
    friendly_transcription_error,
)


class FailingTranscriber:
    model = "primary"

    def transcribe(self, clip: AudioClip) -> TranscriptionResult:
        raise RuntimeError("primary failed")


class SuccessfulTranscriber:
    model = "fallback"

    def transcribe(self, clip: AudioClip) -> TranscriptionResult:
        return TranscriptionResult(text="target north 42 15.732", model=self.model)


class TranscriberTests(unittest.TestCase):
    def test_fallback_transcriber_uses_fallback_after_primary_error(self) -> None:
        transcriber = FallbackTranscriber(FailingTranscriber(), SuccessfulTranscriber())
        clip = AudioClip(wav_bytes=b"", sample_rate=16000, channels=1)

        result = transcriber.transcribe(clip)

        self.assertEqual(result.text, "target north 42 15.732")
        self.assertEqual(result.model, "fallback")

    def test_create_transcriber_can_describe_openai_to_gemini_fallback(self) -> None:
        transcriber = create_transcriber(
            provider="openai",
            fallback_provider="gemini",
            openai_model="gpt-4o-mini-transcribe",
            gemini_model="gemini-2.5-flash",
        )

        self.assertEqual(transcriber.model, "gpt-4o-mini-transcribe -> gemini-2.5-flash")

    def test_friendly_error_mentions_missing_gemini_key(self) -> None:
        self.assertIn(
            "GEMINI_API_KEY",
            friendly_transcription_error(RuntimeError("GEMINI_API_KEY is missing")),
        )


if __name__ == "__main__":
    unittest.main()
