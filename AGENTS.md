# AGENTS.md — DCS AI Copilot

Durable rules for anyone (human or agent) changing this project.

## Session start

1. Read this file, `PROJECT_STATE.md`, `HANDOVER.md`.
2. `git status` and `git log -1 --oneline`. Git is the truth for HEAD and
   the working tree; these files never record the current HEAD.
3. Inspect only the source files the task touches.

## Safety rules

- **Never `git reset --hard`, `git checkout -- .` or `git stash` without
  asking.** Most of the Case III work and several script edits are
  uncommitted working-tree changes. Before a change, make a restore point
  next to the repo, as earlier work did:
  `I:\Codex\DCS-AI-Copilot-backup-<topic>-<yyyymmdd-hhmmss>` with
  `HEAD.txt`, `working-tree.patch` and a copy of tracked + untracked,
  non-ignored files.
- Do not commit or push unless the user explicitly asks.
- Never commit `config.ini` secrets, API keys or `.env`. STT uses paid
  OpenAI/Gemini calls: tests use fakes (`FakeTranscriber`); do not call the
  real providers without explicit permission.
- DCS-BIOS is **read-only**. No cockpit commands, no hidden multiplayer
  data, no changes to DCS/VR/graphics settings (README safety summary).
- The web server binds **127.0.0.1 only** (`start_kneeboard_server`
  refuses anything else); POSTs reject cross-origin requests.
- A running app on port 8765 is the user's. Do not stop it; review UI
  changes on another port with synthetic state (the 2026-09 reviews used a
  scratch server on 8799). Decide whether it is running by checking the
  port, not `.runtime/dcs-ai-copilot.pid` — that file survives a stopped
  process and has been stale before.
- `.runtime/` holds verification evidence (run logs from live sessions).
  Never delete or rewrite it to tidy up; it is the only record of what was
  observed outside the tests.

## Architecture principles

- `KneeboardState` is the single shared state; the web page polls
  `/api/state` every 1.5 s.
- Voice: PTT → STT → `voice/router.py` (deterministic, raw transcript and
  note bodies are never normalized) → notes → coordinate parser fallback.
- Case III timing (`case3.py`) is pure datetime/timedelta arithmetic in
  whole seconds, derived on every snapshot from two stored times (EAT,
  crossing). No countdown variables, no scheduled events.
- Time base: `clock.py` — DCS mission time from DCS-BIOS CommonData when
  available, else PC time. Times from different bases are never mixed.
- Generic CASE III assignments are optional values from the pilot. No
  MA CASE 3 radial, DME, angels, final bearing, button, TACAN or ICLS may
  appear as a runtime default. Copilot must function without the mission.
- Hold rule: turns are always 2:00, standard lap 2/1/2/1; the procedural
  examples require 11 min = 6+5 and 14 min = 7+7. For a remainder under
  2 min, lengthen the last lap; for 2–4 min, choose the feasible lap count
  closest to 6 min and distribute seconds evenly. Every final inbound ends
  at the fix with no extra turn. Must match
  `C3_HoldingPlan` in `I:\Claudecode\ma-case3\src\case3_module.lua`.
- Repeated spoken CROSSING replaces the previous hold-plan origin while
  keeping Push/EAT. Generic commencement requires spoken COMMENCING; time
  passing alone must never transition the phase.
- Case III UI must fit a 480×640 kneeboard without scrolling, in NIGHT and
  DAY themes.

## Testing

`python -m unittest discover -s tests -q` must pass before handing over.
Add tests with every behaviour change; the Case III tests assert exact
second sums and phase boundaries.

## Context management

Keep `HANDOVER.md` short and current (replace, don't append). Update
`PROJECT_STATE.md` when durable state changes. Detailed feature reports go
in `docs/`.
Never delete important project evidence, logs, or provenance merely to save
context.
