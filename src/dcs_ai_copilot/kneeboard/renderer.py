from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Iterable

from dcs_ai_copilot.kneeboard.state import VISIBLE_NOTE_LIMIT, VoiceNote
from dcs_ai_copilot.voice.parser import CapturedCoordinate


def render_kneeboard(
    captures: Iterable[CapturedCoordinate],
    output_file: Path,
    notes: Iterable[VoiceNote] = (),
) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    capture_list = list(captures)
    note_list = list(notes)
    hidden_note_count = max(0, len(note_list) - VISIBLE_NOTE_LIMIT)
    visible_notes = note_list[-VISIBLE_NOTE_LIMIT:]
    body = "\n".join(
        [_render_capture(capture) for capture in capture_list]
        + [_render_history(hidden_note_count)]
        + [_render_note(note) for note in visible_notes]
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DCS AI Copilot Kneeboard</title>
  <style>
    body {{
      margin: 0;
      padding: 24px;
      background: #080e14;
      color: #c5cdd3;
      font-family: Consolas, "Courier New", monospace;
      font-size: 28px;
      line-height: 1.35;
    }}
    .entry {{
      white-space: pre-line;
      font-weight: 700;
    }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""
    output_file.write_text(html, encoding="utf-8")
    return output_file


def _render_capture(capture: CapturedCoordinate) -> str:
    lines = [
        f"{capture.kind.upper()} {capture.index}",
        capture.format_latitude(),
        capture.format_longitude(),
        capture.format_elevation(),
    ]
    return f'  <div class="entry">{escape(chr(10).join(lines), quote=False)}</div>'


def _render_note(note: VoiceNote) -> str:
    lines = [
        f"NOTE {note.index}",
        note.text,
    ]
    return f'  <div class="entry">{escape(chr(10).join(lines), quote=False)}</div>'


def _render_history(hidden_note_count: int) -> str:
    if hidden_note_count <= 0:
        return ""
    return f'  <div class="entry">{hidden_note_count} OLDER NOTES IN HISTORY</div>'
