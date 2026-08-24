from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dcs_ai_copilot.setup.maintenance import default_dcs_saved_games_path


DCS_BIOS_RELEASES_URL = "https://github.com/DCS-Skunkworks/dcs-bios/releases/latest"
DCS_BIOS_USER_GUIDE_URL = (
    "https://github.com/DCS-Skunkworks/dcs-bios/blob/main/Scripts/DCS-BIOS/doc/userguide.adoc"
)
EXPORT_LUA_LINE = r'dofile(lfs.writedir() .. [[Scripts\DCS-BIOS\BIOS.lua]])'


@dataclass(frozen=True)
class DcsBiosSetupStatus:
    saved_games_path: Path
    scripts_dir: Path
    dcs_bios_dir: Path
    reference_json_dir: Path
    export_lua_file: Path
    scripts_dir_exists: bool
    dcs_bios_dir_exists: bool
    reference_json_dir_exists: bool
    export_lua_exists: bool
    export_lua_mentions_dcs_bios: bool


def inspect_dcs_bios_setup(saved_games_path: Path | None = None) -> DcsBiosSetupStatus:
    saved_games = (saved_games_path or default_dcs_saved_games_path()).expanduser()
    scripts_dir = saved_games / "Scripts"
    dcs_bios_dir = scripts_dir / "DCS-BIOS"
    reference_json_dir = dcs_bios_dir / "doc" / "json"
    export_lua_file = scripts_dir / "Export.lua"
    export_lua_text = ""
    if export_lua_file.exists():
        export_lua_text = export_lua_file.read_text(encoding="utf-8", errors="ignore")

    normalized_export = export_lua_text.replace("/", "\\").lower()
    return DcsBiosSetupStatus(
        saved_games_path=saved_games,
        scripts_dir=scripts_dir,
        dcs_bios_dir=dcs_bios_dir,
        reference_json_dir=reference_json_dir,
        export_lua_file=export_lua_file,
        scripts_dir_exists=scripts_dir.exists(),
        dcs_bios_dir_exists=dcs_bios_dir.exists(),
        reference_json_dir_exists=reference_json_dir.exists(),
        export_lua_exists=export_lua_file.exists(),
        export_lua_mentions_dcs_bios="scripts\\dcs-bios\\bios.lua" in normalized_export,
    )


def format_dcs_bios_setup_help(status: DcsBiosSetupStatus) -> str:
    lines = [
        "DCS-BIOS setup help",
        "",
        "Purpose:",
        "- DCS AI Copilot uses DCS-BIOS read-only for cockpit data.",
        "- Version 2.0 still sends no cockpit commands.",
        "- This helper does not edit DCS files automatically.",
        "",
        "Detected paths:",
        f"- DCS Saved Games: {status.saved_games_path}",
        f"- Scripts folder: {status.scripts_dir}",
        f"- DCS-BIOS folder: {status.dcs_bios_dir}",
        f"- Reference JSON: {status.reference_json_dir}",
        f"- Export.lua: {status.export_lua_file}",
        "",
        "Current status:",
        f"- Scripts folder exists: {_yes_no(status.scripts_dir_exists)}",
        f"- DCS-BIOS folder exists: {_yes_no(status.dcs_bios_dir_exists)}",
        f"- DCS-BIOS reference JSON exists: {_yes_no(status.reference_json_dir_exists)}",
        f"- Export.lua exists: {_yes_no(status.export_lua_exists)}",
        f"- Export.lua loads DCS-BIOS: {_yes_no(status.export_lua_mentions_dcs_bios)}",
        "",
        "Install or repair steps:",
        "1. Close DCS World.",
        f"2. Download the latest DCS-BIOS release from: {DCS_BIOS_RELEASES_URL}",
        "3. Download the DCS-BIOS_x.y.z.zip file, not the source-code zip.",
        "4. Extract the ZIP to a temporary folder.",
        f"5. Create this folder if it does not exist: {status.scripts_dir}",
        f"6. Copy the extracted DCS-BIOS folder into: {status.scripts_dir}",
        "7. Open Export.lua in Notepad, or create it if it does not exist.",
        "8. Add this line at the end of Export.lua if it is missing:",
        f"   {EXPORT_LUA_LINE}",
        "9. Save Export.lua as plain text.",
        "10. Start DCS in the F/A-18C, then start DCS AI Copilot.",
        "11. Open the dashboard and check that Aircraft, Master Arm and COMM data update.",
        "",
        "How to verify:",
        "- Run: DCS-AI-Copilot.exe --doctor",
        "- Run: DCS-AI-Copilot.exe --dcs-bios-help",
        "- Open local DCS-BIOS reference, if installed: doc\\control-reference.html",
        "",
        "Safety notes:",
        "- Back up Saved Games before editing Export.lua if you are unsure.",
        "- AI Copilot does not read hidden multiplayer server data.",
        "- AI Copilot does not change DCS graphics, OpenXR, SteamVR, Oculus or headset settings.",
        "",
        f"Official user guide: {DCS_BIOS_USER_GUIDE_URL}",
    ]
    return "\n".join(lines)


def _yes_no(value: bool) -> str:
    return "YES" if value else "NO"
