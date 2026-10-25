# Voice commands

This guide describes the commands implemented by the current DCS AI Copilot
voice router. Hold PTT for the whole phrase, speak, and release PTT. The audio
is transcribed after release.

## What do I say when?

The core CASE III memory aid is:

> **EAT -> CROSSING -> COMMENCING**

1. When Marshal gives you an expected approach time, say **“EAT two one”**.
   Copilot stores the next occurrence of minute `:21`. You can also say a full
   time, for example **“EAT one four two one”** or **“EAT 14:21”**.
2. When you cross the marshal fix inbound, say **“CROSSING”**. Copilot records
   the current clock time and calculates the hold plan to the stored EAT. Say it
   again after a later crossing to replace the previous planning origin.
3. When you actually leave the hold and begin the approach, say
   **“COMMENCING”**. Copilot changes to approach guidance. Reaching EAT by
   itself does not commence the approach.
4. To open or check the CASE III page, say **“CASE THREE STATUS”**.
5. To save something unrelated to the CASE III plan, say
   **“NOTE tanker north”**.
6. To return to the notes page, say **“NOTES”**.

Watch `LAST TRANSCRIPT` and `LAST ERROR` in the VOICE section if a command
does not have the expected effect.

## CASE III commands

| What to say | When | What Copilot does | Useful accepted aliases | Example |
|---|---|---|---|---|
| `CASE THREE` | Before entering or checking CASE III | Opens the CASE III page; it does not change the assignment | `CASE 3`, `CASE III`, `CASE TREE`, `CASE FREE`, `THIS THREE`, `SHOW CASE THREE`, `CASE THREE STATUS` | `CASE THREE STATUS` |
| `EAT <time>` | When Marshal gives Push/EAT | Stores the next matching time and prepares hold timing | `E A T`, `TIME`, `PUSH TIME`, `EXPECTED APPROACH TIME` when used as an assignment field | `EAT three two` |
| `CROSSING` | At an inbound marshal-fix crossing | Records “now” and replans the hold to EAT | `CROSSING NOW`; in CASE III: `MARSHAL`, `MARSHAL CROSS`, `MARSHAL CROSSING`; also `MARSHAL CROSSING NOW` from either page | `CROSSING` |
| `COMMENCING` | When leaving the hold for the approach | Starts the approach phase and opens CASE III | `COMMENCE`, `COMMENCE NOW` | `COMMENCING` |
| `CLEAR CASE` | When the CASE III plan should be discarded | Clears CASE III assignment and timing only; notes are preserved | `CLEAR CASE THREE`, `CLEAR CASE 3`, `RESET CASE THREE`, `CLEAR CASE TREE`, `RESET THIS THREE` | `CLEAR CASE` |
| `SYNC CLOCK <HHMM>` | Only when the page says the time source is PC | Offsets Copilot's CASE III clock without changing Windows time; clears old CASE III timing | Digits may be spoken separately; a colon is accepted | `SYNC CLOCK one four two one` |

### Read back a marshal assignment

You can speak several labeled fields in one PTT recording:

> **“CASE THREE, MARSHAL two zero zero two two, ANGELS seven, TIME three
> two, BUTTON one five, FINAL BEARING one seven zero, TACAN seven two X,
> ICLS one.”**

This stores radial 200, 22 DME, angels 7, EAT `:32`, button 15, final
bearing 170, TACAN 72X and ICLS 1. Fields may also be supplied separately.
Implemented labels and ranges are:

- `MARSHAL` or `RADIAL`: radial 000–359; `MARSHAL` can include DME after the
  three radial digits.
- `DME`: 1–100.
- `ANGELS`: 1–30.
- `TIME`, `PUSH TIME`, `EXPECTED APPROACH TIME` or `EAT`: one to four time
  digits.
- `BUTTON` or `APPROACH BUTTON`: 1–30.
- `FINAL BEARING` or `FB`: 000–359.
- `TACAN`: channel 1–126 followed by X or Y.
- `ICLS`: channel 1–20.

A malformed CASE III field is rejected without applying a partial update.

## Notes commands

| What to say | When | What Copilot does | Useful accepted aliases | Example |
|---|---|---|---|---|
| `NOTE <text>` | Any time you want a short written reminder | Saves the text after the command as a note | `NOTES <text>`, `NOTERA <text>`, `ANTECKNA <text>`, `ANTECKNING <text>` | `NOTE tanker TACAN one two X fuel four two zero zero` |
| `NOTES` | To see the notes page | Opens the notes/targets page | `SHOW NOTES`, `BACK TO NOTES` | `NOTES` |
| `CLEAR NOTES` | To remove all session notes | Clears notes only; CASE III data is preserved | `CLEAR`, `CLEAR NOTE`, `RENSA`, `RENSA NOTES`, `RENSA ANTECKNINGAR`, `RADERA NOTES`, `RADERA ANTECKNINGAR` | `CLEAR NOTES` |

The dashboard shows the six newest notes. Older notes remain in session
history; this display limit does not stop PTT or note capture.

## Display commands

| What to say | What Copilot does | Alias | Example |
|---|---|---|---|
| `DAY MODE` | Selects the light dashboard theme | `DAYTIME` | `DAY MODE` |
| `NIGHT MODE` | Selects the dark dashboard theme | `NIGHTTIME` | `NIGHT MODE` |

## Coordinate capture

The current decimal-minutes target format is also routed through voice:

> **“TARGET NORTH 42 15 decimal 732, EAST 041 38 decimal 219, ELEVATION
> 428.”**

The deterministic parser displays `N42°15.732'`, `E041°38.219'` and
`ELEV 428 FT`. Check `LAST TRANSCRIPT`: speech recognition must preserve the
numbers well enough for the parser. MGRS is not currently a documented
coordinate command because it is not implemented by the current parser.

## Command safety and context

- Prefixing a phrase with `NOTE` gives note capture priority. For example,
  `NOTE DAY MODE` saves text rather than changing the theme.
- The short forms `MARSHAL`, `MARSHAL CROSS` and `CROSSING MARSHAL` are
  intentionally active only while the CASE III page is selected.
- `MARSHAL CROSSING NOW` is an explicit crossing command from either page.
- `CLEAR NOTES` and `CLEAR CASE` affect different data.
- Commands are matched locally after cloud speech-to-text; no local LLM is
  used.
