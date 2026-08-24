# License Help

DCS AI Copilot currently uses the MIT License in `LICENSE`.

This file is guidance for the release process. It is not legal advice.

## Common Options

- MIT: permissive, short, easy for other people to use and modify with attribution.
- Apache-2.0: permissive, with explicit patent terms.
- GPL-3.0: copyleft, distributed derivatives must also be open source.
- Custom/personal license: only use this if standard open source terms do not match what you want.

## Release Steps

1. Confirm `LICENSE` contains the MIT License text.
2. Confirm the copyright line is correct for the release owner.
3. Keep or remove `LICENSE.template.md` as you prefer, but do not treat it as the final license.
4. Run the release check:

```powershell
python main.py --release-check --release-version 2.0
```

5. Build the final release with license enforcement:

```powershell
.\packaging\windows\build_windows.ps1 -Version "2.0" -BuyMeACoffeeUrl "https://buymeacoffee.com/myriskdashk" -RequireInstaller -RequireLicense
```

## Helper Command

From source:

```powershell
python main.py --license-help
```

From the installed app:

```powershell
DCS-AI-Copilot.exe --license-help
```

## Reference

You can compare common open source licenses here:

```text
https://choosealicense.com/
```
