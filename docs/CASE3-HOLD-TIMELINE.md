# Case III — adjusted hold, TIME TO NEXT och reset

Historical implementation notes. For the current generic workflow and
assignment-driven values, see [CASE3-GENERIC.md](CASE3-GENERIC.md).

## Tillägg 2026-09-26: DCS-klocka, varvsmätare, svängsignal, röstformer

Byggt för MA CASE 3 v2.1.0 (`I:\Claudecode\ma-case3`). Hold-algoritmen
nedan är **oförändrad**: användaren bekräftade att svängarna alltid är
2 min (4 min per 360°) och att en rest under 4 min förlänger sista varvet
(8 min = ett varv med 2:00 raksträckor, aldrig två 4-minutersvarv).

- **Klocka** (`src/dcs_ai_copilot/clock.py`): DCS-BIOS CommonData
  `TIME_START_*` (LoGetMissionStartTime, sekunder efter midnatt) +
  `TIME_MODEL_*` (LoGetModelTime i hundradelar) = cockpitklockan. Ingen
  extrapolering mellan paket, så paus fryser klockan. Utan data används
  PC-klockan. Varje avläsning har en nyckel (PC, eller MISSION + epok);
  EAT/crossing satta på en annan nyckel släpps. Ny starttid eller
  modelltid som faller > 2 s två gånger i rad = ny epok (ett ensamt
  trasigt paket ignoreras). `reference.py` läser nu även `CommonData.json`.
- **Röst** (`voice/router.py`): bara "crossing" / "crossing now" på
  CASE III-bladet. EAT tar minut 1–60 i siffror, siffer-för-siffra eller
  som tal ("thirty two", "fourteen thirty two"), 60 = hel timme, och vanliga
  STT-byten (to/too=2, for=4, tree=3). `resolve_eat` tar 1–4 siffror.
- **Mätare** (`lap_gauge`): varvlängder i flygordning, "TWO MORE LAPS ·
  NEXT 6:00", "ONE MORE LAP · NEXT 7:00 EXTENDED", "LAST LAP · COMMENCE AT
  MARSHAL". Före crossing: "IF CROSSING NOW: 2 LAPS · 6:00 + 5:40".
- **Signal** (`phase_cue`): OUTBOUND TURN / TURN INBOUND IN / INBOUND TURN /
  NEXT LAP IN / COMMENCE IN med nedräkning; `cue_urgent` de sista 15 s av
  OUTBOUND (röd, blinkar).
- **Fast rad**: COMMENCE 21 DME · 6000 FT · 250 KT (`COMMENCE_DME`,
  `MARSHAL_ALTITUDE_FT`, `HOLD_SPEED_KT` i `case3.py`).

Tester: `tests/test_case3_clock_gauge.py` (19 nya). Hela sviten 123 OK.
Bladet granskat i 480×640 med syntetisk uppdragsklocka på port 8799:
ryms utan scroll, varv 1 och 2, blinkande TURN INBOUND. **Inte testat
skarpt i DCS**: att DCS-BIOS faktiskt skickar TIME_* till appen under
flygning. Backup före ändring: `I:\Codex\DCS-AI-Copilot-backup-case3-v2-20260926-195700`.


Implementerat 2026-09-14 i `I:\Codex\DCS-AI-Copilot`.

## Exakt algoritm

Beräkna `T = EAT - Marshal Crossing` med datetime/timedelta och hela sekunder.
EAT-upplösningen är oförändrad: nästa rimliga minut/tid, alltid sekunder 00.
Crossing behåller sekunder. Den här modellen använder alltid 360-sekunders
standardhold och två fasta 120-sekunderssvängar.

1. Om `T < 240`: ingen plan/timeline. Visa INSUFFICIENT HOLD TIME och behåll
   nedräkningen till EAT. Negativa tider ger inte negativa varv eller ben.
2. Annars: `full, remainder = divmod(T, 360)` med heltal.
3. `remainder == 0`: bara standardhold, inget justerat slutvarv.
4. `240 <= remainder < 360`: behåll full, använd remainder som slutvarv.
5. `0 < remainder < 240`: minska full med ett och sätt slutvarvet till
   `360 + remainder`. Eftersom steg 1 redan avvisat T under 240 kan full
   aldrig bli negativt här.
6. För ett slutvarv F: `straight_total = F - 240`,
   `outbound = straight_total // 2`, `inbound = straight_total - outbound`.
   Vid udda antal sekunder får inbound den extra sekunden.

Inga beräkningssteg använder flyttal. Varje plan modelleras som explicita faser
med absoluta start- och sluttider. Den sista fasen slutar exakt vid EAT.

| Tillgänglig tid | Fulla standardhold | Justerat slutvarv | TURN / OUTBOUND / TURN / INBOUND |
| --- | ---: | --- | --- |
| 6:00 | 1 | Inget | Standard: 2:00 / 1:00 / 2:00 / 1:00 |
| 12:00 | 2 | Inget | Standard: 2:00 / 1:00 / 2:00 / 1:00 |
| 18:00 | 3 | Inget | Standard: 2:00 / 1:00 / 2:00 / 1:00 |
| 11:00 | 1 | 5:00 | 2:00 / 0:30 / 2:00 / 0:30 |
| 13:21 | 1 | 7:21 | 2:00 / 1:40 / 2:00 / 1:41 |
| 12:20 | 1 | 6:20 | 2:00 / 1:10 / 2:00 / 1:10 |

För varje giltig plan gäller exakt:

`full_holds * 360 + sum(final_phases) == sum(all_phases) == T`

De tidigare JSON-fälten `remaining_time_seconds` och
`final_hold_adjustment_seconds` finns kvar. Det första betyder nu hela det
flygbara justerade slutvarvet, inte den obehandlade divisionsresten. Justeringen
är slutvarvets längd minus 360; positivt betyder längre, negativt kortare.

## Fasordning och tidsreferens

Fasordningen var inte definierad i föregående implementation. Följande ordning
är nu explicit implementerad enligt begäran:

`Marshal Crossing → TURN 1 (LEFT 180°, 2:00) → OUTBOUND → TURN 2 (LEFT 180°, 2:00) → INBOUND → Marshal`

Alla fulla standardhold flygs först, sedan det eventuella justerade slutvarvet.
Efter INBOUND börjar nästa varvs TURN 1 direkt, eller COMMENCE om EAT nåtts.
Det finns ingen extra fas mellan varven. CURRENT skiljer TURN 1 från TURN 2.
NEXT visar LEFT 180° när nästa fas är någon av svängarna.

Exempel med 13:21 totalt, tider relativt crossing:

| Start–slut | Fas |
| --- | --- |
| 0:00–2:00 | Standardhold TURN 1 |
| 2:00–3:00 | Standardhold OUTBOUND |
| 3:00–5:00 | Standardhold TURN 2 |
| 5:00–6:00 | Standardhold INBOUND |
| 6:00–8:00 | Justerat slutvarv TURN 1 |
| 8:00–9:40 | Justerat slutvarv OUTBOUND |
| 9:40–11:40 | Justerat slutvarv TURN 2 |
| 11:40–13:21 | Justerat slutvarv INBOUND |
| 13:21 | COMMENCE |

## Nedräkning

TIME TO NEXT beräknas vid varje uppdatering som den aktuella fasens absoluta
sluttid minus aktuell lokal systemtid. Faser använder intervallet
`start <= now < end`, så exakt på en fasgräns visas den nya fasen.
TIME TO COMMENCE beräknas separat från EAT minus aktuell tid.

Det finns ingen nedräkningsvariabel som minskas vid polling och inga
schemalagda fas-events. Plan/timeline är rena härledningar av sessionens två
tidsstämplar och skapas för aktuell snapshot. Polling fortsätter var 1,5 sekund;
en försenad polling hoppar direkt till rätt fas, utan ackumulerad drift.

Vid och efter EAT visar båda timers 00:00, NEXT är COMMENCE och aktuell fas
är tom. Klockstatus är fortfarande ON TIME vid EAT och LATE efteråt. Planen
finns kvar för inspektion tills reset, men ingen hold-timer fortsätter bakåt.

## Full reset

`clear case three`, `clear case 3`, `reset case three` och motsvarande säkra
case tree/free/III- samt this three/3-alias använder samma reset-funktion som
POST `/api/case3/reset`.

Reset tömmer EAT och crossing. Därmed blir timeline tom och alla härledda
plan-, fas-, justerings- och timerfält null. Status blir READY. Den gemensamma
reset-funktionen sätter vyn till CASE III och ökar state-revisionen så att
webbsidan uppdateras. Inget gammalt fas-event finns att avbryta eller återuppta.
Det gäller även efter upprepade reset eller om reset körs från NOTES-vyn.

Notes inklusive historik, NIGHT/DAY och PTT/STT-inställningar bevaras.
`clear` fortsätter enbart rensa notes. `note clear case three` är fortfarande
en vanlig note. Matchade reset-kommandon konsumeras av befintlig router.

Direkt efter reset kan `EAT three two` följt av `marshal` skapa en ny plan.
Ändrad EAT eller ny crossing räknar också om hela tidslinjen från aktuella värden.

## Filer och restore point

Ändrade källfiler:

- `src/dcs_ai_copilot/case3.py`: heltalsalgoritm, HoldPhase, absolut timeline,
  fasuppslag, utökade JSON-fält, READY och stoppade timers vid EAT.
- `src/dcs_ai_copilot/web/case3_ui.py`: flygbar slutplan, benlängder, CURRENT,
  NEXT och TIME TO NEXT i befintligt NIGHT/DAY-tema.
- `src/dcs_ai_copilot/kneeboard/state.py`: gemensam reset med CASE III-vy.
- `src/dcs_ai_copilot/voice/router.py`: endast nya clear/reset-matchningar och
  anrop till gemensam reset. Övriga aliases och EAT-parsing bevaras.
- `src/dcs_ai_copilot/web/server.py`: API-reset använder samma funktion;
  kommunikationsfel tömmer även visade fas-/NEXT-fält.

Tester/dokumentation:

- Ny `tests/test_case3_timeline.py`: 11 tester, varav ett testar 3 361
  sekundvärden från 4:00 till 60:00.
- `tests/test_case3.py`: gammal reset-förväntan uppdaterad till aktiv CASE III.
- `tests/test_case3_api.py`: utökad kontroll av tomt READY-state efter API-reset.
- Ny `docs/CASE3-HOLD-TIMELINE.md`: denna rapport.
- `docs/CASE3-PHASE1.md`: märkt som historisk rapport med hänvisning hit.

Backup av berörda befintliga filer före ändring:
`I:\Codex\DCS-AI-Copilot-backup-hold-timeline-20260914-082417`.
Tidigare lokala ändringar har behållits. PTT, audio capture, STT-providers,
note-lagring, koordinatparser och DCS-BIOS har inte ändrats i detta arbete.

## Testresultat och praktisk verifiering

`python -m unittest discover -s tests -q`: **104 tester OK**.
Det inkluderar de 93 tidigare testerna och 11 nya. Den enda ändrade gamla
beteendeförväntan gäller att reset nu ska aktivera CASE III i stället för NOTES.

Verifierat: alla begärda totalsummor, exakt sekundersumma, lika ben med rätt
udda sekund, inga negativa ben, tim-/dygnsgränser, 4:00 med nollånga ben,
fasövergångar inklusive 5:00/7:21-slutvarv, ojämna/omvända pollingtidpunkter,
stopp vid EAT, reset-isolation och omedelbart skapande av ny session.

Webbvyn granskades i en separat lokal testserver med syntetiska sessionsdata,
utan att använda mikrofon eller ändra en eventuell pågående flygsession.
7:21-slutvarvet och båda timers granskades visuellt vid 1280×720 och 480×640.
Vid 480×640 var innehållets mått exakt 480×640, utan scrollning. READY efter
reset verifierades visuellt, inklusive bevarat DAY-tema och tomma fasfält.

## Edge cases och nästa praktiska test

- Exakt 4:00 ger två svängar med raka ben 0:00. Nollånga ben finns i planen
  men hoppas över vid fasvisning; den andra svängen börjar direkt. Det följer
  den begärda matematiska modellen och behöver verifieras flygmässigt.
- För lite tid eller EAT före crossing ger ingen hold-plan. Vid EAT visas
  ändå COMMENCE och 00:00. Ingen automatisk flygväg eller position används.
- Lokal systemtid gäller fortfarande. DCS-paus, ändrad systemklocka och
  sommartidsomställning är inte modellerade som flygtid. Om klockan ligger före
  crossing visas ingen aktuell fas; nästa event är första svängen vid crossing.
- Polling kan göra ett visuellt fasbyte upp till ungefär ett pollingintervall
  sent. Det ger ingen ackumulerad matematisk drift. ON TIME-sekunden kan hoppas
  över mellan två pollinguppdateringar.
- Befintlig crossing registreras när det transkriberade kommandot hanteras,
  inte vid ljudinspelningens början. STT-latensen är oförändrad.
- Headsetets läsbarhet och den faktiska sväng-/Marshal-geometrin behöver
  användarens praktiska test. Ingen TTS eller automatisk DCS-position infördes.

Starta om appen på vanligt sätt. Prova EAT → marshal → clear case three →
EAT → marshal; kontrollera att gamla tider är borta och notes/tema finns kvar.
Prova därefter `clear` och verifiera att endast notes rensas.
