from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.dcs_bios.protocol import SYNC_SEQUENCE, DcsBiosMemory
from dcs_ai_copilot.dcs_bios.reference import ControlOutput, load_reference_data


class DcsBiosReferenceTests(unittest.TestCase):
    def test_loads_selected_controls_from_reference_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reference_dir = Path(temp_dir)
            (reference_dir / "MetadataStart.json").write_text(
                json.dumps(
                    {
                        "Metadata": {
                            "_ACFT_NAME": {
                                "identifier": "_ACFT_NAME",
                                "description": "Aircraft Name",
                                "outputs": [
                                    {
                                        "type": "string",
                                        "address": 0x0000,
                                        "max_length": 24,
                                    }
                                ],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (reference_dir / "FA-18C_hornet.json").write_text(
                json.dumps(
                    {
                        "Master Arm Panel": {
                            "MASTER_ARM_SW": {
                                "identifier": "MASTER_ARM_SW",
                                "description": "Master Arm Switch, ARM/SAFE",
                                "outputs": [
                                    {
                                        "type": "integer",
                                        "address": 0x1000,
                                        "mask": 0x0001,
                                        "shift_by": 0,
                                        "max_value": 1,
                                    }
                                ],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            result = load_reference_data([reference_dir])

        self.assertEqual(result.reference_dir, reference_dir)
        self.assertIn("_ACFT_NAME", result.controls)
        self.assertIn("MASTER_ARM_SW", result.controls)
        self.assertEqual(result.controls["MASTER_ARM_SW"].address, 0x1000)


class DcsBiosProtocolTests(unittest.TestCase):
    def test_applies_integer_and_string_writes(self) -> None:
        memory = DcsBiosMemory()
        packet = (
            SYNC_SEQUENCE
            + (0x1000).to_bytes(2, "little")
            + (2).to_bytes(2, "little")
            + (1).to_bytes(2, "little")
            + (0x2000).to_bytes(2, "little")
            + (12).to_bytes(2, "little")
            + b"FA-18C\x00\x00\x00\x00\x00\x00"
        )

        self.assertTrue(memory.apply_packet(packet))
        master_arm = memory.read_control(
            ControlOutput(
                identifier="MASTER_ARM_SW",
                output_type="integer",
                address=0x1000,
                mask=0x0001,
            )
        )
        aircraft = memory.read_control(
            ControlOutput(
                identifier="_ACFT_NAME",
                output_type="string",
                address=0x2000,
                max_length=12,
            )
        )

        self.assertIsNotNone(master_arm)
        self.assertEqual(master_arm.display, "ARM")
        self.assertIsNotNone(aircraft)
        self.assertEqual(aircraft.display, "FA-18C")

    def test_formats_comm_frequency(self) -> None:
        memory = DcsBiosMemory()
        packet = (
            (0x3000).to_bytes(2, "little")
            + (2).to_bytes(2, "little")
            + (30500).to_bytes(2, "little")
        )

        self.assertTrue(memory.apply_packet(packet))
        value = memory.read_control(
            ControlOutput(
                identifier="COMM1_FREQ",
                output_type="integer",
                address=0x3000,
                mask=0xFFFF,
            )
        )

        self.assertIsNotNone(value)
        self.assertEqual(value.display, "305.00 MHz")


if __name__ == "__main__":
    unittest.main()
