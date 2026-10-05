# CASE III fas 1 — implementationsrapport

Historisk rapport för första implementationen. Hold-algoritmen, fasnedräkningen
och reset-beteendet har därefter ersatts enligt [CASE3-HOLD-TIMELINE.md](CASE3-HOLD-TIMELINE.md).

Implementerat 2026-09-13 i `I:\Codex\DCS-AI-Copilot`, inklusive NIGHT/DAY-tillägget.

## Inventering och restore point

Före ändring passerade 71 unittest-tester. Projektet hade redan lokala ändringar
i start/stopp-skript, state, notes, PTT och PTT-tester samt två nya VBS-filer.
Dessa ändringar bevarades.

Restore point: `I:\Codex\DCS-AI-Copilot-backup-20260913-133944`.
Den innehåller befintliga Git-spårade och icke-ignorerade filer, inklusive lokala
ändringar, samt `HEAD.txt` och `working-tree.patch`. Ignorerade runtimefiler,
hemligheter, byggmiljö och distributionsfiler ingår inte. Inga sådana inställningar
behöver återställas för att backa kodändringen. Återställ berörda källfiler från
backupens motsvarande sökvägar, med appen stoppad; använd inte `git reset --hard`
eftersom det skulle förlora tidigare lokala ändringar.

## Befintlig arkitektur

- `main.py` skapar gemensamt state, HTTP-server, befintlig DCS-BIOS-läsare och PTT.
- PTT: WinMM-joystick, knapp 0, med F13 som tangentbordsreserv. Inspelning sker
  under nedtryckt knapp, högst 20 sekunder enligt befintlig konfiguration.
- Efter släpp transkriberar en bakgrundstråd ljudet med befintlig OpenAI-provider
  och Gemini som reserv. Provider, prompt och ljudhantering är oförändrade.
- Tidigare parserordning: rensa notes → note-parser → koordinatparser.
- Notes lagras i minnet; de sex senaste visas med räknare för äldre notes.
  Befintlig renderer skriver dessutom en statisk `kneeboard.html`.
- Befintlig Python HTTPServer kör på `127.0.0.1:8765`. Webbsidan pollar
  `/api/state` var 1,5 sekund. Denna server, port och mekanism återanvänds.

## Ändrade filer i detta arbete

| Fil | Förändring |
| --- | --- |
| `src/dcs_ai_copilot/kneeboard/state.py` | Separat Case3State, aktiv vy och gemensamt tema. NOTES/NIGHT vid start. Utökat JSON-state. |
| `src/dcs_ai_copilot/voice/ptt.py` | Router direkt efter STT. Notes återanvänder befintlig lagring, felhantering och rendering; koordinater fortsätter som fallback. |
| `src/dcs_ai_copilot/web/server.py` | Case III- och tema-API samt infogning av separat UI i befintlig sida. NIGHT-färger för NOTES. |
| `src/dcs_ai_copilot/kneeboard/renderer.py` | Endast bakgrund/textfärg i statisk note-export ändrade till NIGHT. |
| `kneeboard.html` | Befintlig genererad/ignorerad fil fick samma NIGHT-färger; innehållet behölls. |

`main.py`, konfiguration, start/stopp-skript, `voice/notes.py`, STT, ljud och
DCS-BIOS ändrades inte av detta arbete. Deras tidigare Git-diffar kan därför
fortfarande synas i arbetskopian.

## Nya filer

| Fil | Syfte |
| --- | --- |
| `src/dcs_ai_copilot/case3.py` | Testbar datetime/timedelta-matematik, EAT-upplösning och trådsäkert sessionsstate. |
| `src/dcs_ai_copilot/voice/router.py` | Deterministisk routing och tillämpning av vy-, tema- och Case III-kommandon. |
| `src/dcs_ai_copilot/web/case3_ui.py` | CASE III-layout, CSS-variabler för båda teman och rendering från befintlig polling. |
| `tests/test_case3.py` | Matematik, parser, isolation och integration genom transkriptionskedjan. |
| `tests/test_case3_api.py` | API-flöde, validering, cross-origin-avvisning och temabevarande. |
| `docs/CASE3-PHASE1.md` | Denna rapport. |

## Tidsmodell

Alla tider är lokal systemtid med hela sekunder. Ingen DCS-missionstid används.
EAT / command time är alltid på hel minut, med sekunder och mikrosekunder noll
internt. EAT visas som `HH:MM`; marshal crossing visas fortsatt som `HH:MM:SS`.
Exempel: EAT `13:32` (= 13:32:00) minus crossing `13:20:20` ger `11:40`.
`eat 32` väljer närmast kommande :32 i aktuell/nästa timme.
`eat 1432` väljer 14:32 idag eller nästa dygn om tiden redan passerat.
Exakt aktuell minut vid sekund 00 behålls; vid sekund 01 är :00 passerat.

Planen är låst till registrerad crossing: EAT minus crossing delas i hela
6-minutersvarv plus ett eventuellt sista delvarv. Exempel 13:20:20 → 13:32:00:
11:40 totalt = 1 helt hold + sista hold 5:40. Justeringen gäller endast detta
sista delvarv: 20 sekunder mindre än ett standardvarv på 6:00. Ett exakt antal
hela varv ger FINAL HOLD 0:00 och ingen justering. Crossing efter EAT ger noll
varv och tydlig text om missad EAT, aldrig ett negativt antal varv.

Nedräkningen beräknas separat från aktuell tid vid varje polling, även när
state-revisionen är oförändrad. Planen räknas inte automatiskt ned i antal varv.
Registrera en ny crossing manuellt för att få en ny plan från den tidpunkten.

EARLY betyder aktuell systemtid före EAT, ON TIME exakt EAT-sekunden och LATE
efter EAT. Detta är en klockjämförelse, inte en bedömning av flygprofilen. Polling
var 1,5 sekund kan passera den enskilda ON TIME-sekunden mellan uppdateringar.
Backend returnerar också `status_text` för framtida TTS-användning.

## Kommandon

| Säg | Resultat |
| --- | --- |
| `note <text>` | Skapar note med befintlig parser; Case III-ord inuti texten är vanlig note-text. |
| `notes`, `show notes`, `back to notes` | Visar NOTES. |
| `case three`, `case 3`, `show case three` | Visar CASE III. Även CASE III-stavning och avslutande interpunktion tolereras. |
| `eat three two`, `eat 32` | Nästa rimliga :32. |
| `eat one four three two`, `eat 1432`, `eat 14:32` | Nästa 14:32. |
| `marshal crossing now`, `crossing marshal now`, `marshal now` | Registrerar lokal systemtid. Även marshall-stavning tolereras. |
| `case three status` | Öppnar CASE III med aktuell status. |
| `reset case three` | Tömmer bara Case III-sessionen. Notes och tema behålls. |
| `day mode`, `night mode` | Byter gemensamt tema utan att byta vy. |

Tidigare note-alias och rensningskommandon fungerar fortsatt. Matchningen
normaliserar kommandon, men ändrar inte note-innehållet utöver legacy-parsern.

## API

GET `/api/state` innehåller befintliga fält plus `active_view`, `theme` och `case3`.
GET `/api/case3` returnerar enbart Case III-state.

POST kräver `Content-Type: application/json`:

| Endpoint | JSON-kropp |
| --- | --- |
| `/api/view` | `{"view":"notes"}` eller `{"view":"case3"}` |
| `/api/theme` | `{"theme":"night"}` eller `{"theme":"day"}` |
| `/api/case3/eat` | `{"eat":"32"}` eller `{"eat":"1432"}` |
| `/api/case3/crossing` | `{}` |
| `/api/case3/reset` | `{}` |

Ogiltiga värden ger HTTP 400 och ingen mutation. POST stöder inte godtycklig
crossing-tid; använd lokal systemtid enligt fas 1. Servern förblir loopback-only.

## Testresultat och visuell kontroll

`python -m unittest discover -s tests -q`: **85 tester OK** (71 befintliga + 14 nya).
`git diff --check`: inga whitespace-fel; Git visar befintliga LF/CRLF-varningar.

A: 13:20:20 → 13:32:00 = 11:40, 1 helt hold + 5:40.
B: 13:58 → 14:04 = 6:00.
C: 23:58 → 00:04 nästa dygn = 6:00.
D–H: exakt note-regression, vybyte åt båda håll, talad EAT och marshal crossing
passerar. Testerna går även genom PTT-tjänstens transkriptionshanterare med en
simulerad STT-provider. Ingen extern AI behövs för testning eller Case III-logik.

Appen startades med `python main.py` och befintlig konfiguration på port 8765.
WinMM-joystick rapporterade READY. Webbläsaren verifierade NIGHT vid start,
CASE III med nedräkning, DAY i båda vyer, NIGHT igen och NIGHT efter omladdning.
CASE III granskades vid 1280×720 och 480×640 och rymdes utan scrollning.
NOTES behåller sin tidigare layout och scrollbeteende.

Ingen vit flash observerades. NIGHT finns i inbyggd CSS före JavaScript, utan
extern stilmall, och vybyten sker genom att visa/dölja innehåll på samma sida.
Nedräkningen markeras otillgänglig om servern inte kan nås.

## Starta och testa manuellt

Kör från PowerShell, med eventuell äldre instans stoppad:

```powershell
Set-Location -LiteralPath 'I:\Codex\DCS-AI-Copilot'
python main.py
```

Låt terminalen vara öppen. Öppna `http://127.0.0.1:8765` som befintlig webbsida
i OpenKneeboard. Avsluta med `quit` i terminalen eller Ctrl+C. Befintliga
startskript har inte ändrats; detta är det startkommando som verifierades här.

Håll inne din vanliga PTT, säg ett kommando, släpp och invänta transkriberingen:

1. Start: NOTES i NIGHT.
2. `note test note`: NOTE med texten `test note` ska visas.
3. `case three`: samma webbsida visar mörk CASE III.
4. `eat three two`: EAT blir nästa :32 enligt din lokala systemtid.
5. `marshal crossing now`: crossing visas och hold-plan beräknas.
6. `case three status`: aktuell Case III-status visas.
7. `notes`: noten finns kvar och temat är fortfarande NIGHT.
8. `day mode`: NOTES blir ljust beige, inte kritvitt.
9. `case three`: CASE III behåller DAY.
10. `night mode`: CASE III blir mörk igen.
11. `notes`: NOTES behåller NIGHT. Ingen vit mellanbild ska synas vid vybyte.
12. `note tanker twenty miles north`: texten ska vara `tanker twenty miles north`.
13. `reset case three`: Case III-tider töms; återgå till NOTES och kontrollera
    att båda vanliga notes finns kvar.

## Kvarvarande begränsningar

Riktig mikrofontranskribering, fysisk PTT-användning och Pimax/OpenKneeboard-
rendering måste verifieras av användaren. Browser- och simulerade STT-tester
kan inte verifiera ljudigenkänning eller headsetets upplevda ljusstyrka.

Session och tema ligger i minnet. Vybyte och browser-refresh behåller temat;
omstart av processen ger NOTES/NIGHT och en tom session. Den statiska HTML-
exporten är NIGHT; live vy- och temaväxling använder webbadressen ovan.
Fas 1 förutsätter normal lokal väggklocka; manuella systemklockändringar och
sommartidsomställning under en session modelleras inte som flygtid.

Ingen ny extern dependency, flygdatakoppling, extern Case III-AI eller TTS
har införts. Stanna vid denna fas tills användaren har verifierat resultatet.
