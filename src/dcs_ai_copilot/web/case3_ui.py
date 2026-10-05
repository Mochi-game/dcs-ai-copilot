"""CASE III presentation injected into the existing polling dashboard."""

STYLE = """
    :root { color-scheme: dark; --bg: #080e14; --fg: #c5cdd3; --muted: #98a9b6;
      --border: #455563; --early: #c4ad76; --ontime: #8fbc9c; --late: #cb9292;
      --lap-done: #26323c; --lap-now: #8fbc9c; }
    :root[data-theme="day"] { color-scheme: light; --bg: #ded8c8; --fg: #17212a;
      --muted: #45515a; --border: #68737b; --early: #72520c; --ontime: #24583a; --late: #922f35;
      --lap-done: #b9b3a3; --lap-now: #24583a; }
    [hidden] { display: none !important; }
    body.case3-active { padding: 0; overflow: hidden; }
    #case3-view { height: 100dvh; box-sizing: border-box; padding: 2vh 4vw;
      display: flex; flex-direction: column; gap: 1vh; font-weight: 700; }
    #case3-head { display: flex; justify-content: space-between; align-items: baseline; gap: 2vw; }
    #case3-view h2 { margin: 0; font-size: clamp(16px, 4.2vmin, 34px); white-space: nowrap; }
    #case3-commence { color: var(--muted); font-size: clamp(10px, 2.6vmin, 22px); text-align: right; }
    .case3-row { border-top: 1px solid var(--border); padding-top: 0.8vh; }
    .case3-label { color: var(--muted); font-size: clamp(11px, 2.6vmin, 22px); }
    .case3-number { font-size: clamp(18px, 5.2vmin, 52px); line-height: 1.1; }
    #case3-countdown, #case3-next-countdown { font-size: clamp(24px, 6.4vmin, 66px); }
    .case3-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 3vw; }
    .case3-pair > div { min-width: 0; }
    #case3-cue { border: 2px solid var(--border); border-radius: 6px; padding: 0.6vh 2vw;
      display: flex; justify-content: space-between; align-items: center; gap: 2vw; }
    #case3-cue-text { font-size: clamp(18px, 5.4vmin, 56px); line-height: 1.1; }
    #case3-cue-time { font-size: clamp(26px, 8vmin, 84px); line-height: 1; }
    #case3-cue[data-kind="turn-inbound"] { border-color: var(--early); color: var(--early); }
    #case3-cue[data-urgent="true"] { border-color: var(--late); color: var(--late);
      animation: case3-pulse 1s steps(2, start) infinite; }
    @keyframes case3-pulse { to { background: color-mix(in srgb, var(--late) 22%, transparent); } }
    #case3-phase-line { font-size: clamp(10px, 2.5vmin, 20px); color: var(--muted); }
    #case3-laps { display: flex; gap: 1vw; margin: 0.5vh 0; }
    .case3-lap { flex: 1 1 0; min-width: 0; text-align: center; border: 2px solid var(--border);
      border-radius: 4px; font-size: clamp(11px, 3vmin, 26px); padding: 0.3vh 0; }
    .case3-lap[data-state="done"] { background: var(--lap-done); color: var(--muted); }
    .case3-lap[data-state="now"] { border-color: var(--lap-now); color: var(--lap-now); }
    #case3-lap-advice { font-size: clamp(13px, 3.8vmin, 34px); color: var(--ontime); }
    .case3-phases { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1vw; }
    .case3-phases .case3-number { font-size: clamp(16px, 4.2vmin, 42px); }
    .case3-phases .case3-label { font-size: clamp(10px, 2.2vmin, 18px); }
    #case3-plan-message { color: var(--early); font-size: clamp(12px, 3.4vmin, 30px); }
    #case3-reference { font-size: clamp(10px, 2.4vmin, 20px); }
    #case3-reference[data-live="false"] { color: var(--late); }
    #case3-assignment, #case3-approach { font-size: clamp(11px, 2.6vmin, 23px); line-height: 1.3; }
    #case3-approach > div { border-top: 1px solid var(--border); padding: 1vh 0; }
    #case3-status { font-size: clamp(16px, 4.4vmin, 44px); }
    #case3-status[data-status="EARLY"] { color: var(--early); }
    #case3-status[data-status="ON TIME"] { color: var(--ontime); }
    #case3-status[data-status="LATE"] { color: var(--late); }
    #case3-footer { margin-top: auto; display: flex; justify-content: space-between;
      gap: 2vw; font-size: clamp(10px, 2.4vmin, 20px); }
"""

HTML = """
  <main id="case3-view" hidden aria-label="CASE III Recovery">
    <div id="case3-head"><h2>CASE III</h2><span id="case3-commence">ASSIGNMENT PENDING</span></div>
    <div id="case3-assignment"></div>
    <div class="case3-row case3-pair" data-hold-only>
      <div><div class="case3-label" id="case3-eat-label">PUSH / EAT</div><div id="case3-eat" class="case3-number">--:--</div></div>
      <div><div class="case3-label">LATEST CROSSING</div><div id="case3-crossing" class="case3-number">--:--</div></div>
    </div>
    <div class="case3-row case3-pair" data-hold-only>
      <div><div class="case3-label">TIME TO COMMENCE</div><div id="case3-countdown" class="case3-number">--:--</div></div>
      <div><div class="case3-label">TIME TO NEXT</div><div id="case3-next-countdown" class="case3-number">--:--</div></div>
    </div>
    <div id="case3-cue" data-hold-only hidden><span id="case3-cue-text">--</span><span id="case3-cue-time">--:--</span></div>
    <div id="case3-phase-line" data-hold-only>CURRENT <span id="case3-current">--</span> · NEXT <span id="case3-next">--</span></div>
    <div class="case3-row" data-hold-only>
      <div id="case3-plan-message">SET EAT AND MARSHAL CROSS</div>
      <div id="case3-laps"></div>
      <div id="case3-lap-advice"></div>
      <div id="case3-leg-plan" hidden>
        <div class="case3-label" id="case3-leg-caption">THIS LAP</div>
        <div class="case3-phases">
          <div><div class="case3-label">TURN</div><div class="case3-number">2:00</div></div>
          <div><div class="case3-label">OUTBOUND</div><div id="case3-outbound" class="case3-number">--:--</div></div>
          <div><div class="case3-label">TURN</div><div class="case3-number">2:00</div></div>
          <div><div class="case3-label">INBOUND</div><div id="case3-inbound" class="case3-number">--:--</div></div>
        </div>
      </div>
    </div>
    <div id="case3-approach" hidden></div>
    <div class="case3-row"><div class="case3-label">STATUS · CLOCK VS EAT</div>
      <div id="case3-status" class="case3-number">READY</div>
      <div id="case3-reference">CLOCK --:--:--</div></div>
    <div id="case3-footer"><span>VIEW: CASE III</span><span id="case3-voice">VOICE: DISABLED</span></div>
  </main>
"""

SCRIPT = """
    function case3Duration(seconds) {
      if (seconds === null || seconds === undefined) return '--:--';
      const value = Math.abs(seconds);
      return (seconds < 0 ? '-' : '') + String(Math.floor(value / 60)).padStart(2, '0') + ':' +
        String(value % 60).padStart(2, '0');
    }
    function case3Lap(seconds) {
      return Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0');
    }
    function renderCase3(data) {
      document.documentElement.dataset.theme = data.theme === 'day' ? 'day' : 'night';
      const active = data.active_view === 'case3';
      document.body.classList.toggle('case3-active', active);
      document.getElementById('notes-view').hidden = active;
      document.getElementById('case3-view').hidden = !active;
      const c = data.case3 || {};
      const el = id => document.getElementById(id);
      const put = (id, value) => { el(id).textContent = value; };
      const time = value => value ? value.slice(11, 19) : '--:--:--';
      put('case3-commence', c.commence_dme ?
        'FIX ' + c.commence_dme + ' DME · ' + c.marshal_altitude_ft + ' FT' : 'ASSIGNMENT PENDING');
      const a = c.assignment || {};
      const assignment = [a.radial !== undefined ? 'R' + String(a.radial).padStart(3, '0') : '',
        a.dme !== undefined ? a.dme + ' DME' : '', a.angels !== undefined ? 'ANGELS ' + a.angels : '',
        a.button !== undefined ? 'BTN ' + a.button : '', a.fb !== undefined ? 'FB ' + String(a.fb).padStart(3, '0') : '',
        a.tacan ? 'TCN ' + a.tacan : '', a.icls !== undefined ? 'ICLS ' + a.icls : ''].filter(Boolean);
      put('case3-assignment', assignment.join(' · ') || 'SAY MARSHAL ASSIGNMENT');
      const commenced = c.phase !== 'HOLD';
      document.querySelectorAll('[data-hold-only]').forEach(node => { node.hidden = commenced; });
      const approach = el('case3-approach');
      approach.hidden = !commenced;
      approach.replaceChildren(...(c.approach_guidance || []).map(line => {
        const row = document.createElement('div'); row.textContent = line; return row;
      }));
      const clock = c.clock_source === 'MISSION' ? 'MISSION' :
        c.clock_source === 'MANUAL' ? 'MANUAL' : 'PC';
      put('case3-eat-label', 'PUSH / EAT · ' + clock);
      put('case3-eat', c.eat ? c.eat.slice(11, 16) : '--:--');
      put('case3-crossing', c.marshal_crossing_time ? time(c.marshal_crossing_time) : '--:--');
      put('case3-countdown', case3Duration(c.time_to_commence_seconds));
      put('case3-next-countdown', case3Duration(c.time_to_next_seconds));
      put('case3-current', c.current_phase || '--');
      put('case3-next', c.next_event || '--');

      const cue = el('case3-cue');
      cue.hidden = commenced || !c.cue;
      put('case3-cue-text', c.cue || '--');
      put('case3-cue-time', case3Duration(c.cue_seconds));
      cue.dataset.kind = c.current_phase === 'OUTBOUND' ? 'turn-inbound' : '';
      cue.dataset.urgent = c.cue_urgent ? 'true' : 'false';

      const planned = c.plan_status === 'PLANNED';
      const lengths = c.hold_lengths_seconds || [];
      const laps = el('case3-laps');
      laps.textContent = '';
      lengths.forEach((seconds, index) => {
        const lap = document.createElement('div');
        lap.className = 'case3-lap';
        const number = index + 1;
        lap.dataset.state = !c.current_hold ? (c.time_to_commence_seconds === 0 ? 'done' : 'todo') :
          number < c.current_hold ? 'done' : number === c.current_hold ? 'now' : 'todo';
        lap.textContent = case3Lap(seconds);
        laps.appendChild(lap);
      });
      laps.hidden = !lengths.length;
      put('case3-lap-advice', planned ? (c.lap_advice || '') : (c.crossing_preview || ''));
      const message = planned ? '' : c.crossing_preview ? '' : c.recommendation || 'SET EAT AND MARSHAL CROSS';
      put('case3-plan-message', message);
      el('case3-plan-message').hidden = !message;

      const hold = c.current_hold || (c.timeline && c.timeline.length ? 1 : null);
      const legs = (c.timeline || []).filter(p => p.hold_index === hold);
      const leg = name => { const p = legs.find(x => x.phase === name); return p ? p.duration_seconds : null; };
      el('case3-leg-plan').hidden = !planned || !legs.length;
      put('case3-leg-caption', c.current_hold ? 'THIS LAP · ' + c.current_hold + ' OF ' + lengths.length : 'FIRST LAP');
      put('case3-outbound', legs.length ? case3Lap(leg('OUTBOUND')) : '--:--');
      put('case3-inbound', legs.length ? case3Lap(leg('INBOUND')) : '--:--');

      put('case3-status', commenced ? 'COMMENCED' : c.status || 'READY');
      el('case3-status').dataset.status = c.status;
      const live = c.clock_live !== false;
      put('case3-reference', 'TIME SOURCE: ' + clock + ' CLOCK ' + time(c.current_time) +
        (live ? '' : clock === 'MISSION' ? ' · PAUSED / NO DCS DATA' : ''));
      el('case3-reference').dataset.live = live ? 'true' : 'false';
      const voice = data.voice || {};
      const busy = voice.is_recording ? 'RECORDING' :
        voice.last_error ? 'ERROR' : voice.status === 'TRANSCRIBING' ? 'TRANSCRIBING' :
        !voice.enabled ? 'DISABLED' : voice.status === 'STOPPED' ? 'STOPPED' : 'READY';
      put('case3-voice', 'VOICE: ' + busy);
      el('case3-voice').title = voice.last_error || '';
    }
"""
