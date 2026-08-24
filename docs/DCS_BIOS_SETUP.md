# DCS-BIOS Setup For DCS AI Copilot

DCS AI Copilot uses DCS-BIOS read-only to show cockpit data from the F/A-18C.
Version 2.0 still sends no cockpit commands.

Run this from the installed app:

```powershell
DCS-AI-Copilot.exe --dcs-bios-help
```

The helper shows the exact Saved Games path, DCS-BIOS folder, reference JSON folder and `Export.lua` status for that computer.

## Manual Install Summary

1. Close DCS World.
2. Download the latest release from:
   https://github.com/DCS-Skunkworks/dcs-bios/releases/latest
3. Download `DCS-BIOS_x.y.z.zip`.
4. Extract the ZIP.
5. Copy the extracted `DCS-BIOS` folder into:

```text
C:\Users\YourName\Saved Games\DCS.openbeta\Scripts
```

or:

```text
C:\Users\YourName\Saved Games\DCS\Scripts
```

6. Open or create:

```text
Scripts\Export.lua
```

7. Add this line if it is missing:

```lua
dofile(lfs.writedir() .. [[Scripts\DCS-BIOS\BIOS.lua]])
```

8. Start DCS in the F/A-18C.
9. Start DCS AI Copilot and run:

```powershell
DCS-AI-Copilot.exe --doctor
```

10. The dashboard should show Aircraft, Master Arm and COMM data when DCS-BIOS is streaming.

## Safety

DCS AI Copilot does not edit `Export.lua` automatically in version 2.0. Back up Saved Games first if you are unsure.
