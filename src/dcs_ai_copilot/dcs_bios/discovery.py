from __future__ import annotations

from pathlib import Path


def find_dcs_bios_installations(home: Path | None = None) -> list[Path]:
    root = home or Path.home()
    saved_games = root / "Saved Games"
    candidates = [
        saved_games / "DCS" / "Scripts" / "DCS-BIOS",
        saved_games / "DCS.openbeta" / "Scripts" / "DCS-BIOS",
        saved_games / "DCS World" / "Scripts" / "DCS-BIOS",
        saved_games / "DCS World OpenBeta" / "Scripts" / "DCS-BIOS",
    ]
    return [path for path in candidates if path.exists()]


def find_reference_dirs(configured_dir: Path | None = None) -> list[Path]:
    dirs: list[Path] = []
    if configured_dir is not None:
        dirs.append(configured_dir)

    for install in find_dcs_bios_installations():
        dirs.append(install / "doc" / "json")

    seen: set[Path] = set()
    existing: list[Path] = []
    for path in dirs:
        resolved = path.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            existing.append(resolved)
    return existing
