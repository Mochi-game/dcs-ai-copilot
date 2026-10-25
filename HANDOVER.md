# HANDOVER.md — DCS AI Copilot

## Version 4.0.0

This release packages the current microphone selector, voice reliability,
background startup and concurrent local-dashboard fixes together with the
new pilot documentation and printable quick guide.

The microphone selector is in the dashboard's VOICE section. **Use
microphone** validates the choice, activates it for the next PTT and saves the
exact device name + Windows host API. It does not change Windows, DCS, SRS,
Discord or VR audio settings. Missing devices do not silently fall back.

Voice clips are processed in order by one bounded worker. Routing/provider
exceptions remain visible in LAST ERROR and do not kill later PTT recordings.
Saved notes are unlimited for the session; only the newest six are displayed.

## Verification

- `python -m unittest discover -s tests -q`: 168 tests passed.
- Voice, audio, microphone, HTTP concurrency, startup and CASE III tests are
  included in that suite and use fake providers.
- Printable guide: three A4 pages, visually reviewed.
- No paid speech request or DCS/VR setting change is part of automated release
  verification.

## Release hygiene

The public commit must exclude `.env`, `config.ini`, runtime logs, local build
output and unrelated PDFs. GitHub's tag workflow produces the downloadable
installer and portable ZIP from a clean checkout.

## Next task

Consider a context-sensitive **SAY NOW / NEXT** panel in the
Copilot/OpenKneeboard UI. Keep it separate from the 3.0.0 release.
