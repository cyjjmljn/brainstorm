/* Brainstorm Web App — Vanilla JS */

let currentSessionId = null;
let pollInterval = null;

const MODEL_LABELS = {
  claude: "Claude Opus",
  gemini: "Gemini 3.1 Pro",
  qwen: "Qwen 3.5 Plus",
  minimax: "MiniMax M2.5",
};

const POSITION_COLORS = {
  S1: "supporter", S2: "supporter",
  O1: "opponent", O2: "opponent",
  moderator: "moderator",
};

// ── API helpers ─────────────────────────────────────────────

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch("/api" + path, opts);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || resp.statusText);
  }
  return resp.json();
}

// ── View switching ──────────────────────────────────────────

function showView(name) {
  document.querySelectorAll("[id^=view-]").forEach(el => el.classList.add("hidden"));
  document.getElementById("view-" + name).classList.remove("hidden");
}

function showList() {
  stopPolling();
  currentSessionId = null;
  showView("list");
  loadSessions();
}

function showSetup() {
  showView("setup");
  loadPreviousSessions();
  initFileBrowser();
}

// ── Session List ────────────────────────────────────────────

async function loadSessions() {
  const sessions = await api("GET", "/sessions");
  const el = document.getElementById("session-list");
  if (sessions.length === 0) {
    el.innerHTML = '<div style="color:#8b949e;padding:20px;text-align:center">No sessions yet</div>';
    return;
  }
  el.innerHTML = sessions.map(s => {
    const statusLabel = s.status === "new" ? "Ready" :
      s.status === "complete" ? "Complete" :
      s.status.includes("running") ? "Running..." :
      s.status.replace(/_/g, " ");
    return `
    <div class="session-item" onclick="openSession('${s.session_id}')">
      <div><strong>${esc(s.title)}</strong></div>
      <div class="session-meta">
        Stage ${s.stage} | ${statusLabel} | ${s.created_at.slice(0, 16)}
      </div>
    </div>`;
  }).join("");
}

async function loadPreviousSessions() {
  try {
    const sessions = await api("GET", "/sessions");
    const sel = document.getElementById("sel-import");
    sel.innerHTML = '<option value="">None</option>';
    sessions.forEach(s => {
      const statusHint = s.status === "complete" ? "✓" : `Stage ${s.stage}`;
      sel.innerHTML += `<option value="${s.session_id}">${esc(s.title)} (${statusHint}, ${s.created_at.slice(0, 10)})</option>`;
    });
  } catch (e) { /* ignore */ }
}

// ── Create Session ──────────────────────────────────────────

async function createSession() {
  const title = document.getElementById("inp-title").value.trim();
  const idea = document.getElementById("inp-idea").value.trim();
  if (!title || !idea) { alert("Please fill in title and idea"); return; }

  const background = document.getElementById("inp-background").value.trim();
  const importSession = document.getElementById("sel-import").value;
  const instructions = document.getElementById("inp-instructions").value.trim();

  const res = await api("POST", "/sessions", {
    title, idea, background, instructions,
    background_files: selectedFiles,
    import_session: importSession,
    s1: document.getElementById("sel-s1").value,
    s2: document.getElementById("sel-s2").value,
    o1: document.getElementById("sel-o1").value,
    o2: document.getElementById("sel-o2").value,
  });

  openSession(res.session_id);
}

// ── Open/Resume Session ─────────────────────────────────────

async function openSession(sessionId) {
  currentSessionId = sessionId;
  showView("debate");
  await refreshDebate();
}

async function refreshDebate() {
  if (!currentSessionId) return;
  const state = await api("GET", "/sessions/" + currentSessionId);

  document.getElementById("debate-title").textContent = state.title;
  document.getElementById("debate-idea").textContent = state.idea;

  // Load current instructions into edit field
  const instrEl = document.getElementById("inp-edit-instructions");
  if (instrEl && !instrEl._userEditing) {
    instrEl.value = state.instructions || "";
  }

  // Status label
  const statusEl = document.getElementById("debate-status");
  const statusLabel = getStatusLabel(state.status);
  statusEl.textContent = statusLabel;
  statusEl.className = "status-badge " + (
    state.status.includes("running") ? "status-running" :
    state.status.includes("pause") ? "status-pause" :
    state.status === "complete" ? "status-complete" : ""
  );

  // Render rounds dynamically
  const roundsContainer = document.getElementById("rounds-container");
  renderAllRounds(roundsContainer, state);

  // Render action buttons
  renderActions(state);

  // Start polling if running
  if (state.status.includes("running")) {
    startPolling();
  } else {
    stopPolling();
  }
}

function getStatusLabel(status) {
  if (status === "new") return "Ready";
  if (status === "r1_running") return "Round 1 Running...";
  if (status === "r1_pause") return "Round 1 Complete";
  if (status === "synthesis_running") return "Synthesizing...";
  if (status === "complete") return "Complete";
  // Dynamic debate rounds
  const m = status.match(/debate_(\d+)_(attacks_running|defenses_running|pause)/);
  if (m) {
    const num = m[1];
    const sub = m[2];
    if (sub === "attacks_running") return `Debate ${num} Attacks...`;
    if (sub === "defenses_running") return `Debate ${num} Defenses...`;
    if (sub === "pause") return `Debate ${num} Complete`;
  }
  // Roundtable rounds
  const rt = status.match(/roundtable_(\d+)_(running|pause)/);
  if (rt) {
    const num = rt[1];
    if (rt[2] === "running") return `Roundtable ${num} Running...`;
    if (rt[2] === "pause") return `Roundtable ${num} Complete`;
  }
  return status.replace(/_/g, " ");
}

function renderAllRounds(container, state) {
  let html = "";

  // Round 1
  const r1Responses = state.responses.filter(r => r.phase === "r1");
  const r1Visible = r1Responses.length > 0 || state.status.startsWith("r1");
  if (r1Visible) {
    html += renderRoundSection("r1", "Round 1: Neutral Discussion", state, ["r1"], state.summaries.r1);
  }

  // Debate rounds (dynamic)
  const debateNums = new Set();
  state.responses.forEach(r => {
    const m = r.phase.match(/^debate_(\d+)_/);
    if (m) debateNums.add(parseInt(m[1]));
  });
  // Also check if currently running a debate round
  const statusMatch = state.status.match(/^debate_(\d+)_/);
  if (statusMatch) debateNums.add(parseInt(statusMatch[1]));

  // Collect all round numbers and types, then render in order
  const roundEvents = [];

  for (const num of [...debateNums].sort((a, b) => a - b)) {
    roundEvents.push({ type: "debate", num });
  }

  // Roundtable rounds
  const rtNums = new Set();
  state.responses.forEach(r => {
    const m = r.phase.match(/^roundtable_(\d+)$/);
    if (m) rtNums.add(parseInt(m[1]));
  });
  const rtStatus = state.status.match(/^roundtable_(\d+)_/);
  if (rtStatus) rtNums.add(parseInt(rtStatus[1]));
  for (const num of [...rtNums].sort((a, b) => a - b)) {
    roundEvents.push({ type: "roundtable", num });
  }

  // Sort all by round number
  roundEvents.sort((a, b) => a.num - b.num);

  for (const evt of roundEvents) {
    if (evt.type === "debate") {
      const num = evt.num;
      const isSwap = num % 2 === 0;
      const label = `Debate ${num}${isSwap ? " (Role Swap)" : ""}`;
      const phases = [`debate_${num}_attack`, `debate_${num}_defense`];
      const summaryKey = `debate_${num}`;
      html += renderRoundSection(`debate_${num}`, label, state, phases, state.summaries[summaryKey]);
    } else {
      const num = evt.num;
      const label = `Roundtable ${num}`;
      const phases = [`roundtable_${num}`];
      const summaryKey = `roundtable_${num}`;
      html += renderRoundSection(`roundtable_${num}`, label, state, phases, state.summaries[summaryKey]);
    }
  }

  // Synthesis
  const synthResponses = state.responses.filter(r => r.phase === "synthesis");
  if (synthResponses.length > 0 || state.status === "synthesis_running") {
    html += renderSynthesisSection(state, synthResponses);
  }

  container.innerHTML = html;
}

function renderRoundSection(key, label, state, phases, summary) {
  const responses = state.responses.filter(r => phases.includes(r.phase));
  const isRunning = state.status.startsWith(key) && state.status.includes("running");

  let badge = "";
  if (isRunning) {
    badge = '<span class="spinner"></span>';
  } else if (responses.length > 0) {
    badge = responses.length + " responses";
  }

  let body = "";
  for (const phase of phases) {
    const phaseResponses = responses.filter(r => r.phase === phase);
    if (phaseResponses.length === 0) continue;

    const phaseLabel = phase.includes("attack") ? "Attacks" : phase.includes("defense") ? "Defenses" : "Responses";
    body += `<h2>${phaseLabel}</h2>`;

    for (const r of phaseResponses) {
      const colorClass = POSITION_COLORS[r.position] || "neutral";
      const modelLabel = MODEL_LABELS[r.model_name] || r.model_name;
      const text = r.error ? `ERROR: ${r.error}` : r.text;
      body += `
        <div class="card card-${colorClass}">
          <h3>${esc(r.position)} — ${esc(modelLabel)}</h3>
          <div class="card-text">${esc(text)}</div>
        </div>`;
    }
  }

  if (summary) {
    body += `
      <div class="card card-moderator">
        <h3>Moderator Summary</h3>
        <div class="card-text">${esc(summary)}</div>
      </div>`;
  }

  return `
    <div class="round-section">
      <div class="round-header" onclick="toggleRound('${key}')">
        <span>${esc(label)}</span>
        <span>${badge}</span>
      </div>
      <div id="${key}-body" class="round-body${body ? '' : ' hidden'}">${body}</div>
    </div>`;
}

function renderSynthesisSection(state, synthResponses) {
  const isRunning = state.status === "synthesis_running";
  let badge = isRunning ? '<span class="spinner"></span>' : (synthResponses.length > 0 ? "Done" : "");

  let body = "";
  if (synthResponses.length > 0) {
    const latest = synthResponses[synthResponses.length - 1];
    body = `
      <div class="card card-moderator">
        <h3>Final Synthesis</h3>
        <div class="card-text">${esc(latest.text)}</div>
      </div>`;
  }

  return `
    <div class="round-section">
      <div class="round-header" onclick="toggleRound('synthesis')">
        <span>Synthesis</span>
        <span>${badge}</span>
      </div>
      <div id="synthesis-body" class="round-body${body ? '' : ' hidden'}">${body}</div>
    </div>`;
}

function renderActions(state) {
  const el = document.getElementById("action-buttons");
  const buttons = [];

  if (state.status === "new") {
    buttons.push(`<button class="btn-primary" onclick="runPhase('r1')">Start Round 1</button>`);
  } else if (state.status === "r1_pause" || state.status.match(/(debate|roundtable)_\d+_pause/)) {
    const nextRound = (state.current_round || 0) + 1;
    const isSwap = nextRound % 2 === 0;
    const swapLabel = isSwap ? " (Role Swap)" : "";
    buttons.push(`<button class="btn-primary" onclick="runPhase('debate')">⚔️ Debate ${nextRound}${swapLabel}</button>`);
    buttons.push(`<button class="btn-primary" onclick="runPhase('roundtable')" style="background:#238636">🤝 Roundtable ${nextRound}</button>`);
    buttons.push(`<button class="btn-secondary" onclick="runPhase('synthesis')">Synthesis</button>`);
  } else if (state.status === "complete") {
    buttons.push(`<button class="btn-primary" onclick="newStage()">Start New Stage</button>`);
  }

  if (state.status.includes("running")) {
    buttons.push(`<span><span class="spinner"></span> Processing...</span>`);
  }

  el.innerHTML = buttons.join("");
}

// ── Actions ─────────────────────────────────────────────────

async function runPhase(phase) {
  if (!currentSessionId) return;
  try {
    await api("POST", `/sessions/${currentSessionId}/run/${phase}`);
    startPolling();
    await refreshDebate();
  } catch (e) {
    alert("Error: " + e.message);
  }
}

async function addNote() {
  const textarea = document.getElementById("inp-note");
  const text = textarea.value.trim();
  if (!text) return;
  await api("POST", `/sessions/${currentSessionId}/notes`, { text });
  textarea.value = "";
  alert("Note added. It will be included in the next round's context.");
}

async function updateInstructions() {
  const textarea = document.getElementById("inp-edit-instructions");
  const instructions = textarea.value.trim();
  await api("POST", `/sessions/${currentSessionId}/instructions`, { instructions });
  alert("Instructions updated. Will apply to all future rounds.");
}

async function addContext() {
  const textarea = document.getElementById("inp-add-context");
  const text = textarea.value.trim();
  if (!text) return;
  await api("POST", `/sessions/${currentSessionId}/context`, { text });
  textarea.value = "";
  alert("Context added to session.");
}

async function newStage() {
  await api("POST", `/sessions/${currentSessionId}/new-stage`);
  await refreshDebate();
}

// ── Polling ─────────────────────────────────────────────────

function startPolling() {
  stopPolling();
  pollInterval = setInterval(async () => {
    await refreshDebate();
  }, 3000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

// ── Round toggle ────────────────────────────────────────────

function toggleRound(roundKey) {
  const body = document.getElementById(roundKey + "-body");
  if (body) body.classList.toggle("hidden");
}

// ── Utils ───────────────────────────────────────────────────

function esc(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");
}

// ── File Browser ────────────────────────────────────────────

let selectedFiles = [];

async function initFileBrowser() {
  selectedFiles = [];
  renderSelectedFiles();
  const data = await api("POST", "/local-files", { path: "" });
  renderFileBrowserRoots(data.dirs);
}

function renderFileBrowserRoots(dirs) {
  const el = document.getElementById("file-browser");
  el.innerHTML = `<div class="file-list">${
    dirs.map(d => `<div class="file-item" onclick="browseDir('${esc(d)}')"><span class="icon">📁</span> ${esc(d)}</div>`).join("")
  }</div>`;
}

async function browseDir(path) {
  const data = await api("POST", "/local-files", { path });
  const el = document.getElementById("file-browser");
  const parent = path.replace(/\/[^/]+\/?$/, "") || "/";
  let html = '<div class="file-list">';
  html += `<div class="file-item" onclick="browseDir('${esc(parent)}')" style="color:#8b949e"><span class="icon">⬆</span> ..</div>`;
  html += `<div style="padding:4px 10px;font-size:0.75em;color:#484f58">${esc(data.current || path)}</div>`;
  for (const item of data.files) {
    if (item.type === "dir") {
      html += `<div class="file-item" onclick="browseDir('${esc(item.path)}')"><span class="icon">📁</span> ${esc(item.name)}</div>`;
    } else {
      const selected = selectedFiles.includes(item.path);
      html += `<div class="file-item" onclick="toggleFile('${esc(item.path)}')" style="${selected ? 'background:#1f6feb33' : ''}"><span class="icon">📄</span> ${esc(item.name)}</div>`;
    }
  }
  html += '</div>';
  el.innerHTML = html;
}

function toggleFile(path) {
  const idx = selectedFiles.indexOf(path);
  if (idx >= 0) {
    selectedFiles.splice(idx, 1);
  } else {
    selectedFiles.push(path);
  }
  renderSelectedFiles();
  // Re-render current directory to update highlight
  const currentPath = document.querySelector("#file-browser .file-list div[style*='color:#484f58']");
  if (currentPath) browseDir(currentPath.textContent);
}

function renderSelectedFiles() {
  const el = document.getElementById("selected-files");
  if (selectedFiles.length === 0) {
    el.innerHTML = '';
    return;
  }
  el.innerHTML = selectedFiles.map(f => {
    const name = f.split("/").pop();
    return `<span class="selected-file" onclick="toggleFile('${esc(f)}')" title="Click to remove">${esc(name)} ×</span>`;
  }).join("");
}

// ── Init ────────────────────────────────────────────────────

loadSessions();
