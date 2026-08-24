from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dcs_ai_copilot.voice.parser import CoordinateParseError, parse_coordinate_message


class CoordinateParserTests(unittest.TestCase):
    def test_parses_target_coordinate_message(self) -> None:
        capture = parse_coordinate_message(
            "target north 42 15.732 east 041 38.219 elevation 428"
        )

        self.assertEqual(capture.kind, "target")
        self.assertEqual(capture.index, 1)
        self.assertEqual(capture.format_latitude(), "N42°15.732'")
        self.assertEqual(capture.format_longitude(), "E041°38.219'")
        self.assertEqual(capture.format_elevation(), "ELEV 428 FT")

    def test_rejects_invalid_minutes(self) -> None:
        with self.assertRaises(CoordinateParseError):
            parse_coordinate_message(
                "target north 42 60.000 east 041 38.219 elevation 428"
            )

    def test_parses_transcription_with_merged_coordinates(self) -> None:
        capture = parse_coordinate_message(
            "Morf 4215.732 east 041.38219. Elevation 428."
        )

        self.assertEqual(capture.kind, "target")
        self.assertEqual(capture.format_latitude(), "N42°15.732'")
        self.assertEqual(capture.format_longitude(), "E041°38.219'")
        self.assertEqual(capture.format_elevation(), "ELEV 428 FT")

    def test_parses_transcription_with_comma_split_merged_coordinates(self) -> None:
        capture = parse_coordinate_message(
            "Target, morph, 4215, 732, east, 041, 38219, elevation 428."
        )

        self.assertEqual(capture.kind, "target")
        self.assertEqual(capture.format_latitude(), "N42°15.732'")
        self.assertEqual(capture.format_longitude(), "E041°38.219'")
        self.assertEqual(capture.format_elevation(), "ELEV 428 FT")

    def test_parses_transcription_with_direction_adjectives_and_decimal_word(self) -> None:
        capture = parse_coordinate_message(
            "Target: Northern, North, 4215, decimal 732. Eastern, 041, decimal 38219. Elevation 428."
        )

        self.assertEqual(capture.kind, "target")
        self.assertEqual(capture.format_latitude(), "N42°15.732'")
        self.assertEqual(capture.format_longitude(), "E041°38.219'")
        self.assertEqual(capture.format_elevation(), "ELEV 428 FT")

    def test_reports_missing_elevation_number(self) -> None:
        with self.assertRaisesRegex(CoordinateParseError, "elevation number is missing"):
            parse_coordinate_message(
                "Target: Northern, North, 4215, decimal 732. Eastern, 041, decimal 38219. Elevation."
            )

    def test_parses_decimal_word_joined_to_coordinate(self) -> None:
        capture = parse_coordinate_message(
            "Target: North 4215.decimal 732. East 04138.decimal219. Elevation: 428 feet."
        )

        self.assertEqual(capture.kind, "target")
        self.assertEqual(capture.format_latitude(), "N42°15.732'")
        self.assertEqual(capture.format_longitude(), "E041°38.219'")
        self.assertEqual(capture.format_elevation(), "ELEV 428 FT")

    def test_parses_longitude_when_degrees_and_minutes_are_merged(self) -> None:
        capture = parse_coordinate_message(
            "target north 42 15.732 east 04138.219 elevation 428"
        )

        self.assertEqual(capture.format_longitude(), "E041°38.219'")


if __name__ == "__main__":
    unittest.main()
