from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Protocol
from urllib.parse import urlparse

from dcs_ai_copilot.kneeboard.state import KneeboardState
from dcs_ai_copilot.web.case3_ui import STYLE, HTML, SCRIPT


class LoopbackHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True
    connection_timeout = 5.0


class MicrophoneControl(Protocol):
    def list_microphones(self) -> dict[str, object]: ...
    def select_microphone(self, device: str) -> None: ...


def start_kneeboard_server(
    state: KneeboardState,
    host: str = "127.0.0.1",
    port: int = 8765,
    voice_service: MicrophoneControl | None = None,
) -> tuple[LoopbackHTTPServer, threading.Thread]:
    if host != "127.0.0.1":
        raise ValueError("web server must bind to 127.0.0.1")

    handler = build_request_handler(state, voice_service)
    server = LoopbackHTTPServer((host, port), handler)
    thread = threading.Thread(
        target=server.serve_forever,
        name="kneeboard-http-server",
        daemon=True,
    )
    thread.start()
    return server, thread


def build_request_handler(
    state: KneeboardState,
    voice_service: MicrophoneControl | None = None,
) -> type[BaseHTTPRequestHandler]:
    class KneeboardRequestHandler(BaseHTTPRequestHandler):
        server_version = "DCSAICopilot/0.1"

        def setup(self) -> None:
            super().setup()
            # Browser preconnects can open sockets without sending a request.
            self.connection.settimeout(self.server.connection_timeout)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self._send_text(render_dashboard_html(), "text/html; charset=utf-8")
                return
            if path == "/api/state":
                self._send_json(state.as_json_data)
                return
            if path == "/api/case3":
                self._send_json(state.case3.as_json_data)
                return
            if path == "/api/microphones":
                if not self._local_host():
                    self.send_error(403, "Invalid local host")
                    return
                if voice_service is None:
                    self._send_json(lambda: {"error": "Microphone selection unavailable"}, 503)
                    return
                try:
                    devices = voice_service.list_microphones()
                except Exception as exc:
                    self._send_json(lambda: {"error": str(exc)}, 503)
                    return
                self._send_json(lambda: devices)
                return
            self.send_error(404, "Not found")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path not in {"/api/view", "/api/theme", "/api/case3/eat", "/api/case3/crossing", "/api/case3/reset", "/api/voice/input"}:
                self.send_error(404, "Not found")
                return
            # Consume bounded bodies before rejecting headers; closing a Windows
            # socket with unread request data can reset it before the reply arrives.
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError("JSON body must be 1-4096 bytes")
                raw_body = self.rfile.read(length)
            except ValueError as exc:
                self._send_json(lambda: {"error": str(exc)}, 400)
                return
            # Browser mutations are same-origin JSON; keep the existing loopback scope.
            origin = self.headers.get("Origin")
            if path == "/api/voice/input" and not self._local_host():
                self.send_error(403, "Invalid local host")
                return
            if origin and origin != f"http://{self.headers.get('Host')}":
                self.send_error(403, "Cross-origin request rejected")
                return
            if self.headers.get_content_type() != "application/json":
                self.send_error(415, "Use application/json")
                return
            try:
                body = json.loads(raw_body)
                if not isinstance(body, dict):
                    raise ValueError("Expected JSON object")
                if path == "/api/voice/input":
                    device = body.get("device")
                    if not isinstance(device, str) or len(device) > 512 or any(c in device for c in "\r\n\x00"):
                        raise ValueError("device must be a microphone name")
                    if voice_service is None:
                        self._send_json(lambda: {"error": "Microphone selection unavailable"}, 503)
                        return
                    try:
                        voice_service.select_microphone(device)
                    except Exception as exc:
                        code = 400 if isinstance(exc, ValueError) else 409 if isinstance(exc, RuntimeError) else 503
                        self._send_json(lambda: {"error": str(exc)}, code)
                        return
                elif path == "/api/view":
                    view = body.get("view")
                    if not isinstance(view, str):
                        raise ValueError("view must be notes or case3")
                    state.set_view(view)
                elif path == "/api/theme":
                    theme = body.get("theme")
                    if not isinstance(theme, str):
                        raise ValueError("theme must be night or day")
                    state.set_theme(theme)
                elif path == "/api/case3/eat":
                    eat = body.get("eat")
                    if not isinstance(eat, str):
                        raise ValueError("eat must be a string: MM or HHMM")
                    state.case3.set_eat(eat)
                elif path == "/api/case3/crossing":
                    state.case3.set_crossing()
                else:
                    state.reset_case3()
            except (ValueError, UnicodeError) as exc:
                if path == "/api/voice/input":
                    self._send_json(lambda: {"error": str(exc)}, 400)
                    return
                self.send_error(400, "Invalid command", explain=str(exc))
                return
            self._send_json(state.as_json_data)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _local_host(self) -> bool:
            return self.headers.get("Host") in {
                f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}",
            }

        def _send_json(self, data_factory: Callable[[], dict[str, object]], status: int = 200) -> None:
            payload = json.dumps(data_factory(), ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_text(self, text: str, content_type: str) -> None:
            payload = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return KneeboardRequestHandler


def render_dashboard_html() -> str:
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI COPILOT</title>
  <style>
    html, body {
      margin: 0;
      min-height: 100%;
      background: var(--bg);
      color: var(--fg);
      font-family: Consolas, "Courier New", monospace;
    }
    body {
      padding: 24px;
      box-sizing: border-box;
    }
    header {
      margin-bottom: 18px;
      border-bottom: 2px solid var(--border);
      padding-bottom: 10px;
    }
    h1 {
      margin: 0;
      font-size: 30px;
      line-height: 1.1;
      letter-spacing: 0;
    }
    #status {
      margin-top: 6px;
      font-size: 14px;
      font-weight: 700;
    }
    #captures {
      display: grid;
      gap: 20px;
      margin-bottom: 28px;
    }
    .panel {
      border-top: 2px solid var(--border);
      padding-top: 14px;
      margin-top: 20px;
    }
    .panel h2 {
      margin: 0 0 12px;
      font-size: 22px;
      line-height: 1.2;
      letter-spacing: 0;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(120px, 0.9fr) minmax(120px, 1.1fr);
      gap: 8px 18px;
      font-size: 18px;
      line-height: 1.3;
      font-weight: 700;
    }
    .label {
      color: var(--muted);
    }
    .entry {
      white-space: pre-line;
      font-size: 28px;
      line-height: 1.35;
      font-weight: 700;
    }
    .empty {
      font-size: 20px;
      line-height: 1.35;
      font-weight: 700;
    }
    .recording {
      background: #b00020;
      color: #fff;
      padding: 3px 8px;
      display: inline-block;
      font-weight: 900;
    }
    .transcript {
      overflow-wrap: anywhere;
    }
    .grid > div { min-width: 0; overflow-wrap: anywhere; }
    .mic-controls { display: grid; grid-template-columns: minmax(0, 1fr) auto 42px; gap: 8px; margin: 12px 0; }
    .mic-controls select {
      min-width: 0; max-width: 100%; width: 100%;
    }
    .mic-controls select, .mic-controls button {
      background: var(--bg); color: var(--fg); border: 1px solid var(--border);
      border-radius: 4px; padding: 8px; min-height: 42px;
      font: inherit; font-size: 16px; letter-spacing: 0;
    }
    .mic-controls button { cursor: pointer; }
    .mic-controls :disabled { opacity: 0.55; cursor: default; }
    .mic-controls :focus-visible { outline: 2px solid var(--fg); outline-offset: 2px; }
    #mic-message { min-height: 1.4em; font-size: 16px; overflow-wrap: anywhere; }
    #mic-message[data-error="true"] { color: var(--late); }
    @media (max-width: 520px) {
      .mic-controls { grid-template-columns: minmax(0, 1fr) 42px; }
      .mic-controls select { grid-column: 1 / -1; }
      #mic-apply { justify-self: start; }
      .grid { grid-template-columns: minmax(100px, 0.8fr) minmax(0, 1.2fr); font-size: 16px; gap: 8px; }
    }
    .support {
      border-top: 2px solid var(--border);
      margin-top: 22px;
      padding-top: 14px;
      font-size: 16px;
      font-weight: 700;
    }
    .support a {
      color: var(--fg);
    }
  </style>
</head>
<body>
  <header>
    <h1>AI COPILOT</h1>
    <div id="status">WAITING FOR DATA</div>
  </header>
  <main id="captures" aria-live="polite">
    <div class="empty">NO TARGETS CAPTURED</div>
  </main>
  <section class="panel" aria-live="polite">
    <h2>VOICE</h2>
    <form id="mic-form" class="mic-controls">
      <select id="mic-select" aria-label="Input microphone" disabled>
        <option>Loading microphones...</option>
      </select>
      <button id="mic-apply" type="submit" disabled>Use microphone</button>
      <button id="mic-refresh" type="button" title="Refresh microphones" aria-label="Refresh microphones">&#8635;</button>
    </form>
    <div id="mic-message" role="status" aria-live="polite"></div>
    <div class="grid">
      <div class="label">VOICE STATUS</div><div id="voice-status">DISABLED</div>
      <div class="label">MICROPHONE</div><div id="voice-input">-</div>
      <div class="label">STT MODEL</div><div id="voice-model">-</div>
      <div class="label">STT TIME</div><div id="voice-latency">-</div>
      <div class="label">PTT MODE</div><div id="voice-mode">-</div>
      <div class="label">JOY BACKEND</div><div id="voice-joy-backend">-</div>
      <div class="label">PTT</div><div id="voice-ptt">-</div>
      <div class="label">JOYSTICK</div><div id="voice-joystick" class="transcript">-</div>
      <div class="label">JOY BUTTON</div><div id="voice-joy-button">-</div>
      <div class="label">LAST TRANSCRIPT</div><div id="voice-transcript" class="transcript">-</div>
      <div class="label">LAST ERROR</div><div id="voice-error" class="transcript">-</div>
    </div>
  </section>
  <section class="panel" aria-live="polite">
    <h2>DCS-BIOS</h2>
    <div class="grid">
      <div class="label">STATUS</div><div id="dcs-status">STARTING</div>
      <div class="label">INSTALL</div><div id="dcs-install">CHECKING</div>
      <div class="label">AIRCRAFT</div><div id="dcs-aircraft">-</div>
      <div class="label">MASTER ARM</div><div id="dcs-master-arm">-</div>
      <div class="label">COMM 1</div><div id="dcs-comm1">-</div>
      <div class="label">COMM 1 FREQ</div><div id="dcs-comm1-freq">-</div>
      <div class="label">COMM 2</div><div id="dcs-comm2">-</div>
      <div class="label">COMM 2 FREQ</div><div id="dcs-comm2-freq">-</div>
    </div>
  </section>
  <footer id="support" class="support" hidden>
    <a id="support-link" href="#" target="_blank" rel="noopener noreferrer">Buy Me a Coffee</a>
  </footer>
  <script>
    let latestRevision = -1;
    let micBusy = false;
    let micRecording = false;
    let micSelected = null;
    let micReady = false;

    function micControls() {
      document.getElementById("mic-select").disabled = micBusy || micRecording || !micReady;
      document.getElementById("mic-apply").disabled = micBusy || micRecording || !micReady;
      document.getElementById("mic-refresh").disabled = micBusy;
    }

    function micMessage(message, error = false) {
      const element = document.getElementById("mic-message");
      element.textContent = message;
      element.dataset.error = String(error);
    }

    function selectCurrentMic(value) {
      const select = document.getElementById("mic-select");
      if (![...select.options].some(option => option.value === value)) {
        select.add(new Option(value + " (not available)", value));
      }
      select.value = value;
      micSelected = value;
    }

    async function loadMicrophones() {
      micBusy = true;
      micControls();
      micMessage("Loading microphones...");
      try {
        const response = await fetch("/api/microphones", { cache: "no-store" });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not load microphones");
        const select = document.getElementById("mic-select");
        select.replaceChildren();
        for (const item of data.devices) select.add(new Option(item.label, item.value));
        selectCurrentMic(data.selected);
        micReady = true;
        micMessage("");
      } catch (error) {
        micMessage(error.message, true);
      } finally {
        micBusy = false;
        micControls();
      }
    }

    document.getElementById("mic-refresh").addEventListener("click", loadMicrophones);
    document.getElementById("mic-form").addEventListener("submit", async event => {
      event.preventDefault();
      if (micBusy || micRecording || !micReady) return;
      micBusy = true;
      micControls();
      micMessage("Changing microphone...");
      try {
        const response = await fetch("/api/voice/input", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ device: document.getElementById("mic-select").value }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Microphone change failed");
        selectCurrentMic(data.voice.selected_input);
        renderVoice(data);
        micMessage("Microphone saved");
      } catch (error) {
        micMessage(error.message, true);
      } finally {
        micBusy = false;
        micControls();
      }
    });

    function render(data) {
      if (data.revision === latestRevision) {
        return;
      }
      latestRevision = data.revision;
      const container = document.getElementById("captures");
      const status = document.getElementById("status");
      container.textContent = "";
      const notes = data.notes || [];
      if (!data.captures.length && !notes.length) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "NO TARGETS CAPTURED";
        container.appendChild(empty);
        status.textContent = "WAITING FOR DATA";
        return;
      }
      for (const capture of data.captures) {
        const entry = document.createElement("div");
        entry.className = "entry";
        entry.textContent = [
          capture.title,
          capture.latitude,
          capture.longitude,
          capture.elevation
        ].join("\\n");
        container.appendChild(entry);
      }
      if (data.note_history_count) {
        const entry = document.createElement("div");
        entry.className = "entry";
        entry.textContent = data.note_history_count === 1
          ? "1 OLDER NOTE IN HISTORY"
          : data.note_history_count + " OLDER NOTES IN HISTORY";
        container.appendChild(entry);
      }
      for (const note of notes) {
        const entry = document.createElement("div");
        entry.className = "entry";
        entry.textContent = [
          note.title,
          note.text
        ].join("\\n");
        container.appendChild(entry);
      }
      status.textContent = "UPDATED";
    }

    function valueDisplay(values, id) {
      if (!values || !values[id]) {
        return "-";
      }
      return values[id].display || "-";
    }

    function renderDcsBios(data) {
      const dcs = data.dcs_bios || {};
      const values = dcs.values || {};
      document.getElementById("dcs-status").textContent = dcs.status || "UNKNOWN";
      document.getElementById("dcs-install").textContent =
        dcs.installed ? "FOUND" : "NOT FOUND";
      document.getElementById("dcs-aircraft").textContent = dcs.aircraft || "-";
      document.getElementById("dcs-master-arm").textContent =
        valueDisplay(values, "MASTER_ARM_SW");
      document.getElementById("dcs-comm1").textContent =
        valueDisplay(values, "UFC_COMM1_DISPLAY");
      document.getElementById("dcs-comm2").textContent =
        valueDisplay(values, "UFC_COMM2_DISPLAY");
      document.getElementById("dcs-comm1-freq").textContent =
        valueDisplay(values, "COMM1_FREQ");
      document.getElementById("dcs-comm2-freq").textContent =
        valueDisplay(values, "COMM2_FREQ");
    }

    function renderVoice(data) {
      const voice = data.voice || {};
      micRecording = Boolean(voice.is_recording);
      if (micReady && !micBusy && typeof voice.selected_input === "string" && voice.selected_input !== micSelected) {
        selectCurrentMic(voice.selected_input);
      }
      micControls();
      const status = voice.status || "UNKNOWN";
      const statusEl = document.getElementById("voice-status");
      statusEl.textContent = voice.is_recording ? "RECORDING" : status;
      if (voice.pending_count) {
        statusEl.textContent += " (" + voice.pending_count + " pending)";
      }
      statusEl.className = voice.is_recording ? "recording" : "";
      document.getElementById("voice-input").textContent = voice.input_device || "-";
      document.getElementById("voice-model").textContent = voice.last_model || voice.model || "-";
      document.getElementById("voice-latency").textContent =
        typeof voice.last_latency_seconds === "number" ? voice.last_latency_seconds.toFixed(2) + " s" : "-";
      document.getElementById("voice-mode").textContent = voice.ptt_mode || "-";
      document.getElementById("voice-joy-backend").textContent =
        voice.joystick_backend || "-";
      document.getElementById("voice-ptt").textContent = voice.ptt_key || "-";
      document.getElementById("voice-joystick").textContent =
        [voice.joystick_status, voice.joystick_detail].filter(Boolean).join(" - ") || "-";
      document.getElementById("voice-joy-button").textContent =
        voice.joystick_button === undefined ? "-" : String(voice.joystick_button);
      document.getElementById("voice-transcript").textContent =
        voice.last_transcript || "-";
      document.getElementById("voice-error").textContent =
        voice.last_error || "-";
    }

    function renderApp(data) {
      const app = data.app || {};
      const support = document.getElementById("support");
      const supportLink = document.getElementById("support-link");
      if (app.buy_me_a_coffee_url) {
        support.hidden = false;
        supportLink.href = app.buy_me_a_coffee_url;
      } else {
        support.hidden = true;
      }
    }

    async function refresh() {
      try {
        const response = await fetch("/api/state", { cache: "no-store" });
        if (!response.ok) {
          throw new Error("HTTP " + response.status);
        }
        const data = await response.json();
        render(data);
        renderApp(data);
        renderVoice(data);
        renderDcsBios(data);
      } catch {
        document.getElementById("status").textContent = "SERVER UNAVAILABLE";
      } finally {
        setTimeout(refresh, 500);
      }
    }

    refresh();
    loadMicrophones();
  </script>
</body>
</html>
"""
    html = html.replace("  </style>", STYLE + "  </style>")
    html = html.replace("<body>", '<body>\n<div id="notes-view">')
    html = html.replace("  <script>", '</div>\n' + HTML + "  <script>" + SCRIPT)
    html = html.replace("        render(data);", "        renderCase3(data);\n        render(data);")
    html = html.replace('        document.getElementById("status").textContent = "SERVER UNAVAILABLE";',
                        '        document.getElementById("status").textContent = "SERVER UNAVAILABLE";\n'
                        '        document.getElementById("case3-status").textContent = "SERVER UNAVAILABLE";\n'
                        '        document.getElementById("case3-countdown").textContent = "--:--";\n'
                        '        document.getElementById("case3-next-countdown").textContent = "--:--";\n'
                        '        document.getElementById("case3-current").textContent = "--";\n'
                        '        document.getElementById("case3-next").textContent = "--";\n'
                        '        document.getElementById("case3-voice").textContent = "VOICE: OFFLINE";')
    return html
