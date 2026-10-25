# API keys for DCS AI Copilot

This guide explains which cloud API keys DCS AI Copilot uses, where to get
them, and how to add them safely.

## Which keys do I need?

- **OpenAI API key:** required and used as the primary speech-to-text service.
- **Gemini API key:** optional. If it is configured, DCS AI Copilot can try
  Gemini when the OpenAI transcription request fails.

For the simplest setup, start with only the OpenAI key. Add Gemini later if
you want a second cloud provider as fallback.

## 1. Create an OpenAI API key

1. Open the official OpenAI API key page:
   https://platform.openai.com/api-keys
2. Sign in or create an OpenAI Platform account.
3. Create a new secret key and copy it immediately.
4. Check API billing or add credits here:
   https://platform.openai.com/settings/organization/billing/overview
5. You can later view API usage here:
   https://platform.openai.com/usage

Official OpenAI quickstart:
https://developers.openai.com/api/docs/quickstart

The API key is a secret. Do not paste it into Discord, GitHub, screenshots,
support messages or public files.

## 2. Optional: create a Gemini API key

You do not need Gemini for normal operation. It is only a fallback when both
providers are configured.

1. Open Google AI Studio:
   https://aistudio.google.com/app/apikey
2. Sign in with your Google account.
3. Create an API key and copy it.
4. Use the Billing and Usage pages in the Google AI Studio dashboard to check
   the selected project's quota and costs.

Official Gemini instructions:
https://ai.google.dev/gemini-api/docs/api-key

Official Gemini billing guide:
https://ai.google.dev/gemini-api/docs/billing

## 3. Add the keys with the setup wizard (recommended)

### Installed version

Open the Windows Start menu and choose:

```text
DCS AI Copilot > First-time Setup
```

Paste your OpenAI key when the wizard asks for `OpenAI API key`. If you also
want Gemini fallback, paste that key when it asks for
`Gemini API key, optional fallback`. Otherwise, press Enter at the Gemini
question.

### Portable version

Open PowerShell in the extracted DCS AI Copilot folder and run:

```powershell
.\DCS-AI-Copilot.exe --setup
```

### Running from source

Open PowerShell in the project folder and run:

```powershell
python main.py --setup
```

The setup wizard stores the keys locally in `.env`. DCS AI Copilot does not
store them in `config.ini`.

## 4. Manual setup (optional)

Use this only if you do not want to run the setup wizard.

1. Copy `.env.example` to `.env` in the same folder as DCS AI Copilot.
2. Open `.env` in Notepad.
3. Enter the keys without quotation marks:

```text
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_optional_gemini_key_here
```

If you do not want Gemini fallback, leave its value empty:

```text
GEMINI_API_KEY=
```

Never rename `.env` to `.env.txt`. In File Explorer, enable **File name
extensions** if you are unsure.

## 5. Check the setup

For an installed version, open:

```text
DCS AI Copilot > Check Installation
```

For the portable version:

```powershell
.\DCS-AI-Copilot.exe --doctor
```

For source:

```powershell
python main.py --doctor
```

The report should show that the OpenAI API key is present. If Gemini fallback
is enabled, it should also show that the Gemini key is present.

## How fallback works

1. DCS AI Copilot sends the released PTT recording to OpenAI first.
2. If OpenAI succeeds, Gemini is not called.
3. If OpenAI fails and a Gemini key is configured, the same recording is sent
   to Gemini.

Both services are cloud APIs. No local language model is installed and no GPU
is used for transcription.

## Common problems

### `insufficient_quota` or billing error

The key was accepted, but the provider account has no usable quota or billing
is not active. Open the provider's Billing and Usage pages and check the
project connected to that key.

### The key is present but transcription still fails

Run **Check Installation**, then check `LAST ERROR` on the dashboard. Also
confirm that you copied the complete key without spaces before or after it.

### A key was accidentally shared

Delete or revoke that key immediately on the provider's API key page, create a
new one, and run **First-time Setup** again.
