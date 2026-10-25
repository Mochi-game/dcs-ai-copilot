# Microphone setup on Windows

DCS AI Copilot selects its own recording input. Changing it does **not**
change the Windows default microphone, SRS, Discord, DCS, OpenXR or VR
settings.

## Select a microphone in the dashboard

1. Start DCS AI Copilot.
2. Open `http://127.0.0.1:8765` in a browser, or open its existing
   OpenKneeboard Web Dashboard page.
3. In the `VOICE` section, open the microphone list.
4. Select the physical input you want, for example a Pimax microphone, USB
   headset or webcam microphone.
5. Press **Use microphone**. The new input is validated and becomes active
   for the next PTT recording; no restart is normally required.
6. Hold PTT and confirm that the page shows `RECORDING`.
7. Say a short test such as **“NOTE microphone test”**, release PTT, and check
   `LAST TRANSCRIPT` and `LAST ERROR`.

The selection is saved in `config.ini` under `[voice] input_device` as the
device name together with its Windows host API, for example:

```ini
[voice]
input_device = Microphone (example headset), Windows WASAPI
```

An empty value, or **Windows default microphone** in the dashboard, uses the
current Windows default input. The UI does not depend on a hard-coded device
index. A numeric index is still accepted for manual configuration, but it can
change after reconnecting USB devices and is therefore less robust.

## MME, DirectSound, WASAPI and WDM-KS

Windows may expose one physical microphone several times through different
audio host APIs:

- `MME`: older, broadly compatible Windows path.
- `Windows DirectSound`: another compatibility path.
- `Windows WASAPI`: newer Windows audio path.
- `Windows WDM-KS`: low-level driver path; not usually the first choice for
  troubleshooting.

There is no rule that every system must use MME. Select the entry with the
correct physical device name, apply it, and make the short PTT test above.
If one host API fails at 16 kHz mono, try another entry for the same physical
microphone. Keep the one that records reliably.

## Recognize common devices

- **VR/Pimax:** usually contains `Pimax` in its name. `Pimax AirLink` may be a
  separate device; choose the one that corresponds to the connection in use.
- **Headset microphone:** often includes the headset or USB adapter name,
  such as Jabra, SteelSeries or Logitech.
- **Webcam microphone:** commonly includes the webcam model, for example
  `HD Pro Webcam C920`; do not choose it merely because Windows made it the
  default.
- **USB microphone:** normally contains the manufacturer/model or `USB
  Audio`.
- **Bluetooth:** choose an input/headset profile, not a stereo output. Windows
  can rename or switch the profile when the microphone becomes active.

The `MICROPHONE` line in VOICE shows the input Copilot actually selected.

## List devices without recording

Press the refresh arrow beside the microphone selector. It asks the running
app to enumerate inputs again without starting a recording.

For a terminal list, run one of these from the project folder:

```powershell
python main.py --diagnose-audio
```

or, in a source installation that uses the build environment:

```powershell
.\.build-venv\Scripts\python.exe main.py --diagnose-audio
```

The diagnostic shows input-capable devices, their current indexes and the
Windows default. It does not record audio.

## If a selected microphone is disconnected

There is **no automatic fallback** to another microphone. This avoids silently
recording the wrong room or device. A disconnected or renamed input can make
the next recording fail and put the reason in `LAST ERROR`.

Reconnect the same device, or select another microphone and press **Use
microphone**. If a newly connected device does not appear after refresh,
restart only DCS AI Copilot with the device connected; the underlying
PortAudio device list can remain cached for the running process.

## Troubleshooting

### Microphone is not listed

1. Check that Windows sees and enables it under **Settings > System > Sound >
   Input**.
2. Press the dashboard refresh button.
3. Run `python main.py --diagnose-audio`.
4. If still missing, connect/power the device first and restart Copilot.

### Wrong microphone is used

Do not rely on **Windows default microphone**. Select the exact physical name
and host API, press **Use microphone**, and verify the `MICROPHONE` line. A
webcam is a common accidental default.

### It works in Windows but not in Copilot

- In **Settings > Privacy & security > Microphone**, allow microphone access
  and allow desktop apps to access it.
- Check the Windows input-level meter and input volume.
- Make sure another program has not taken exclusive control of the device.
- Try another host-API entry for the same microphone.
- Read `LAST ERROR`; an unsupported 16 kHz mono format is detected when you
  apply the selection.

### PTT works but nothing is transcribed

- Confirm `RECORDING` appears while PTT is held and disappears immediately on
  release.
- Speak only after `RECORDING` is visible, then release after the full phrase.
- Check `LAST ERROR` for missing API key, quota/billing, network or provider
  errors. Speech-to-text happens in the cloud after release.
- A full transcription queue reports VOICE BUSY; wait for pending clips to
  drain and try again.

### The transcript contains wrong words or numbers

- Move the microphone closer, reduce fan/cockpit background noise and speak
  digits distinctly.
- Use the tested command vocabulary in
  [VOICE-COMMANDS.md](VOICE-COMMANDS.md).
- Inspect `LAST TRANSCRIPT` before assuming the command parser failed.
- Short clipped speech often means speaking before recording began or
  releasing PTT too early.

### Bluetooth profile changes

Windows can replace a high-quality playback profile with a headset/hands-free
profile when the microphone opens. Re-open the selector and choose the input
profile that is currently listed. If its name changed, the old saved name will
not fall back automatically.

### USB index changed after reconnect

Dashboard selections are stored by exact name + host API and normally survive
an index change. A manually configured numeric index may point to a different
device after reconnect; replace it through the dashboard or use the exact
name shown by diagnostics.
