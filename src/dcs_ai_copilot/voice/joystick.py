from __future__ import annotations

import os
import re
import sys
import ctypes
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class JoystickDeviceInfo:
    index: int
    name: str
    guid: str
    axes: int
    buttons: int
    hats: int


@dataclass(frozen=True)
class WinmmJoystickDeviceInfo:
    device_id: int
    name: str
    axes: int
    buttons: int
    max_buttons: int
    buttons_mask: int


def normalize_joystick_button(value: str | int) -> int:
    if isinstance(value, int):
        if value < 0:
            raise ValueError("joystick button must be 0 or greater")
        return value

    text = value.strip().lower()
    if text.isdigit():
        return int(text)

    match = re.fullmatch(r"(?:joy_)?btn_?(\d+)", text)
    if not match:
        raise ValueError(f"unsupported joystick button value: {value}")

    direct_input_number = int(match.group(1))
    if direct_input_number <= 0:
        raise ValueError("DirectInput button names start at 1")
    return direct_input_number - 1


def list_joystick_devices() -> list[JoystickDeviceInfo]:
    pygame = _load_pygame()
    pygame.joystick.init()
    devices: list[JoystickDeviceInfo] = []
    for index in range(pygame.joystick.get_count()):
        joystick = pygame.joystick.Joystick(index)
        joystick.init()
        devices.append(
            JoystickDeviceInfo(
                index=index,
                name=joystick.get_name(),
                guid=joystick.get_guid(),
                axes=joystick.get_numaxes(),
                buttons=joystick.get_numbuttons(),
                hats=joystick.get_numhats(),
            )
        )
    return devices


def is_winmm_button_pressed(buttons_mask: int, button: str | int) -> bool:
    normalized_button = normalize_joystick_button(button)
    return bool(buttons_mask & (1 << normalized_button))


def list_winmm_joystick_devices() -> list[WinmmJoystickDeviceInfo]:
    if sys.platform != "win32":
        return []

    winmm = ctypes.WinDLL("winmm")
    device_count = int(winmm.joyGetNumDevs())
    devices: list[WinmmJoystickDeviceInfo] = []
    for device_id in range(device_count):
        caps = _JOYCAPSW()
        caps_result = winmm.joyGetDevCapsW(
            device_id,
            ctypes.byref(caps),
            ctypes.sizeof(caps),
        )
        if caps_result != 0:
            continue

        state = _JOYINFOEX()
        state.dwSize = ctypes.sizeof(_JOYINFOEX)
        state.dwFlags = _JOY_RETURNALL
        state_result = winmm.joyGetPosEx(device_id, ctypes.byref(state))
        if state_result != 0:
            continue

        devices.append(
            WinmmJoystickDeviceInfo(
                device_id=device_id,
                name=caps.szPname,
                axes=int(caps.wNumAxes),
                buttons=int(caps.wNumButtons),
                max_buttons=int(caps.wMaxButtons),
                buttons_mask=int(state.dwButtons),
            )
        )
    return devices


class JoystickPttListener:
    def __init__(
        self,
        device_name: str,
        button: str | int,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        on_status: Callable[[str, str], None],
        poll_interval_seconds: float = 0.01,
    ) -> None:
        self._device_name = device_name
        self._button = normalize_joystick_button(button)
        self._on_press = on_press
        self._on_release = on_release
        self._on_status = on_status
        self._poll_interval_seconds = max(0.005, poll_interval_seconds)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="joystick-ptt-listener",
            daemon=True,
        )

    @property
    def button(self) -> int:
        return self._button

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        try:
            pygame = _load_pygame()
            pygame.joystick.init()
        except Exception as exc:
            self._on_status("JOYSTICK ERROR", str(exc))
            return

        was_pressed = False
        joystick = None
        while not self._stop_event.is_set():
            if joystick is None:
                joystick = self._find_joystick(pygame)
                if joystick is None:
                    self._on_status(
                        "JOYSTICK NOT FOUND",
                        f"Could not find joystick matching: {self._device_name}",
                    )
                    time.sleep(2)
                    continue
                self._on_status("JOYSTICK READY", joystick.get_name())

            try:
                pygame.event.pump()
                is_pressed = bool(joystick.get_button(self._button))
            except Exception as exc:
                joystick = None
                was_pressed = False
                self._on_status("JOYSTICK ERROR", str(exc))
                time.sleep(1)
                continue

            if is_pressed and not was_pressed:
                self._on_press()
            elif was_pressed and not is_pressed:
                self._on_release()
            was_pressed = is_pressed
            time.sleep(self._poll_interval_seconds)

        if was_pressed:
            self._on_release()

    def _find_joystick(self, pygame):
        targets = [
            target.strip().lower()
            for target in re.split(r"[|;]", self._device_name)
            if target.strip()
        ]
        for index in range(pygame.joystick.get_count()):
            joystick = pygame.joystick.Joystick(index)
            joystick.init()
            joystick_name = joystick.get_name().lower()
            if any(target in joystick_name for target in targets):
                if self._button >= joystick.get_numbuttons():
                    self._on_status(
                        "JOYSTICK ERROR",
                        f"{joystick.get_name()} has only {joystick.get_numbuttons()} buttons",
                    )
                    return None
                return joystick
        return None


class WinmmJoystickPttListener:
    def __init__(
        self,
        device_name: str,
        device_id: str,
        button: str | int,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
        on_status: Callable[[str, str], None],
        poll_interval_seconds: float = 0.01,
    ) -> None:
        self._device_name = device_name
        self._device_id = device_id
        self._button = normalize_joystick_button(button)
        self._on_press = on_press
        self._on_release = on_release
        self._on_status = on_status
        self._poll_interval_seconds = max(0.005, poll_interval_seconds)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="winmm-joystick-ptt-listener",
            daemon=True,
        )

    @property
    def button(self) -> int:
        return self._button

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        if sys.platform != "win32":
            self._on_status("JOYSTICK ERROR", "WinMM joystick input is Windows-only")
            return

        try:
            winmm = ctypes.WinDLL("winmm")
        except Exception as exc:
            self._on_status("JOYSTICK ERROR", str(exc))
            return

        was_pressed = False
        device: WinmmJoystickDeviceInfo | None = None
        while not self._stop_event.is_set():
            if device is None:
                device = self._find_device()
                if device is None:
                    self._on_status(
                        "JOYSTICK NOT FOUND",
                        f"Could not find WinMM joystick matching: {self._device_name}",
                    )
                    time.sleep(2)
                    continue
                self._on_status(
                    "JOYSTICK READY",
                    (
                        f"WinMM device {device.device_id}: {device.name} "
                        f"axes={device.axes} buttons={device.buttons}"
                    ),
                )

            try:
                buttons_mask = _read_winmm_buttons(winmm, device.device_id)
                is_pressed = is_winmm_button_pressed(buttons_mask, self._button)
            except Exception as exc:
                device = None
                was_pressed = False
                self._on_status("JOYSTICK ERROR", str(exc))
                time.sleep(1)
                continue

            if is_pressed and not was_pressed:
                self._on_press()
            elif was_pressed and not is_pressed:
                self._on_release()
            was_pressed = is_pressed
            time.sleep(self._poll_interval_seconds)

        if was_pressed:
            self._on_release()

    def _find_device(self) -> WinmmJoystickDeviceInfo | None:
        devices = list_winmm_joystick_devices()
        return self._select_from_devices(devices)

    def _select_from_devices(
        self,
        devices: list[WinmmJoystickDeviceInfo],
    ) -> WinmmJoystickDeviceInfo | None:
        configured_id = self._device_id.strip().lower()
        if configured_id and configured_id != "auto":
            try:
                device_id = int(configured_id)
            except ValueError:
                return None
            return _find_winmm_by_id(devices, device_id, self._button)

        targets = _target_names(self._device_name)
        for device in devices:
            if any(target in device.name.lower() for target in targets):
                if self._button < device.buttons:
                    return device

        if any("takeoff panel" in target or "f18 takeoff" in target for target in targets):
            candidates = [
                device
                for device in devices
                if device.axes == 0 and self._button < device.buttons
            ]
            if len(candidates) == 1:
                return candidates[0]

        return None


def run_joystick_diagnostics(include_axes: bool = False) -> int:
    pygame = _load_pygame()
    pygame.init()
    pygame.joystick.init()
    joysticks = [pygame.joystick.Joystick(index) for index in range(pygame.joystick.get_count())]
    for joystick in joysticks:
        joystick.init()
    winmm_devices = list_winmm_joystick_devices()

    print("Joystick diagnostics")
    print("Press joystick buttons to see button numbers. Press Ctrl+C to stop.")
    if not include_axes:
        print("Axis and hat movement is hidden. Use --diagnose-joystick-axes to show it.")
    print()
    if not joysticks and not winmm_devices:
        print("No joystick devices found.")
        return 1

    print("Pygame devices:")
    for joystick in joysticks:
        print(f"[{joystick.get_id()}] {joystick.get_name()}")
        print(f"    GUID: {joystick.get_guid()}")
        print(
            f"    axes={joystick.get_numaxes()} buttons={joystick.get_numbuttons()} hats={joystick.get_numhats()}"
        )
    print()
    print("WinMM devices:")
    if winmm_devices:
        for device in winmm_devices:
            print(f"[{device.device_id}] {device.name}")
            print(
                f"    axes={device.axes} buttons={device.buttons} max_buttons={device.max_buttons} "
                f"mask=0x{device.buttons_mask:08x}"
            )
    else:
        print("No active WinMM joystick devices found.")
    print()
    last_buttons = {
        joystick.get_id(): [
            bool(joystick.get_button(button))
            for button in range(joystick.get_numbuttons())
        ]
        for joystick in joysticks
    }
    last_axes = {
        joystick.get_id(): [
            round(float(joystick.get_axis(axis)), 3)
            for axis in range(joystick.get_numaxes())
        ]
        for joystick in joysticks
    }
    last_hats = {
        joystick.get_id(): [
            joystick.get_hat(hat)
            for hat in range(joystick.get_numhats())
        ]
        for joystick in joysticks
    }
    last_winmm_buttons = {
        device.device_id: device.buttons_mask
        for device in winmm_devices
    }
    winmm = ctypes.WinDLL("winmm") if sys.platform == "win32" else None

    try:
        while True:
            pygame.event.pump()
            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN:
                    joystick = pygame.joystick.Joystick(event.joy)
                    print(f"PYGAME DOWN device={event.joy} name={joystick.get_name()} button={event.button}")
                elif event.type == pygame.JOYBUTTONUP:
                    joystick = pygame.joystick.Joystick(event.joy)
                    print(f"PYGAME UP   device={event.joy} name={joystick.get_name()} button={event.button}")
                elif include_axes and event.type == pygame.JOYAXISMOTION:
                    joystick = pygame.joystick.Joystick(event.joy)
                    print(
                        f"PYGAME AXIS device={event.joy} name={joystick.get_name()} axis={event.axis} value={event.value:.3f}"
                    )
                elif include_axes and event.type == pygame.JOYHATMOTION:
                    joystick = pygame.joystick.Joystick(event.joy)
                    print(f"PYGAME HAT  device={event.joy} name={joystick.get_name()} hat={event.hat} value={event.value}")

            for joystick in joysticks:
                joystick_id = joystick.get_id()
                for button in range(joystick.get_numbuttons()):
                    current = bool(joystick.get_button(button))
                    if current != last_buttons[joystick_id][button]:
                        state = "DOWN" if current else "UP"
                        print(f"PYGAME POLL {state} device={joystick_id} name={joystick.get_name()} button={button}")
                        last_buttons[joystick_id][button] = current

                if include_axes:
                    for axis in range(joystick.get_numaxes()):
                        current_axis = round(float(joystick.get_axis(axis)), 3)
                        if abs(current_axis - last_axes[joystick_id][axis]) >= 0.1:
                            print(
                                f"PYGAME POLL AXIS device={joystick_id} name={joystick.get_name()} axis={axis} value={current_axis:.3f}"
                            )
                            last_axes[joystick_id][axis] = current_axis

                    for hat in range(joystick.get_numhats()):
                        current_hat = joystick.get_hat(hat)
                        if current_hat != last_hats[joystick_id][hat]:
                            print(f"PYGAME POLL HAT  device={joystick_id} name={joystick.get_name()} hat={hat} value={current_hat}")
                            last_hats[joystick_id][hat] = current_hat

            if winmm is not None:
                for device in list_winmm_joystick_devices():
                    previous_mask = last_winmm_buttons.get(device.device_id, 0)
                    current_mask = _read_winmm_buttons(winmm, device.device_id)
                    changed = previous_mask ^ current_mask
                    if changed:
                        for button in range(device.max_buttons):
                            if changed & (1 << button):
                                state = "DOWN" if current_mask & (1 << button) else "UP"
                                print(
                                    f"WINMM {state} device={device.device_id} name={device.name} "
                                    f"button={button} mask=0x{current_mask:08x}"
                                )
                        last_winmm_buttons[device.device_id] = current_mask
            time.sleep(0.01)
    except KeyboardInterrupt:
        print()
        print("Joystick diagnostics stopped.")
        return 0


def _load_pygame():
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
    import pygame

    return pygame


def _target_names(device_name: str) -> list[str]:
    return [
        target.strip().lower()
        for target in re.split(r"[|;]", device_name)
        if target.strip()
    ]


def _find_winmm_by_id(
    devices: list[WinmmJoystickDeviceInfo],
    device_id: int,
    button: int,
) -> WinmmJoystickDeviceInfo | None:
    for device in devices:
        if device.device_id == device_id and button < device.buttons:
            return device
    return None


def _read_winmm_buttons(winmm, device_id: int) -> int:
    state = _JOYINFOEX()
    state.dwSize = ctypes.sizeof(_JOYINFOEX)
    state.dwFlags = _JOY_RETURNBUTTONS
    result = winmm.joyGetPosEx(device_id, ctypes.byref(state))
    if result != 0:
        raise OSError(f"joyGetPosEx failed for device {device_id}: {result}")
    return int(state.dwButtons)


_JOY_RETURNBUTTONS = 0x00000080
_JOY_RETURNALL = 0x000000FF
_MAXPNAMELEN = 32
_MAX_JOYSTICKOEMVXDNAME = 260


class _JOYINFOEX(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("dwFlags", ctypes.c_uint32),
        ("dwXpos", ctypes.c_uint32),
        ("dwYpos", ctypes.c_uint32),
        ("dwZpos", ctypes.c_uint32),
        ("dwRpos", ctypes.c_uint32),
        ("dwUpos", ctypes.c_uint32),
        ("dwVpos", ctypes.c_uint32),
        ("dwButtons", ctypes.c_uint32),
        ("dwButtonNumber", ctypes.c_uint32),
        ("dwPOV", ctypes.c_uint32),
        ("dwReserved1", ctypes.c_uint32),
        ("dwReserved2", ctypes.c_uint32),
    ]


class _JOYCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.c_uint16),
        ("wPid", ctypes.c_uint16),
        ("szPname", ctypes.c_wchar * _MAXPNAMELEN),
        ("wXmin", ctypes.c_uint32),
        ("wXmax", ctypes.c_uint32),
        ("wYmin", ctypes.c_uint32),
        ("wYmax", ctypes.c_uint32),
        ("wZmin", ctypes.c_uint32),
        ("wZmax", ctypes.c_uint32),
        ("wNumButtons", ctypes.c_uint32),
        ("wPeriodMin", ctypes.c_uint32),
        ("wPeriodMax", ctypes.c_uint32),
        ("wRmin", ctypes.c_uint32),
        ("wRmax", ctypes.c_uint32),
        ("wUmin", ctypes.c_uint32),
        ("wUmax", ctypes.c_uint32),
        ("wVmin", ctypes.c_uint32),
        ("wVmax", ctypes.c_uint32),
        ("wCaps", ctypes.c_uint32),
        ("wMaxAxes", ctypes.c_uint32),
        ("wNumAxes", ctypes.c_uint32),
        ("wMaxButtons", ctypes.c_uint32),
        ("szRegKey", ctypes.c_wchar * _MAXPNAMELEN),
        ("szOEMVxD", ctypes.c_wchar * _MAX_JOYSTICKOEMVXDNAME),
    ]
