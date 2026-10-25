# PROJECT_STATE.md — DCS AI Copilot

## Current release

- Version: **3.0.0**.
- Windows releases are built by the tag-triggered GitHub Actions workflow.
- The installer, portable ZIP and release notes are published on the matching
  GitHub Release.

## Purpose and safety boundary

DCS AI Copilot is a lightweight local dashboard for DCS World F/A-18C,
OpenKneeboard and cloud speech-to-text. It binds only to
`http://127.0.0.1:8765` and keeps local CPU/GPU use low.

- DCS-BIOS integration is read-only; no cockpit commands are sent.
- No hidden multiplayer/server data is read.
- No local LLM or GPU inference is used.
- DCS graphics, OpenXR, PimaxXR, QuadViews, Pimax Play, SRS and Discord
  settings are not changed.
- API keys and local `config.ini` values are never release content.

## Implemented

### Voice and microphone

- Joystick PTT with F13 keyboard fallback; 16 kHz mono PCM records only while
  PTT is held.
- OpenAI cloud STT with optional Gemini cloud fallback.
- Dashboard microphone selector enumerates inputs on demand, validates the
  selected input and saves its exact device name + Windows host API.
- Changing the Copilot input does not change Windows or other applications.
  There is deliberately no automatic fallback if the selected mic disappears.
- One bounded FIFO worker preserves spoken note/clear/CASE III order and
  recovers after transcription or routing errors. Up to eight audio clips can
  wait; saved session notes remain unlimited and the six newest are displayed.
- Dashboard shows microphone, recording state, actual STT model/time, pending
  count, last transcript and last error.

### Dashboard and startup

- Standard-library `ThreadingHTTPServer` serves the dashboard and microphone
  API without one idle connection blocking all clients.
- Same-origin checks and bounded JSON bodies protect the local microphone API.
- Hidden Windows launcher resolves project-local Python first, verifies HTTP
  readiness, records the listening PID and keeps dated startup logs.
- The page polls again 0.5 seconds after each completed response, without
  overlapping requests.

### CASE III and DCS-BIOS

- Generic assignment, EAT, crossing, hold timeline and spoken commencement;
  no mission-specific assignment defaults.
- Preferred clock is DCS-BIOS mission start + model time. Before those words
  arrive, PC time is used and can be aligned with `SYNC CLOCK HHMM` without
  changing Windows time. Time bases are never mixed.
- F/A-18C aircraft, Master Arm and COMM values remain read-only.

### Documentation

- `docs/VOICE-COMMANDS.md`: verified command inventory and pilot sequence.
- `docs/MICROPHONE-SETUP.md`: selector, Windows host APIs and troubleshooting.
- `docs/QUICK-REFERENCE.md`: compact OpenKneeboard reference.
- `docs/DCS-AI-Copilot-Quick-Guide.pdf`: three-page printable A4 guide,
  generated from the adjacent project-owned HTML source.

## Verification

- Full automated suite: **168 tests passed** on 25 Oct 2026. Tests use fake
  speech providers and make no paid API requests.
- The quick-guide PDF was rendered and visually reviewed as three A4 pages.
- `git diff --check` is required before every release commit.

## Known limitations

- Live in-flight validation of DCS-BIOS mission-time delivery and full CASE III
  behavior remains incomplete.
- OpenKneeboard readability still needs a final headset check.
- Actual STT accuracy, latency and account access depend on the selected cloud
  provider and require a real paid request to verify.
- Newly connected audio devices can require an AI Copilot restart before
  PortAudio lists them.
- SRS/Discord capture and cockpit write/control are not implemented.

## Recommended next improvement

Add a context-sensitive **SAY NOW / NEXT** panel to the dashboard so the pilot
sees the next useful CASE III voice command without memorizing the sequence.
This is a future idea, not part of version 3.0.0.
