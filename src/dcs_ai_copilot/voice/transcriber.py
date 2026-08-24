from __future__ import annotations

import io
import os
from dataclasses import dataclass

from dcs_ai_copilot.voice.audio import AudioClip


TRANSCRIPTION_PROMPT = (
    "Transcribe short DCS World F/A-18C radio-style coordinate calls. "
    "Preserve words and numbers such as target, bullseye, tanker, waypoint, "
    "north, south, east, west, elevation, feet, and decimal minutes."
)

GEMINI_TRANSCRIPTION_PROMPT = (
    f"{TRANSCRIPTION_PROMPT} Return only the transcript text. "
    "Do not explain, summarize, add punctuation advice, or format as a list."
)


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    model: str


class OpenAITranscriber:
    def __init__(self, model: str = "gpt-4o-mini-transcribe") -> None:
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def transcribe(self, clip: AudioClip) -> TranscriptionResult:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")

        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        audio_file = io.BytesIO(clip.wav_bytes)
        audio_file.name = "ptt.wav"
        response = client.audio.transcriptions.create(
            model=self._model,
            file=audio_file,
            prompt=TRANSCRIPTION_PROMPT,
        )
        text = getattr(response, "text", "")
        return TranscriptionResult(text=str(text).strip(), model=self._model)


class GeminiTranscriber:
    def __init__(self, model: str = "gemini-2.5-flash") -> None:
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def transcribe(self, clip: AudioClip) -> TranscriptionResult:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=self._model,
            contents=[
                GEMINI_TRANSCRIPTION_PROMPT,
                types.Part.from_bytes(data=clip.wav_bytes, mime_type="audio/wav"),
            ],
        )
        text = getattr(response, "text", "")
        return TranscriptionResult(text=str(text).strip(), model=self._model)


class FallbackTranscriber:
    def __init__(self, primary, fallback) -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def model(self) -> str:
        return f"{self._primary.model} -> {self._fallback.model}"

    def transcribe(self, clip: AudioClip) -> TranscriptionResult:
        try:
            return self._primary.transcribe(clip)
        except Exception as primary_exc:
            try:
                return self._fallback.transcribe(clip)
            except Exception as fallback_exc:
                raise RuntimeError(
                    "Primary transcription failed: "
                    f"{friendly_transcription_error(primary_exc)}; "
                    "fallback transcription failed: "
                    f"{friendly_transcription_error(fallback_exc)}"
                ) from fallback_exc


def create_transcriber(
    provider: str = "openai",
    fallback_provider: str = "",
    openai_model: str = "gpt-4o-mini-transcribe",
    gemini_model: str = "gemini-2.5-flash",
):
    primary = _create_provider_transcriber(provider, openai_model, gemini_model)
    fallback_name = fallback_provider.strip().lower()
    if not fallback_name or fallback_name in {"none", "off", provider.strip().lower()}:
        return primary
    fallback = _create_provider_transcriber(fallback_provider, openai_model, gemini_model)
    return FallbackTranscriber(primary, fallback)


def _create_provider_transcriber(provider: str, openai_model: str, gemini_model: str):
    normalized = provider.strip().lower()
    if normalized == "openai":
        return OpenAITranscriber(openai_model)
    if normalized == "gemini":
        return GeminiTranscriber(gemini_model)
    raise ValueError(f"Unsupported transcription provider: {provider}")


def friendly_transcription_error(exc: Exception) -> str:
    text = str(exc)
    if "insufficient_quota" in text or "exceeded your current quota" in text:
        return (
            "OpenAI API quota/billing saknas eller är slut. "
            "Kontrollera billing/credits för API-nyckelns OpenAI-projekt."
        )
    if "OPENAI_API_KEY is missing" in text:
        return "OPENAI_API_KEY saknas i .env eller miljön."
    if "GEMINI_API_KEY is missing" in text:
        return "GEMINI_API_KEY saknas i .env eller miljön."
    return text
