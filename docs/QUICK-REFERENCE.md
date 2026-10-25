# DCS AI COPILOT — QUICK REFERENCE

## CASE III

> **EAT -> CROSSING -> COMMENCING**

| Situation | SAY |
|---|---|
| EAT received | **EAT two one** |
| Cross marshal fix inbound | **CROSSING** |
| Begin approach | **COMMENCING** |
| Open/check plan | **CASE THREE STATUS** |
| Remove CASE III plan | **CLEAR CASE** |

Full-time example: **EAT one four two one** or **EAT 14:21**.
Each new **CROSSING** replaces the previous hold-plan origin.

## NOTES

| Action | SAY |
|---|---|
| Create | **NOTE** `<text>` |
| Show notes page | **NOTES** |
| Remove all notes | **CLEAR NOTES** |

The six newest notes are shown; older notes remain in session history.

## DISPLAY

- **DAY MODE**
- **NIGHT MODE**

## PTT

1. Hold PTT.
2. Wait for `RECORDING`.
3. Speak the whole phrase.
4. Release PTT — recording stops immediately.
5. Check `LAST TRANSCRIPT` / `LAST ERROR`.

Joystick is the primary PTT when configured; F13 remains the keyboard
fallback.

## MICROPHONE

Dashboard `VOICE` -> choose input -> **Use microphone** -> make a short PTT
test. The `MICROPHONE` line shows the active input. MME, DirectSound and
WASAPI may be different Windows paths to the same device; there is no
universal requirement to use MME.

If the selected microphone is disconnected, Copilot does **not** silently
fall back. Reconnect it or select another input. Refresh the list; restart
Copilot if a newly connected device remains missing.

## TIME SOURCE

- Preferred: DCS-BIOS mission start + model time (`MISSION`). It follows the
  simulated cockpit clock and freezes when DCS is paused; Copilot does not
  extrapolate between packets.
- Before mission-time data has arrived: local PC clock (`PC`).
- With PC source only: **SYNC CLOCK HHMM** creates a manual CASE III offset
  without changing Windows time. Example: **SYNC CLOCK one four two one**.
- If mission packets stop after mission time became active, the last mission
  reading is retained and marked not live; Copilot does not silently switch
  to PC time.
- Changing time base or restarting a mission clears incompatible CASE III
  timing so PC and mission times are never mixed.

## OPENKNEEBOARD

Web Dashboard URL: `http://127.0.0.1:8765`

The page updates automatically. It shows selected microphone, voice status,
last transcript/error, time source and CASE III state.

## HELP

- Voice guide: `docs/VOICE-COMMANDS.md`
- Microphone guide: `docs/MICROPHONE-SETUP.md`
- DCS-BIOS check: `DCS-AI-Copilot.exe --dcs-bios-help`
- Installation check: `DCS-AI-Copilot.exe --doctor`
