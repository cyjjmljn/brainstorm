/* Forge — Competitive Paper Introduction Platform (frontend) */

const API = '/api/forge';
let currentSessionId = null;
let pollTimer = null;
let lastStatus = null;

// ── Views ──────────────────────────────────────────────────────────────────

function showView(id) {
  document.querySelectorAll('[id^="view-"]').forEach(v => v.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
}

function showList() {
  currentSessionId = null;
  stopPolling();
  showView('view-list');
  loadSessions();
}

function showSetup() {
  showView('view-setup');
}

// ── Mode selector ──────────────────────────────────────────────────────────

const MODE_DESCS = {
  story_driven: 'Story-driven: optimize the narrative, identify what evidence is needed.',
  evidence_driven: 'Evidence-driven: find the best story to explain your findings.',
  joint: 'Joint: optimize both story and evidence fit together.',
};

function selectMode(el) {
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('mode-desc').textContent = MODE_DESCS[el.dataset.mode] || '';
}

function getSelectedMode() {
  const active = document.querySelector('.mode-btn.active');
  return active ? active.dataset.mode : 'joint';
}

// ── Session List ───────────────────────────────────────────────────────────

async function loadSessions() {
  try {
    const res = await fetch(`${API}/sessions`);
    const sessions = await res.json();
    const container = document.getElementById('session-list');
    if (!sessions.length) {
      container.innerHTML = '<div style="color:#8b949e;padding:20px;text-align:center">No forge sessions yet.</div>';
      return;
    }
    container.innerHTML = sessions.map(s => `
      <div class="session-item" onclick="openSession('${s.session_id}')">
        <div>${s.title}</div>
        <div class="session-meta">${s.status} | ${s.created_at?.slice(0,16) || ''}</div>
      </div>
    `).join('');
  } catch (e) {
    console.error('Failed to load sessions:', e);
  }
}

// ── Create Session ─────────────────────────────────────────────────────────

async function createSession() {
  const title = document.getElementById('inp-title').value.trim();
  const story = document.getElementById('inp-story').value.trim();
  const evidence = document.getElementById('inp-evidence').value.trim();

  if (!title) { alert('Title is required'); return; }
  if (!story && !evidence) { alert('Provide at least a story or evidence'); return; }

  const body = {
    title,
    story,
    evidence,
    mode: getSelectedMode(),
    background: document.getElementById('inp-background')?.value?.trim() || '',
    instructions: document.getElementById('inp-instructions')?.value?.trim() || '',
    w1: document.getElementById('sel-w1').value,
    w2: document.getElementById('sel-w2').value,
    w3: document.getElementById('sel-w3').value,
    w4: document.getElementById('sel-w4').value,
  };

  try {
    const res = await fetch(`${API}/sessions`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await res.json();
    openSession(data.session_id);
  } catch (e) {
    alert('Failed to create session: ' + e.message);
  }
}

// ── Open Session ───────────────────────────────────────────────────────────

async function openSession(sessionId) {
  currentSessionId = sessionId;
  showView('view-forge');
  await renderSession();
  startPolling();
}

// ── Render ──────────────────────────────────────────────────────────────────

async function renderSession() {
  if (!currentSessionId) return;

  try {
    const res = await fetch(`${API}/sessions/${currentSessionId}`);
    const state = await res.json();

    document.getElementById('forge-title').textContent = state.title;
    renderStatus(state.status);
    renderScores(state);
    renderRounds(state);
    renderActions(state);

    // Populate edit instructions if empty
    const instrInput = document.getElementById('inp-edit-instructions');
    if (instrInput && !instrInput.value && state.instructions) {
      instrInput.value = state.instructions;
    }

    lastStatus = state.status;
  } catch (e) {
    console.error('Failed to render session:', e);
  }
}

function renderStatus(status) {
  const badge = document.getElementById('forge-status');
  let cls = 'status-pause';
  if (status.includes('running') || status.includes('judging')) cls = 'status-running';
  else if (status === 'complete') cls = 'status-complete';
  badge.className = `status-badge ${cls}`;
  badge.textContent = formatStatus(status);
}

function formatStatus(s) {
  const map = {
    'new': 'Ready',
    'draft_running': 'Drafting...',
    'draft_judging': 'Judging...',
    'draft_pause': 'Draft Complete',
    'synthesis_running': 'Synthesizing...',
    'complete': 'Complete',
  };
  if (map[s]) return map[s];
  if (s.includes('refine') && s.includes('running')) return 'Refining...';
  if (s.includes('refine') && s.includes('judging')) return 'Judging...';
  if (s.includes('_pause')) return 'Round Complete';
  return s;
}

// ── Scores ──────────────────────────────────────────────────────────────────

function renderScores(state) {
  const dashboard = document.getElementById('score-dashboard');
  const content = document.getElementById('score-content');

  if (!state.scores || Object.keys(state.scores).length === 0) {
    dashboard.classList.add('hidden');
    return;
  }

  dashboard.classList.remove('hidden');

  // Get the latest round's scores
  const roundKeys = Object.keys(state.scores).sort();
  const latestKey = roundKeys[roundKeys.length - 1];
  const scores = state.scores[latestKey];

  if (!scores || Object.keys(scores).length === 0) {
    content.innerHTML = '<div style="color:#8b949e">Scores pending...</div>';
    return;
  }

  const dims = ['elegance', 'surprise', 'mechanism', 'evidence_fit', 'publishability'];
  const dimLabels = { elegance: 'Elegance', surprise: 'Surprise', mechanism: 'Mechanism', evidence_fit: 'Evidence Fit', publishability: 'Publishability' };

  // Get model names from positions
  const modelMap = {};
  (state.positions || []).forEach(p => { modelMap[p.position] = p.model_name; });

  let html = `<div class="tab-bar">`;
  const positions = Object.keys(scores).sort();
  positions.forEach((pos, i) => {
    const isBest = pos === state.best_draft;
    const total = scores[pos]?.total || 0;
    const label = `${pos} (${modelMap[pos] || '?'})${isBest ? ' ★' : ''} — ${total}/50`;
    html += `<div class="tab${i === 0 ? ' active' : ''}" onclick="switchScoreTab(this, '${pos}')">${label}</div>`;
  });
  html += `</div>`;

  positions.forEach((pos, i) => {
    const s = scores[pos] || {};
    const total = s.total || 0;
    const totalCls = total >= 40 ? 'total-high' : total >= 30 ? 'total-mid' : 'total-low';

    html += `<div class="tab-content${i === 0 ? ' active' : ''}" data-tab="${pos}">`;
    html += `<div style="margin-bottom:8px"><span class="total-score ${totalCls}">${total}/50</span></div>`;
    dims.forEach(d => {
      const val = s[d] || 0;
      html += `<div class="score-row">
        <span class="score-label">${dimLabels[d]}</span>
        <div class="score-bar-bg"><div class="score-bar score-bar-${d}" style="width:${val * 10}%"></div></div>
        <span class="score-value">${val}</span>
      </div>`;
    });
    html += `</div>`;
  });

  content.innerHTML = html;
}

function switchScoreTab(el, pos) {
  el.parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  const container = el.parentElement.parentElement;
  container.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  container.querySelector(`[data-tab="${pos}"]`)?.classList.add('active');
}

// ── Rounds ──────────────────────────────────────────────────────────────────

function renderRounds(state) {
  const container = document.getElementById('rounds-container');
  let html = '';

  // Loading indicator
  if (state.status.includes('running') || state.status.includes('judging')) {
    const msgs = [
      'Models are writing furiously...',
      'Economists arguing about identification...',
      'Searching for the perfect hook...',
      'Channeling inner Acemoglu...',
      'Optimizing story elegance...',
      'Finding counterintuitive angles...',
    ];
    const msg = msgs[Math.floor(Date.now() / 5000) % msgs.length];
    html += `<div class="card" style="text-align:center;padding:20px">
      <span class="spinner"></span>
      <span class="loading-msg">${msg}</span>
    </div>`;
  }

  // Draft round
  const draftResponses = (state.responses || []).filter(r => r.phase === 'draft' && !r.error);
  if (draftResponses.length > 0) {
    html += renderRoundSection('Draft Round', draftResponses, state, 'draft');
  }

  // Draft judge
  const draftJudge = (state.responses || []).filter(r => r.phase === 'draft_judge' && !r.error);
  if (draftJudge.length > 0) {
    html += renderJudgeSection('Draft — Judge', draftJudge[0], state);
  }

  // Refine rounds
  for (let i = 1; i <= 20; i++) {
    const refinePhase = `refine_${i}`;
    const refineResponses = (state.responses || []).filter(r => r.phase === refinePhase && !r.error);
    if (refineResponses.length === 0) break;

    html += renderRoundSection(`Refine Round ${i}`, refineResponses, state, refinePhase);

    const judgePhase = `refine_${i}_judge`;
    const judgeResponses = (state.responses || []).filter(r => r.phase === judgePhase && !r.error);
    if (judgeResponses.length > 0) {
      html += renderJudgeSection(`Round ${i} — Judge`, judgeResponses[0], state);
    }
  }

  // Synthesis
  const synthesis = (state.responses || []).filter(r => r.phase === 'synthesis' && !r.error);
  if (synthesis.length > 0) {
    html += `<div class="round-section">
      <div class="round-header" onclick="toggleRound(this)">
        <span>Final Synthesis</span><span>▼</span>
      </div>
      <div class="round-body">
        <div class="card card-judge">
          <h3>Final Introduction + Gap Analysis</h3>
          <div class="card-text">${escapeHtml(synthesis[0].text)}</div>
        </div>
      </div>
    </div>`;
  }

  container.innerHTML = html;
}

function renderRoundSection(title, responses, state, phase) {
  const modelMap = {};
  (state.positions || []).forEach(p => { modelMap[p.position] = p.model_name; });

  // Get scores for this phase
  const phaseKey = phase.replace('refine_', 'refine_');
  const scores = state.scores?.[phaseKey === 'draft' ? 'draft' : phaseKey] || {};

  let cards = '';
  responses.forEach(r => {
    const isBest = r.position === state.best_draft;
    const cardClass = isBest ? 'card-best' : 'card-writer';
    const score = scores[r.position]?.total;
    const scoreLabel = score ? ` — ${score}/50` : '';
    const bestLabel = isBest ? ' ★ BEST' : '';
    cards += `<div class="card ${cardClass}">
      <h3>${r.position} (${r.model_name})${scoreLabel}${bestLabel}</h3>
      <div class="card-text">${escapeHtml(r.text)}</div>
    </div>`;
  });

  return `<div class="round-section">
    <div class="round-header" onclick="toggleRound(this)">
      <span>${title} (${responses.length} drafts)</span><span>▼</span>
    </div>
    <div class="round-body">${cards}</div>
  </div>`;
}

function renderJudgeSection(title, response, state) {
  return `<div class="round-section">
    <div class="round-header" onclick="toggleRound(this)">
      <span>${title}</span><span>▼</span>
    </div>
    <div class="round-body">
      <div class="card card-judge">
        <h3>Judge (${response.model_name})</h3>
        <div class="card-text">${escapeHtml(response.text)}</div>
      </div>
    </div>
  </div>`;
}

function toggleRound(header) {
  const body = header.nextElementSibling;
  const arrow = header.querySelector('span:last-child');
  if (body.style.display === 'none') {
    body.style.display = '';
    arrow.textContent = '▼';
  } else {
    body.style.display = 'none';
    arrow.textContent = '▶';
  }
}

// ── Actions ─────────────────────────────────────────────────────────────────

function renderActions(state) {
  const container = document.getElementById('action-buttons');
  let html = '';

  if (state.status === 'new') {
    html = `<button class="btn-primary" onclick="runPhase('draft')">Start Forging</button>`;
  } else if (state.status.endsWith('_pause')) {
    html = `
      <button class="btn-primary" onclick="runPhase('refine')">Forge Again</button>
      <button class="btn-synthesis" onclick="runPhase('synthesis')">Final Product</button>
    `;
  } else if (state.status === 'complete') {
    html = `<div style="color:#d2a8ff">Session complete. Check the synthesis above.</div>`;
  } else {
    // Running state
    html = `<div style="color:#58a6ff"><span class="spinner"></span> Working...</div>`;
  }

  container.innerHTML = html;
}

// ── API Actions ─────────────────────────────────────────────────────────────

async function runPhase(phase) {
  if (!currentSessionId) return;
  try {
    await fetch(`${API}/sessions/${currentSessionId}/run/${phase}`, { method: 'POST' });
    await renderSession();
  } catch (e) {
    alert('Failed: ' + e.message);
  }
}

async function addNote() {
  const text = document.getElementById('inp-note').value.trim();
  if (!text) return;
  try {
    await fetch(`${API}/sessions/${currentSessionId}/notes`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ text }),
    });
    document.getElementById('inp-note').value = '';
    await renderSession();
  } catch (e) {
    console.error('Failed to add note:', e);
  }
}

async function addContext() {
  const text = document.getElementById('inp-add-context').value.trim();
  if (!text) return;
  try {
    await fetch(`${API}/sessions/${currentSessionId}/context`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ text }),
    });
    document.getElementById('inp-add-context').value = '';
    document.getElementById('add-evidence-section').classList.add('hidden');
  } catch (e) {
    console.error('Failed to add context:', e);
  }
}

async function updateInstructions() {
  const text = document.getElementById('inp-edit-instructions').value.trim();
  try {
    await fetch(`${API}/sessions/${currentSessionId}/instructions`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ instructions: text }),
    });
    document.getElementById('edit-instructions-section').classList.add('hidden');
  } catch (e) {
    console.error('Failed to update instructions:', e);
  }
}

// ── Polling ─────────────────────────────────────────────────────────────────

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    if (!currentSessionId) return;
    try {
      const res = await fetch(`${API}/sessions/${currentSessionId}/status`);
      const data = await res.json();
      if (data.status !== lastStatus) {
        await renderSession();
      }
    } catch (e) {
      console.error('Poll error:', e);
    }
  }, 3000);
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

// ── Utils ───────────────────────────────────────────────────────────────────

function escapeHtml(text) {
  if (!text) return '';
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Init ────────────────────────────────────────────────────────────────────

loadSessions();
