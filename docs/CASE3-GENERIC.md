# Generic CASE III in DCS AI Copilot

This workflow works in ordinary and multiplayer DCS missions, with or
without MA CASE 3 or Bankler. It follows `I:\Claudecode\ma-case3\Case 3
Procedures.pdf`, especially pages 9, 18–22 and 24–29. The pilot supplies
the actual assignment; radial, distance, angels, final bearing, button,
TACAN and ICLS have no trainer defaults.

## Speak the assignment

Hold PTT for the whole readback and release it to transcribe. A complete
example is:

> “Case three, marshal two zero zero, two two, angels seven, time three two,
> button one five, final bearing one seven zero, TACAN seven two X, ICLS one.”

This stores R200, 22 DME, angels 7, Push/EAT :32, button 15, FB170,
TACAN 72X and ICLS 1. The inbound reciprocal is 020. `radial`, `marshal
radial`, `D M E`, `marshal D M E`, `push time`, `E A T` and `expected approach
time` are accepted. Fields can also be spoken separately. Push Time and EAT
share one internal value. A partial or malformed field is rejected without
changing an earlier valid assignment. Explicit `EAT 1432` and `EAT 14:32`
retain HHMM support.

## Hold and commence

Say **CROSSING**, **marshal crossing**, or **marshal crossing now** at each
early *inbound* pass of the fix. Every command replaces the previous
planning origin while keeping Push/EAT. The page shows LATEST CROSSING,
PUSH / EAT, remaining time, lap lengths, the current turn/leg and the
outbound/inbound straight-leg durations. Crossing begins TURN OUT; each
lap then flies OUTBOUND, TURN IN, INBOUND and ends at the fix. There is no
extra turn after the final inbound.

Turns are 2:00 each and never adjusted. A standard lap is 2:00 turn out,
1:00 outbound, 2:00 turn in, 1:00 inbound. Four to six minutes remaining
after standard laps becomes a shorter final lap. A residual under two
minutes lengthens the last lap. For a residual of two to four minutes, the
planner compares feasible lap counts and evenly distributes seconds using
the count whose laps are closest to 6:00. Thus 11 minutes is **6+5**
(the last legs are 0:30 each); 14 minutes is **7+7** (all straight legs
are 1:30); 15 minutes is **5+5+5**. Below four minutes it shows
INSUFFICIENT TIME FOR FULL HOLD; it never makes a negative leg.

In a generic mission, Copilot has no physical aircraft position. Say
**COMMENCING**, **commence**, or **commence now** at the actual Push/EAT
fix crossing to change from hold to approach guidance. Silence and the
clock reaching EAT do not change phase. The guidance covers 250 KIAS and
about 4000 fpm to platform, 5000 ft then about 2000 fpm, the 20 DME
correction toward the assigned FB and 1200 ft level-off, 8 DME landing
configuration, and the ball at about 3/4 NM. Unassigned values appear as
“assigned” labels; no trainer numbers are inserted.

**CLEAR CASE**, **clear case three**, **clear case 3**, **case three reset**
and **reset case three** clear only CASE III state. **CLEAR NOTE** and
**CLEAR NOTES** clear only notes. Theme and unrelated state survive.

## Recording and time

The microphone records locally while PTT is held. There is no VAD or
silence-based stop; transcription starts after PTT release, or at the
configurable 90-second safety limit (`max_record_seconds` in `config.ini`).
The configured primary STT is OpenAI `gpt-4o-mini-transcribe`, with Gemini
`gemini-2.5-flash` fallback. Both transcriptions are cloud API requests;
the microphone recorder and deterministic command parser run locally.
Automated tests use fake transcribers and make no paid requests.

DCS-BIOS CommonData mission start and model-time words are the preferred
clock, independent of the trainer mission. When those words have not
arrived, the page states **TIME SOURCE: PC CLOCK**. Say **SYNC CLOCK HHMM**
to align CASE III to a cockpit time manually in that fallback state, without
changing Windows time. Sync clears old EAT and crossing because they may
belong to another time base. A later switch to mission time also clears
old timing values. Mission-clock delivery still needs a real DCS check.

## MA CASE 3 trainer

The trainer is standalone. Its own Lua scores the approach and detects
real inbound fix passes. Copilot remains generic and manual when both run:
there is currently no verified safe event bridge. On an early pass, say
CROSSING to refresh Copilot; at the valid Push/EAT crossing, say COMMENCING
in Copilot. The trainer commences automatically on its own. Do not infer
physical crossings from silence.
