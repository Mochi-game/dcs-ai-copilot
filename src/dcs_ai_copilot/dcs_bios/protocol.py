from __future__ import annotations

from dataclasses import dataclass

from dcs_ai_copilot.dcs_bios.reference import ControlOutput


SYNC_SEQUENCE = b"\x55\x55\x55\x55"


@dataclass(frozen=True)
class DecodedValue:
    identifier: str
    raw: int | str
    display: str


class DcsBiosMemory:
    def __init__(self, size: int = 65536) -> None:
        self._data = bytearray(size)

    def apply_packet(self, packet: bytes) -> bool:
        index = 0
        changed = False
        while index < len(packet):
            if packet[index : index + 4] == SYNC_SEQUENCE:
                index += 4
                continue
            if index + 4 > len(packet):
                break

            address = int.from_bytes(packet[index : index + 2], "little")
            length = int.from_bytes(packet[index + 2 : index + 4], "little")
            index += 4
            if length <= 0 or index + length > len(packet):
                break
            if address + length <= len(self._data):
                self._data[address : address + length] = packet[index : index + length]
                changed = True
            index += length
        return changed

    def read_control(self, output: ControlOutput) -> DecodedValue | None:
        if output.output_type == "integer":
            return self._read_integer(output)
        if output.output_type == "string":
            return self._read_string(output)
        return None

    def _read_integer(self, output: ControlOutput) -> DecodedValue | None:
        if output.address + 2 > len(self._data):
            return None
        word = int.from_bytes(self._data[output.address : output.address + 2], "little")
        mask = output.mask if output.mask is not None else 0xFFFF
        value = (word & mask) >> output.shift_by
        return DecodedValue(
            identifier=output.identifier,
            raw=value,
            display=_format_integer(output.identifier, value),
        )

    def _read_string(self, output: ControlOutput) -> DecodedValue | None:
        length = output.max_length or 0
        if length <= 0 or output.address + length > len(self._data):
            return None
        raw_bytes = bytes(self._data[output.address : output.address + length])
        value = raw_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()
        return DecodedValue(
            identifier=output.identifier,
            raw=value,
            display=value or "-",
        )


def _format_integer(identifier: str, value: int) -> str:
    if identifier == "MASTER_ARM_SW":
        if value == 0:
            return "SAFE"
        if value == 1:
            return "ARM"
    if identifier in {"COMM1_FREQ", "COMM2_FREQ"}:
        if value <= 0:
            return "-"
        return f"{value / 100:.2f} MHz"
    return str(value)
