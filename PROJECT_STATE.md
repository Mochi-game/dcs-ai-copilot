# PROJECT_STATE.md — DCS AI Copilot

## Purpose

A light copilot for DCS World F/A-18C, built for VR: a local OpenKneeboard
web dashboard (`http://127.0.0.1:8765`), push-to-talk voice notes and
commands transcribed by OpenAI (Gemini fallback), read-only DCS-BIOS
values, and a generic standalone CASE III workflow.

## Versions

- Git tags `v0.1.0`, `v2.0`; last commit "Fix Windows release workflow
  arguments" (24 Aug 2026). Releases are built by a tag-triggered Windows
  workflow.
- Everything below under "Case III" is **uncommitted working-tree work**
  (13–30 Sep 2026). The user requested no commit or push.

## Verified functionality

- Notes, coordinate capture, PTT (WinMM joystick button 0, F13 fallback),
  STT, DCS-BIOS read-only listener, NIGHT/DAY themes, static
  `kneeboard.html` fallback.
- **Voice chain verified live (1 Oct 2026).** A real app run with a real
  microphone and the real OpenAI STT provider routed spoken input correctly:
  `"CASE III."` → `CASE3_VIEW`, `"EAT four zero."` → `CASE3_EAT`.
  PTT → STT → `voice/router.py` is therefore confirmed outside the test
  fakes. Evidence: `.runtime/dcs-ai-copilot.err.log`. One clipped utterance
  in the same run (`"IT. Four zero."`) did not route, consistent with PTT
  pressed slightly after speech began. Nothing in that run establishes
  anything about DCS-BIOS or the kneeboard display.
- CASE III (current guide: `docs/CASE3-GENERIC.md`):
  - Deterministic combined/partial spoken marshal readback with optional
    radial, DME, angels, Push/EAT, button, FB, TACAN and ICLS. No trainer
    assignment defaults. Inbound is the reciprocal of the supplied radial.
  - Each spoken CROSSING replaces the previous hold-plan origin, preserving
    Push/EAT. A spoken COMMENCING starts the generic approach phase; silence
    and clock time cannot trigger it. CLEAR CASE and CLEAR NOTES are isolated.
  - Fixed 2-minute turns; 11 min = 6+5, 14 min = 7+7. Every final inbound
    ends at the fix. Approach guidance follows `Case 3 Procedures.pdf`.
  - DCS mission clock via DCS-BIOS `TIME_START_*` + `TIME_MODEL_*`; PC fallback
    can be manually synced with SYNC CLOCK HHMM without changing Windows.
  - Local PTT capture with configurable 90-second limit and no silence stop;
    OpenAI `gpt-4o-mini-transcribe` primary, Gemini `gemini-2.5-flash`
    fallback, both cloud STT. Tests use fakes.
- Test suite: 131 tests OK, re-run 5 Oct 2026 with no change since the
  30 Sep run. A paired synthetic manual-flow check also matched the
  trainer's 11-minute and re-crossed 7-minute plans.

## Known limitations

Live DCS validation remains **incomplete**. The 1 Oct run covers the voice
chain only. Still unverified:

- **DCS-BIOS mission time.** No evidence that DCS-BIOS delivers the
  `TIME_START_*` / `TIME_MODEL_*` CommonData words to the app during flight,
  or that the page shows "EAT · MISSION" instead of the PC fallback. Unit
  tests and a synthetic-clock page review only.
- **OpenKneeboard CASE III display.** The 480×640 view has never been read
  in the headset; readability in NIGHT and DAY themes is unconfirmed.
- **Spoken CROSSING and COMMENCING in a real flight.** Covered by unit tests
  and a synthetic paired timing check, not by a flown mission.

Other limitations:

- Spoken crossing time is when the transcript is handled, not when speech
  began (STT latency, expected ~1–2 s; not yet measured against a live run).
- Page updates every 1.5 s poll; a phase change can show up to one poll
  late (no accumulated drift).

## Important decisions

- Hold algorithm follows the procedural examples; never shorten turns.
- Mission clock without extrapolation, so a DCS pause freezes the timers.
- CASE III is generic and standalone: the Copilot must work with no mission
  loaded and carries no MA CASE 3 assignment values as defaults.
- Pairing with the MA CASE 3 mission at `I:\Claudecode\ma-case3` (not a git
  repo) is **optional in both directions**; neither project requires the
  other. No automatic trainer-event bridge is implemented and no verified
  safe one was found, so paired operation stays manual: the pilot speaks
  CROSSING/COMMENCING to the Copilot while the trainer's Lua detects its own
  events.

## Planned / open

- Live DCS test of the mission clock, the kneeboard view and the full
  Case III flow.
- Consider committing the Case III work once flown (user decision).
