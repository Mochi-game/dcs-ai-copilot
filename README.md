# DCS AI Copilot

En mycket lätt första grund för en framtida AI-copilot till DCS World F/A-18C, optimerad för VR och multiplayer.

Den här milstolpen gör bara detta:

- Startar en lokal OpenKneeboard Web Dashboard på `http://127.0.0.1:8765`.
- Läser koordinatrader från terminalen.
- Tolkar target-koordinater och elevation till strukturerad data.
- Visar fångade koordinater i webbsidan.
- Lyssnar read-only på DCS-BIOS exportström för några F/A-18C-värden.
- Spelar in mikrofonljud medan F13 hålls nere och transkriberar via OpenAI.
- Kan använda fysisk joystick/DirectInput-knapp som primär PTT. För WINWING F18 TAKEOFF PANEL 2 används Windows WinMM-läsning när pygame inte exponerar panelen.
- Kan spara enkla röstanteckningar som börjar med `note`.
- Skapar eller uppdaterar `kneeboard.html` som enkel filfallback.
- Loggar till `logs/dcs-ai-copilot.log`.

Den här milstolpen gör inte detta:

- Ingen lokal AI-modell.
- Ingen GPU-användning.
- Ingen cockpit-command/write-integration.
- Ingen SRS- eller Discord-integration.
- Ingen läsning av dold multiplayerinformation eller serverdata.

Public safety summary:

- No local AI model or GPU inference is used.
- DCS-BIOS is read-only.
- No cockpit commands are sent.
- No hidden multiplayer or server data is read.
- No DCS graphics, OpenXR, PimaxXR, QuadViews or Pimax Play settings are changed.

## License

DCS AI Copilot is released under the MIT License. See `LICENSE`.

## Krav

- Windows
- Python 3.11 eller senare
- OpenAI API-nyckel för rösttranskribering
- Valfri Gemini API-nyckel om du vill ha Gemini som fallback när OpenAI inte kan transkribera
- VR-plattform/headsetval under setup, till exempel OpenXR/Pimax, OpenXR/annan, SteamVR, Oculus, annan eller ingen VR

Testat lokalt med Python 3.13.2.

## Installera dependencies

Från projektmappen:

```powershell
Set-Location C:\Projects\DCS-AI-Copilot
python -m pip install -r requirements.txt
```

Installerade direkta dependencies:

```text
openai
sounddevice
pynput
pygame
google-genai
```

## OpenAI API-nyckel

Lägg nyckeln i `.env`:

```powershell
Set-Location C:\Projects\DCS-AI-Copilot
Copy-Item .env.example .env
notepad .env
```

Fyll i:

```text
OPENAI_API_KEY=din_api_nyckel_har
GEMINI_API_KEY=din_gemini_nyckel_har
```

Gemini-raden är valfri. Nycklar ska inte hårdkodas i Python-filer. `.env` ligger i `.gitignore`.

## Starta terminaltestet

Öppna PowerShell och kör:

```powershell
Set-Location C:\Projects\DCS-AI-Copilot
python main.py
```

För första konfiguration på en ny dator:

```powershell
python main.py --setup
```

Guiden frågar efter DCS World-installationsmapp, DCS Saved Games, VR-plattform/headset, OpenAI API-nyckel, valfri Gemini API-nyckel för fallback, PTT-val, joystick och valfri Buy Me a Coffee-länk. VR-valet används bara för hjälptext; appen ändrar aldrig OpenXR, SteamVR, Oculus, PimaxXR, QuadViews, Pimax Play eller DCS grafikinställningar.

Kontrollera installationen:

```powershell
python main.py --doctor
```

`--doctor` visar vad som är OK, vad som saknas, och exakt nästa åtgärd för exempelvis OpenAI API key, OpenKneeboard, DCS-BIOS och Python dependencies.
Den varnar också om DCS World-installationsmappen saknas eller inte ser ut att innehålla `DCS.exe`.

Lista mikrofoner och andra ljudingångar:

```powershell
python main.py --diagnose-audio
```

Om Windows standardmikrofon inte är rätt kan du sätta `input_device` i `config.ini` till indexet eller exakt namn från diagnostiken:

```ini
[voice]
input_device = 2
```

Programmet fortsätter köra och visar:

```text
URL: http://127.0.0.1:8765
```

Röststyrning med primär joystick-PTT:

```text
Håll WINWING F18 TAKEOFF PANEL 2 `JOY_BTN1` / `Button 1` nedtryckt, tala koordinaten, släpp knappen.
```

Keyboard fallback:

```text
Håll F13 nedtryckt, tala koordinaten, släpp F13.
```

Exempel att säga:

```text
target north 42 15.732 east 041 38.219 elevation 428
```

Röstanteckningar:

```text
note tanker tacan 12 x fuel 4200
note attack heading 270 push time 15
notera bingo fuel 3500
anteckna bingo fuel 3500
```

De visas som:

```text
NOTE 1
tanker tacan 12 x fuel 4200
```

Dashboarden visar de 6 senaste anteckningarna. Äldre anteckningar behålls i sessionens historik och räknas som `OLDER NOTES IN HISTORY`.

I OpenKneeboard:

1. Lägg till en Web Dashboard.
2. Använd URL:

```text
http://127.0.0.1:8765
```

Skriv sedan:

```text
target north 42 15.732 east 041 38.219 elevation 428
```

Web Dashboard-sidan uppdaterar sig själv automatiskt. Programmet skapar även eller uppdaterar:

```text
kneeboard.html
```

Förväntat innehåll på kneeboard-sidan:

```text
TARGET 1
N42°15.732'
E041°38.219'
ELEV 428 FT
```

## DCS-BIOS read-only

Programmet försöker automatiskt hitta DCS-BIOS i:

```text
%USERPROFILE%\Saved Games\DCS\Scripts\DCS-BIOS
%USERPROFILE%\Saved Games\DCS.openbeta\Scripts\DCS-BIOS
```

Det lyssnar read-only på DCS-BIOS exportström:

```text
239.255.50.10:5010
```

Det skickar inga DCS-BIOS-kommandon till DCS.

Dashboarden visar:

- anslutningsstatus
- om DCS-BIOS-installation hittades
- aktuell aircraft/module
- Master Arm
- COMM1/COMM2 display
- COMM1/COMM2 frekvens om DCS-BIOS-reference finns

## Rösttranskribering

Röstinmatning använder OpenAI Audio Transcriptions API via OpenAI Python SDK:

```text
client.audio.transcriptions.create(...)
model = gpt-4o-mini-transcribe
```

Om Gemini fallback är aktiverad används OpenAI först. Om OpenAI-anropet misslyckas, till exempel på grund av quota/billing/rate limit, provas Gemini via Google GenAI SDK:

```text
model = gemini-2.5-flash
```

Gemini får samma korta WAV-klipp som OpenAI. Ingen lokal AI-modell eller GPU används.

Ljud spelas in lokalt som 16 kHz mono PCM/WAV endast medan PTT är aktiv. Max inspelningstid är 20 sekunder.

### API usage och kostnad

Varje PTT-inspelning som släpps leder normalt till ett OpenAI-transkriberingsanrop. Om OpenAI misslyckas och Gemini fallback är aktiverad kan samma inspelning också göra ett Gemini-anrop. Kostnaden är alltså inte bara "per knapptryck" utan beror på provider, modell och hur mycket ljud/text som behandlas.

OpenAI usage/kostnad ses i OpenAI Platform dashboard och via OpenAI Usage/Costs API. Gemini usage/kostnad ses i Google AI Studio/Google Cloud billing. Kontrollera alltid aktuell prissida hos respektive provider innan publicering.

Dashboarden visar:

- `VOICE STATUS`
- `PTT MODE`
- joystick-status och knappnummer
- `LAST TRANSCRIPT`
- `LAST ERROR`
- en tydlig `RECORDING`-indikator medan PTT hålls nere

## Joystickdiagnostik

Lista hittade joystick-enheter och se knapptryckningar live:

```powershell
Set-Location C:\Projects\DCS-AI-Copilot
python main.py --diagnose-joysticks
```

Diagnostiken visar både pygame-enheter och Windows WinMM-enheter. Standardläget visar bara knapptryckningar så brus från joystick-axlar inte fyller terminalen. Om du behöver se axlar senare kan du köra:

```powershell
python main.py --diagnose-joysticks --diagnose-joystick-axes
```

På vissa WINWING-paneler syns `WINWING F18 TAKEOFF PANEL 2` i Windows testpanel men inte som egen pygame-enhet. Då ska du titta efter rader som börjar med `WINMM`.

Tryck på `Button 1` på `WINWING F18 TAKEOFF PANEL 2`. För `JOY_BTN1` / `Button 1` förväntas normalt:

```text
button=0
```

Exempel på rätt signal:

```text
WINMM DOWN device=4 name=MS-drivrutin för PC-spelenhet button=0
WINMM UP device=4 name=MS-drivrutin för PC-spelenhet button=0
```

Device-id kan vara ett annat nummer på en annan dator. Använd det id som diagnostiken visar.

Avsluta diagnostiken med `Ctrl+C`.

Aktuell standardkonfiguration:

```ini
ptt_mode = joystick
keyboard_ptt_key = f13
joystick_backend = winmm
joystick_name = WINWING F18 TAKEOFF PANEL 2
joystick_button = 0
joystick_winmm_device_id = auto
```

Om diagnostiken visar rätt panel men auto-valet inte fungerar kan du låsa WinMM-device-id manuellt:

```ini
joystick_winmm_device_id = nytt_id
```

Om dashboarden visar `INSTALL NOT FOUND` behöver DCS-BIOS installeras i Saved Games innan cockpitdata kan visas.

## Kör tester

Från projektmappen:

```powershell
python -m unittest discover -s tests
```

## Backup och avinstallation

Backup av DCS Saved Games till annan disk:

```powershell
python main.py --backup-dcs E:\DCS-Backups
```

Visa avinstallationshjälp:

```powershell
python main.py --uninstall-help
```

Visa hjälp för licensval innan GitHub-publicering:

```powershell
python main.py --license-help
```

Visa installationshjälp utan att skriva om config:

```powershell
python main.py --setup-help
```

Kontrollera om projektet är redo för publik GitHub-release:

```powershell
python main.py --release-check --release-version 0.1.0
```

Kontrollen stoppar om exempelvis `LICENSE`, Buy Me a Coffee-länk, releasefiler eller säkerhetstexter saknas.

## Installer och publicering

Underlag för Windows-build finns i:

```text
packaging/windows/
```

Portable ZIP-builden innehåller även:

```text
Install-DCS-AI-Copilot.ps1
Uninstall-DCS-AI-Copilot.ps1
```

De installerar/avinstallerar per Windows-användare utan admin.

Användarguide och publiceringschecklista finns i:

```text
docs/USER_SETUP_GUIDE.md
docs/PUBLISHING_CHECKLIST.md
docs/LICENSE_HELP.md
```

Kör release-kontrollen innan du taggar eller laddar upp filer:

```powershell
DCS-AI-Copilot.exe --release-check --release-version 0.1.0
```

Kör även smoke-test på den byggda ZIP:en och portable-installeraren:

```powershell
.\packaging\windows\Test-Release-Smoke.ps1 -Version "0.1.0"
```

När `LICENSE` och Buy Me a Coffee-länk är klara kan final release-helpern köra tester, build och release-check i följd:

```powershell
.\packaging\windows\Prepare-GitHub-Release.ps1 -Version "0.1.0" -BuyMeACoffeeUrl "https://buymeacoffee.com/myriskdashk" -GitHubUser "YOUR_GITHUB_USER"
```

Förbered lokal Git-commit och tagg när GitHub-repot finns:

```powershell
.\packaging\windows\Prepare-Local-Git-Repository.ps1 -Version "0.1.0" -GitUserName "YOUR_GIT_NAME" -GitUserEmail "YOUR_GIT_EMAIL" -GitHubUser "YOUR_GITHUB_USER"
```

När GitHub Actions har `Read and write permissions` kan en ny GitHub Release skapas automatiskt genom att pusha en ny versionstagg:

```powershell
git tag v0.1.1
git push origin main
git push origin v0.1.1
```

## Dependencies

Externa Python-paket finns i `requirements.txt`:

```text
openai
sounddevice
pynput
pygame
google-genai
```

## Projektstruktur

```text
main.py
config.ini
src/
  dcs_ai_copilot/
    ai/
    dcs/
    dcs_bios/
    kneeboard/
    web/
    voice/
tests/
```
