from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SELECTED_CONTROL_IDS = (
    "_ACFT_NAME",
    "MASTER_ARM_SW",
    "UFC_COMM1_DISPLAY",
    "UFC_COMM2_DISPLAY",
    "COMM1_FREQ",
    "COMM2_FREQ",
    "TIME_START_HIGH",
    "TIME_START_LOW",
    "TIME_MODEL_HIGH",
    "TIME_MODEL_LOW",
)


@dataclass(frozen=True)
class ControlOutput:
    identifier: str
    output_type: str
    address: int
    description: str = ""
    mask: int | None = None
    shift_by: int = 0
    max_value: int | None = None
    max_length: int | None = None


@dataclass(frozen=True)
class ReferenceLoadResult:
    reference_dir: Path | None
    controls: dict[str, ControlOutput]


def load_reference_data(reference_dirs: list[Path]) -> ReferenceLoadResult:
    for reference_dir in reference_dirs:
        controls = _load_controls_from_dir(reference_dir)
        if controls:
            return ReferenceLoadResult(reference_dir=reference_dir, controls=controls)
    return ReferenceLoadResult(reference_dir=None, controls={})


def _load_controls_from_dir(reference_dir: Path) -> dict[str, ControlOutput]:
    controls: dict[str, ControlOutput] = {}
    for file_name in ("MetadataStart.json", "CommonData.json", "FA-18C_hornet.json"):
        path = reference_dir / file_name
        if not path.exists():
            continue
        controls.update(_load_selected_controls(path))
    return controls


def _load_selected_controls(path: Path) -> dict[str, ControlOutput]:
    with path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)

    controls: dict[str, ControlOutput] = {}
    for control in _iter_controls(document):
        identifier = control.get("identifier")
        if identifier not in SELECTED_CONTROL_IDS:
            continue
        outputs = control.get("outputs") or []
        if not outputs:
            continue
        output = outputs[0]
        controls[identifier] = ControlOutput(
            identifier=identifier,
            output_type=str(output.get("type", "")),
            address=int(output["address"]),
            description=str(control.get("description", "")),
            mask=_optional_int(output.get("mask")),
            shift_by=int(output.get("shift_by", 0)),
            max_value=_optional_int(output.get("max_value")),
            max_length=_optional_int(output.get("max_length")),
        )
    return controls


def _iter_controls(document: Any) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    if not isinstance(document, dict):
        return controls

    for value in document.values():
        if isinstance(value, dict) and "identifier" in value:
            controls.append(value)
            continue
        if isinstance(value, dict):
            for nested in value.values():
                if isinstance(nested, dict) and "identifier" in nested:
                    controls.append(nested)
    return controls


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)
