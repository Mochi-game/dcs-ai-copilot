# HANDOVER.md — DCS AI Copilot

## Project

A light VR copilot for DCS World F/A-18C: a local OpenKneeboard web
dashboard on `http://127.0.0.1:8765`, push-to-talk voice notes and commands
via cloud STT, read-only DCS-BIOS values, and a generic standalone CASE III
workflow. Durable behavior and limits live in `PROJECT_STATE.md`; the rules
every agent must follow are in `AGENTS.md`.

## Current milestone

The generic standalone CASE III implementation is **complete in the working
tree and unflown**. This is a handover for live verification, not for new
features. Do not change application code without being asked.

## Repository state

- Expected HEAD at handover: `43f9d7d Fix Windows release workflow
  arguments`. Git is the truth — run `git status` and `git log -1 --oneline`
  at session start; do not expect this file to track HEAD.
- Branch `main` carries substantial uncommitted work: roughly 16 modified
  tracked files and 18 untracked ones. Nothing has been committed or pushed,
  by the user's decision. A documentation-only commit would still leave the
  application changes uncommitted.
- Important uncommitted CASE III components:
  - `src/dcs_ai_copilot/case3.py` — hold/approach timing arithmetic
  - `src/dcs_ai_copilot/clock.py` — mission-time vs PC-time base
  - `src/dcs_ai_copilot/voice/router.py` — deterministic command routing
  - `src/dcs_ai_copilot/web/case3_ui.py` — 480×640 kneeboard view
  - tests: `test_case3.py`, `test_case3_api.py`, `test_case3_clock_gauge.py`,
    `test_case3_generic.py`, `test_case3_timeline.py`,
    `test_command_router.py`
  - docs: `docs/CASE3-GENERIC.md` (pilot guide), `CASE3-HOLD-TIMELINE.md`,
    `CASE3-PHASE1.md`
- Restore point taken before the 30 Sep implementation:
  `I:\Codex\DCS-AI-Copilot-backup-case3-generic-20260930-073844`
  (HEAD, patch, tracked and non-ignored untracked files).
- Preserve the working tree. Do not reset, stash, commit or push without
  explicit authorization.

## Verification status

- `python -m unittest discover -s tests -q` → **131 passed, 5 Oct 2026**.
  Tests use `FakeTranscriber`; no paid API calls.
- **Live voice chain, 1 Oct 2026.** A real run with a real microphone and the
  real OpenAI provider routed `"CASE III."` → `CASE3_VIEW` and
  `"EAT four zero."` → `CASE3_EAT`. PTT → STT → router is confirmed outside
  the fakes. Evidence: `.runtime/dcs-ai-copilot.err.log` — keep it. One
  clipped utterance (`"IT. Four zero."`) failed to route in the same run,
  consistent with PTT pressed just after speech began.
- STT architecture: local PTT capture (WinMM joystick button 0, F13
  fallback), 90-second limit, no silence stop; OpenAI
  `gpt-4o-mini-transcribe` primary with Gemini `gemini-2.5-flash` fallback.
  Both are paid cloud calls.
- Time source: DCS mission time from DCS-BIOS `TIME_START_*` + `TIME_MODEL_*`
  when available, otherwise PC time, which can be aligned with
  SYNC CLOCK HHMM without touching Windows. The two bases are never mixed and
  the clock does not extrapolate, so a DCS pause freezes the timers.

## Still unverified

- DCS-BIOS `TIME_*` delivery in flight, and whether the page shows
  "EAT · MISSION" rather than PC fallback.
- OpenKneeboard 480×640 CASE III readability in DAY and NIGHT.
- Spoken CROSSING and COMMENCING during a real flight.
- Actual STT latency; a spoken crossing is timestamped when the transcript is
  handled, not when speech began.
- The page polls every 1.5 s, so a phase change can appear up to one poll
  late.

## Environment note

`.runtime/dcs-ai-copilot.pid` holds PID 8116 from the 1 Oct run, but nothing
was listening on port 8765 on 5 Oct — the file is stale. Check the port, not
the pid file, before concluding the app is running. If it is running, it is
the user's; do not stop it.

## Recommended next action

A live DCS CASE III validation, with no application-code changes:

1. Start the app (`Start-DCS-AI-Copilot.ps1`), after confirming port 8765 is
   free.
2. Fly a real DCS CASE III recovery.
3. Check whether DCS-BIOS `TIME_*` is received and the UI shows mission time
   rather than PC fallback.
4. Check OpenKneeboard 480×640 readability in both DAY and NIGHT.
5. Speak CROSSING and COMMENCING and confirm the hold plan re-origins and the
   approach phase starts.
6. Record the observed STT latency.
7. Write the real results into `PROJECT_STATE.md` and replace this file.

Starting the app and flying make paid STT calls — get explicit authorization
first.
