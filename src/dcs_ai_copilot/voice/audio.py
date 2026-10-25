from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable


@dataclass(frozen=True)
class AudioClip:
    wav_bytes: bytes
    sample_rate: int
    channels: int

    @property
    def duration_seconds(self) -> float:
        try:
            with wave.open(io.BytesIO(self.wav_bytes), "rb") as wav:
                return wav.getnframes() / wav.getframerate()
        except (wave.Error, EOFError, ZeroDivisionError):
            return 0.0


@dataclass(frozen=True)
class AudioInputDevice:
    index: int
    name: str
    max_input_channels: int
    default_sample_rate: float
    is_default: bool = False


class MicrophoneRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, input_device: str = "") -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._input_device = _parse_input_device(input_device)
        self._lock = Lock()
        self._frames: list[bytes] = []
        self._stream = None

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def describe_input(self) -> str:
        import sounddevice as sd

        device = sd.query_devices(self._input_device, "input")
        host = sd.query_hostapis(device["hostapi"])["name"]
        return f"{device['name']} ({host})"

    def validate_input(self) -> None:
        import sounddevice as sd

        sd.check_input_settings(
            device=self._input_device, samplerate=self._sample_rate,
            channels=self._channels, dtype="int16",
        )

    def start(self) -> None:
        if self._stream is not None:
            return
        import sounddevice as sd

        with self._lock:
            self._frames = []

        stream = sd.RawInputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="int16",
            device=self._input_device,
            callback=self._on_audio,
        )
        try:
            stream.start()
        except Exception:
            stream.close()
            raise
        self._stream = stream

    def stop(self) -> AudioClip:
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

        with self._lock:
            pcm = b"".join(self._frames)
            self._frames = []

        return AudioClip(
            wav_bytes=_pcm_to_wav(pcm, self._sample_rate, self._channels),
            sample_rate=self._sample_rate,
            channels=self._channels,
        )

    def _on_audio(self, indata, frames, time, status) -> None:
        del frames, time, status
        with self._lock:
            self._frames.append(bytes(indata))


def _pcm_to_wav(pcm: bytes, sample_rate: int, channels: int) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return output.getvalue()


def _parse_input_device(value: str) -> int | str | None:
    value = value.strip()
    if not value or value.lower() in {"default", "auto"}:
        return None
    try:
        return int(value)
    except ValueError:
        return value


def microphone_choices() -> list[dict[str, str]]:
    """Enumerate on demand, without opening streams or changing audio defaults."""
    import sounddevice as sd

    hosts = sd.query_hostapis()
    choices = [{"value": "", "label": "Windows default microphone"}]
    seen = set()
    for device in sd.query_devices():
        if device["max_input_channels"] <= 0:
            continue
        name = f"{device['name']}, {hosts[device['hostapi']]['name']}"
        if name not in seen:
            choices.append({"value": name, "label": name})
            seen.add(name)
    return choices


def list_audio_input_devices(
    query_devices: Callable[[], Any] | None = None,
    default_device: object | None = None,
) -> list[AudioInputDevice]:
    if query_devices is None or default_device is None:
        import sounddevice as sd

        if query_devices is None:
            query_devices = sd.query_devices
        if default_device is None:
            default_device = sd.default.device

    default_input = _default_input_index(default_device)
    devices: list[AudioInputDevice] = []
    for index, raw_device in enumerate(query_devices()):
        channels = int(_device_value(raw_device, "max_input_channels", 0) or 0)
        if channels <= 0:
            continue
        devices.append(
            AudioInputDevice(
                index=index,
                name=str(_device_value(raw_device, "name", f"Device {index}")),
                max_input_channels=channels,
                default_sample_rate=float(_device_value(raw_device, "default_samplerate", 0.0) or 0.0),
                is_default=index == default_input,
            )
        )
    return devices


def run_audio_diagnostics(print_func: Callable[[str], None] = print) -> int:
    print_func("DCS AI Copilot audio diagnostics")
    print_func("")
    try:
        devices = list_audio_input_devices()
    except Exception as exc:
        print_func(f"Could not query audio devices: {exc}")
        print_func("Check Windows microphone privacy settings and sounddevice installation.")
        return 1

    if not devices:
        print_func("No microphone/input devices found.")
        print_func("Check Windows Settings > Privacy & security > Microphone.")
        return 1

    print_func("Input devices:")
    for device in devices:
        marker = " DEFAULT" if device.is_default else ""
        sample_rate = f"{device.default_sample_rate:.0f} Hz" if device.default_sample_rate else "unknown Hz"
        print_func(
            f"[{device.index}] {device.name}{marker} "
            f"inputs={device.max_input_channels} default_rate={sample_rate}"
        )
    print_func("")
    print_func("Use the index or exact name in config.ini [voice] input_device if the default microphone is wrong.")
    return 0


def _default_input_index(default_device: object) -> int | None:
    value = default_device
    if not isinstance(default_device, (str, int)):
        try:
            # sounddevice returns an indexable pair, not a list/tuple.
            value = default_device[0]
        except (TypeError, IndexError, KeyError):
            return None
    try:
        index = int(value)
    except (TypeError, ValueError):
        return None
    return index if index >= 0 else None


def _device_value(device: object, key: str, default: object) -> object:
    if isinstance(device, dict):
        return device.get(key, default)
    return getattr(device, key, default)
