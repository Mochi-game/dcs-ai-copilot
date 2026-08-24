from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable
from urllib.parse import urlparse

from dcs_ai_copilot.kneeboard.state import KneeboardState


class LoopbackHTTPServer(HTTPServer):
    allow_reuse_address = False


def start_kneeboard_server(
    state: KneeboardState,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> tuple[LoopbackHTTPServer, threading.Thread]:
    if host != "127.0.0.1":
        raise ValueError("web server must bind to 127.0.0.1")

    handler = build_request_handler(state)
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
) -> type[BaseHTTPRequestHandler]:
    class KneeboardRequestHandler(BaseHTTPRequestHandler):
        server_version = "DCSAICopilot/0.1"

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                self._send_text(render_dashboard_html(), "text/html; charset=utf-8")
                return
            if path == "/api/state":
                self._send_json(state.as_json_data)
                return
            self.send_error(404, "Not found")

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(self, data_factory: Callable[[], dict[str, object]]) -> None:
            payload = json.dumps(data_factory(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
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
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI COPILOT</title>
  <style>
    html, body {
      margin: 0;
      min-height: 100%;
      background: #f4f0e4;
      color: #101010;
      font-family: Consolas, "Courier New", monospace;
    }
    body {
      padding: 24px;
      box-sizing: border-box;
    }
    header {
      margin-bottom: 18px;
      border-bottom: 2px solid #101010;
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
      border-top: 2px solid #101010;
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
      color: #424242;
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
    .support {
      border-top: 2px solid #101010;
      margin-top: 22px;
      padding-top: 14px;
      font-size: 16px;
      font-weight: 700;
    }
    .support a {
      color: #101010;
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
    <div class="grid">
      <div class="label">VOICE STATUS</div><div id="voice-status">DISABLED</div>
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
      const status = voice.status || "UNKNOWN";
      const statusEl = document.getElementById("voice-status");
      statusEl.textContent = voice.is_recording ? "RECORDING" : status;
      statusEl.className = voice.is_recording ? "recording" : "";
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
      }
    }

    refresh();
    setInterval(refresh, 1500);
  </script>
</body>
</html>
"""
