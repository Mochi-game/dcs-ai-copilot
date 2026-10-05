from __future__ import annotations

import logging
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from dcs_ai_copilot.dcs_bios.discovery import (
    find_dcs_bios_installations,
    find_reference_dirs,
)
from dcs_ai_copilot.dcs_bios.protocol import DcsBiosMemory
from dcs_ai_copilot.dcs_bios.reference import (
    SELECTED_CONTROL_IDS,
    ControlOutput,
    load_reference_data,
)
from dcs_ai_copilot.kneeboard.state import KneeboardState


@dataclass(frozen=True)
class DcsBiosReaderConfig:
    enabled: bool
    multicast_group: str
    port: int
    reference_dir: Path | None = None


class DcsBiosReader:
    def __init__(
        self,
        config: DcsBiosReaderConfig,
        state: KneeboardState,
        logger: logging.Logger,
    ) -> None:
        self._config = config
        self._state = state
        self._logger = logger
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="dcs-bios-readonly-listener",
            daemon=True,
        )
        self._memory = DcsBiosMemory()
        self._controls: dict[str, ControlOutput] = {}
        self._reference_dir: Path | None = None
        self._last_reference_check = 0.0

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        if not self._config.enabled:
            self._state.update_dcs_bios(
                status="DISABLED",
                installed=bool(find_dcs_bios_installations()),
                reference_loaded=False,
            )
            return

        self._refresh_reference(force=True)
        sock = self._open_socket()
        if sock is None:
            self._state.update_dcs_bios(status="SOCKET ERROR")
            return

        self._state.update_dcs_bios(status="LISTENING", listening=True)
        with sock:
            while not self._stop_event.is_set():
                self._refresh_reference()
                try:
                    packet, _ = sock.recvfrom(4096)
                except TimeoutError:
                    self._mark_timeout_if_needed()
                    continue
                except OSError as exc:
                    self._logger.warning("DCS-BIOS socket error: %s", exc)
                    self._state.update_dcs_bios(status="SOCKET ERROR")
                    return

                if self._memory.apply_packet(packet):
                    self._publish_values()

    def _open_socket(self) -> socket.socket | None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self._config.port))
            membership = socket.inet_aton(self._config.multicast_group) + socket.inet_aton(
                "127.0.0.1"
            )
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
            sock.settimeout(0.5)
            return sock
        except OSError as exc:
            self._logger.warning("Could not open DCS-BIOS read-only socket: %s", exc)
            return None

    def _refresh_reference(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_reference_check < 10:
            return
        self._last_reference_check = now

        installations = find_dcs_bios_installations()
        reference_dirs = find_reference_dirs(self._config.reference_dir)
        result = load_reference_data(reference_dirs)
        if result.controls:
            self._controls = result.controls
            self._reference_dir = result.reference_dir

        missing = [
            control_id
            for control_id in SELECTED_CONTROL_IDS
            if control_id not in self._controls
        ]
        self._state.update_dcs_bios(
            installed=bool(installations),
            install_path=str(installations[0]) if installations else "",
            reference_loaded=bool(self._controls),
            reference_dir=str(self._reference_dir) if self._reference_dir else "",
            missing_controls=missing,
        )

    def _publish_values(self) -> None:
        values: dict[str, dict[str, object]] = {}
        for identifier, output in self._controls.items():
            decoded = self._memory.read_control(output)
            if decoded is None:
                continue
            values[identifier] = {
                "raw": decoded.raw,
                "display": decoded.display,
            }

        aircraft = str(values.get("_ACFT_NAME", {}).get("display", "")).strip()
        self._publish_mission_time(values)
        self._state.update_dcs_bios(
            status="CONNECTED" if aircraft else "RECEIVING",
            listening=True,
            last_packet_time=time.time(),
            aircraft=aircraft,
            is_fa18c=aircraft == "FA-18C_hornet",
            values=values,
        )

    def _publish_mission_time(self, values: dict[str, dict[str, object]]) -> None:
        words = [values.get(name, {}).get("raw") for name in (
            "TIME_START_HIGH", "TIME_START_LOW", "TIME_MODEL_HIGH", "TIME_MODEL_LOW")]
        if not all(isinstance(word, int) for word in words):
            return
        start = words[0] * 65536 + words[1]
        model = words[2] * 65536 + words[3]
        # All zero before DCS has sent a frame from a running mission.
        if start or model:
            self._state.mission_clock.update(start, model)

    def _mark_timeout_if_needed(self) -> None:
        snapshot = self._state.snapshot().dcs_bios
        last_packet = float(snapshot.get("last_packet_time") or 0)
        if last_packet <= 0:
            status = "WAITING FOR DCS-BIOS"
        elif time.time() - last_packet > 3:
            status = "NO RECENT DATA"
        else:
            return
        self._state.update_dcs_bios(status=status, listening=True)
