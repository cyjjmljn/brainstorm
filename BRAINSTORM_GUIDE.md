# Brainstorm Tool — Multi-Model Research Debate Platform

> Last updated: 2026-02-23

## What This Is

A structured research brainstorming tool that pits 4 AI models against each other in academic debate. Models take turns as supporters and opponents of a research idea, with role-swapping across rounds. A moderator (Claude Opus) summarizes each round and produces a final synthesis.

Two interfaces exist:
- **Web UI** at `http://100.99.160.75:8765` (mobile-first, Tailscale)
- **Discord agents** via OpenClaw (can read/write to the same session files)

Both interfaces share the same file-based sessions in `/Users/minime/research_project/brainstorm/sessions/`.

---

## Architecture

```
brainstorm/
├── src/
│   ├── main.py              ← FastAPI app + REST API routes
│   ├── models.py            ← Pydantic schemas (SessionState, RoundResponse, etc.)
│   ├── llm_client.py        ← Unified OpenAI-compatible async client (all 4 models)
│   ├── debate_engine.py     ← Round orchestration (parallel calls, state transitions)
│   ├── session_store.py     ← File I/O with atomic writes
│   └── prompts.py           ← All prompt templates + context builder
├── static/app.js            ← Frontend (polling, UI)
├── templates/index.html     ← Single-page mobile-first HTML
├── sessions/                ← All session data (see below)
├── requirements.txt
└── run.sh                   ← Start server (creates venv if needed)
```

### Tech Stack
- **Backend**: FastAPI + uvicorn (async)
- **Frontend**: Vanilla JS, no build step, mobile-first CSS
- **State**: File-based JSON + Markdown (no database)
- **LLM calls**: `openai.AsyncOpenAI` (all models use OpenAI-compatible endpoints)

---

## Models

| Short Name | Model | Endpoint | Cost |
|------------|-------|----------|------|
| `claude` | Claude Opus 4.6 | `localhost:3456` (Max subscription proxy) | $0 |
| `gemini` | Gemini 3.1 Pro | Google AI API | API credits |
| `qwen` | Qwen 3.5 Plus | DashScope API | API credits |
| `minimax` | MiniMax M2.5 | MiniMax API | API credits |

All models configured in `src/llm_client.py`. API keys loaded from `/Users/minime/.simulation.env`.

**Cost per round**: ~$0.05–0.15 for the 3 paid models combined (Claude is free via subscription).

---

## Debate Protocol

### Positions
- **S1, S2**: Supporters (defend the research idea)
- **O1, O2**: Opponents (attack the research idea)

Each position is assigned a model at session creation. Default: S1=Claude, S2=Gemini, O1=Qwen, O2=MiniMax.

### Round Flow

```
[Session Created] status=new
       │
       ▼
Round 1: All 4 models as neutral discussants (parallel)
       │  → round1.md saved
       │  → moderator summary generated
       ▼
   status=r1_pause  ← USER CAN: add notes, add context, edit instructions
       │
       │  User chooses: ⚔️ Debate  OR  🤝 Roundtable  OR  Synthesis
       ▼
  ┌─── Debate Round N ──────────────────────────────────┐
  │  Phase 1: Attackers argue against idea (parallel)   │
  │  Phase 2: Defenders respond to attacks (parallel)   │
  │  → debate_N_attacks.md + debate_N_defenses.md saved │
  │  → moderator summary generated                      │
  │                                                      │
  │  Odd rounds (1,3,5): O1+O2 attack, S1+S2 defend    │
  │  Even rounds (2,4,6): S1+S2 attack, O1+O2 defend   │
  │  (role swap to prevent stale arguments)             │
  └──────────────────────────────────────────────────────┘
       │
       ▼
   status=debate_N_pause  ← USER CAN: add notes, edit instructions, etc.
       │
       │  User can run MORE debate/roundtable rounds (no limit)
       ▼
  ┌─── Roundtable Round N ─────────────────────────────┐
  │  All 4 models as collaborative discussants          │
  │  No forced sides — models speak naturally           │
  │  Good for: exploring nuance, avoiding hallucinated  │
  │  arguments from forced opposition                   │
  │  → roundtable_N.md saved                            │
  └─────────────────────────────────────────────────────┘
       │
       ▼
  Synthesis: Claude Opus produces final analysis
       │  → synthesis.md saved
       ▼
   status=complete
       │
       ▼  (optional)
  New Stage: Reset round counter, keep all prior context
```

### Anti-Convergence Design

A key problem in multi-round AI debates is models converging on the same points. This is addressed by:

1. **Sliding window context**: Models see FULL responses from the most recent round + compressed summaries of older rounds. This ensures they can engage with specific arguments.
2. **Critical rules in all prompts**: Models MUST reference specific prior arguments, MUST NOT repeat points already raised, and MUST propose new angles.
3. **Role swapping**: Even-numbered debate rounds swap attacker/defender roles, forcing models to argue against positions they previously defended.
4. **Moderator summaries** include "Settled Issues" (arguments that were successfully rebutted and should NOT be raised again) and "Suggested New Angles" for future rounds.

### User Controls Between Rounds

- **Add Note**: Your thoughts are injected into every model's context for the next round. Use this to redirect discussion, ask specific questions, or push toward specific angles.
- **Add Context**: Additional background text or files added to the session's persistent background.
- **Edit Instructions**: Modify the system prompt for all future rounds (e.g., "請用中文討論" or "focus on methodology only").

---

## Session File System

### Directory Structure

```
sessions/
└── {session_id}/           ← e.g. 20260222-214809-682b85
    ├── session.json        ← SINGLE SOURCE OF TRUTH (full state)
    ├── round1.md           ← Human-readable Round 1 transcript
    ├── debate_1_attacks.md
    ├── debate_1_defenses.md
    ├── debate_2_attacks.md
    ├── debate_2_defenses.md
    ├── roundtable_3.md     ← (if roundtable mode was used)
    ├── synthesis.md        ← Final synthesis
    └── user_notes.md       ← All user notes appended
```

### session.json Schema

```json
{
  "session_id": "20260222-214809-682b85",
  "title": "portfolio choice paper's development",
  "idea": "The full research idea text...",
  "background": "Accumulated context (pasted text + imported files + prior session data)",
  "instructions": "請用中文討論，遇到關鍵學術語時標明英文。",
  "created_at": "2026-02-22T13:48:09.123456",
  "updated_at": "2026-02-22T23:01:45.789012",
  "status": "debate_3_pause",
  "stage": 1,
  "current_round": 3,
  "positions": [
    {"position": "S1", "model_name": "claude"},
    {"position": "S2", "model_name": "gemini"},
    {"position": "O1", "model_name": "qwen"},
    {"position": "O2", "model_name": "minimax"}
  ],
  "responses": [
    {
      "position": "S1",
      "model_name": "claude",
      "phase": "r1",
      "text": "Full model response text...",
      "tokens_in": 1234,
      "tokens_out": 890,
      "latency_ms": 15432.5,
      "error": null,
      "timestamp": "2026-02-22T13:49:00.000000"
    }
  ],
  "summaries": {
    "r1": "Moderator summary of Round 1...",
    "debate_1": "Moderator summary of Debate Round 1...",
    "debate_2": "Moderator summary of Debate Round 2..."
  },
  "user_notes": [
    {
      "stage": 1,
      "after_phase": "r1",
      "text": "Please focus more on the identification strategy.",
      "timestamp": "2026-02-22T14:00:00.000000"
    }
  ]
}
```

### Status State Machine

| Status | Meaning |
|--------|---------|
| `new` | Session created, ready for Round 1 |
| `r1_running` | Round 1 in progress (4 parallel calls) |
| `r1_pause` | Round 1 complete, waiting for user |
| `debate_N_attacks_running` | Debate round N attacks in progress |
| `debate_N_defenses_running` | Debate round N defenses in progress |
| `debate_N_pause` | Debate round N complete, waiting for user |
| `roundtable_N_running` | Roundtable round N in progress |
| `roundtable_N_pause` | Roundtable round N complete, waiting for user |
| `synthesis_running` | Final synthesis in progress |
| `complete` | Session complete (can start new stage) |

### Markdown Files

Each `.md` file in a session directory is a human-readable transcript. These are generated alongside `session.json` but are NOT the source of truth — `session.json` is. The markdown files are useful for:
- Reading in any markdown viewer (Obsidian, VS Code, etc.)
- Sharing with colleagues
- Importing as context into other tools

---

## Web UI vs Discord: How They Share Data

### What the Web UI Can Do

The web UI (`http://100.99.160.75:8765`) provides:
- Create new sessions with model assignments
- Run rounds (debate/roundtable/synthesis) with real-time polling
- Add notes and context between rounds
- Edit instructions mid-session
- Import context from previous sessions (dropdown picker)
- Browse local files and attach them as context
- View all rounds in collapsible cards

### What Discord Agents Can Do

OpenClaw Discord agents have **full filesystem access** to the sessions directory via `--add-dir /Users/minime/research_project`. This means:

1. **Read any session**: Read `sessions/{id}/session.json` to understand the full state, or read the `.md` files for human-readable transcripts.

2. **Read synthesis/summaries**: The `summaries` dict in session.json contains moderator summaries for every round. The `synthesis.md` file has the final analysis.

3. **Use sessions as context**: An agent can read a previous brainstorm session's synthesis and use it as context for a new task. For example:
   ```
   Read /Users/minime/research_project/brainstorm/sessions/20260222-214809-682b85/synthesis.md
   ```

4. **List all sessions**: Read every `session.json` to find sessions by title/status:
   ```
   ls /Users/minime/research_project/brainstorm/sessions/
   ```

5. **Cross-reference with research**: Since agents can also access `/Users/minime/research_project/`, they can connect brainstorm outputs with actual research files.

### What Discord Agents CANNOT Do (Currently)

- **Cannot run rounds via the web API** (no HTTP client in agent tools — they'd need to use `curl`).
- **Cannot create new sessions** through the web UI's workflow.
- **Cannot modify session.json directly** in a safe way (no atomic writes or lock management).

### Recommended Discord Workflow

For Discord agents that need brainstorm context:

```
1. List sessions:
   ls /Users/minime/research_project/brainstorm/sessions/

2. Read a session's state:
   cat sessions/{id}/session.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['title'], d['status'])"

3. Read the synthesis (if complete):
   cat sessions/{id}/synthesis.md

4. Read specific round transcripts:
   cat sessions/{id}/round1.md
   cat sessions/{id}/debate_1_attacks.md

5. Read moderator summaries (from session.json):
   python3 -c "import json; d=json.load(open('sessions/{id}/session.json')); [print(k,v[:200]) for k,v in d['summaries'].items()]"
```

### Future Integration Ideas

- Add a CLI command (`python -m brainstorm list/read/run`) for Discord agents to interact without the web UI
- Add a webhook that notifies Discord when a brainstorm round completes
- Allow Discord agents to call the REST API with `curl` to run rounds

---

## REST API Reference

Base URL: `http://100.99.160.75:8765/api`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sessions` | List all sessions (basic info) |
| `POST` | `/sessions` | Create new session |
| `GET` | `/sessions/{id}` | Full session state (JSON) |
| `GET` | `/sessions/{id}/status` | Lightweight status (for polling) |
| `POST` | `/sessions/{id}/run/{phase}` | Trigger a round: `r1`, `debate`, `roundtable`, `synthesis` |
| `POST` | `/sessions/{id}/notes` | Add user note `{"text": "..."}` |
| `POST` | `/sessions/{id}/context` | Add context `{"text": "...", "files": [...]}` |
| `POST` | `/sessions/{id}/instructions` | Update instructions `{"instructions": "..."}` |
| `POST` | `/sessions/{id}/new-stage` | Start new stage (resets round counter) |
| `GET` | `/sessions/{id}/files/{name}` | Get a markdown file from session dir |
| `POST` | `/local-files` | Browse local directories for file picker |

### Create Session Request

```json
{
  "title": "My Research Idea",
  "idea": "Detailed description of the research idea...",
  "background": "Optional pasted context",
  "background_files": ["/path/to/file.md"],
  "import_session": "20260222-214809-682b85",
  "instructions": "請用中文討論",
  "s1": "claude",
  "s2": "gemini",
  "o1": "qwen",
  "o2": "minimax"
}
```

---

## Running the Server

```bash
cd /Users/minime/research_project/brainstorm
bash run.sh
```

This creates a venv (if needed), installs dependencies, and starts uvicorn on `0.0.0.0:8765`.

### Dependencies

```
fastapi
uvicorn
openai
python-dotenv
jinja2
aiofiles
pydantic
```

---

## Known Behaviors and Fixes

1. **MiniMax thinking tags**: MiniMax M2.5 sometimes leaks `<think>...</think>` tags in output. These are stripped automatically in `llm_client.py`.

2. **Role reinforcement**: All prompts include the role in BOTH the system prompt AND user prompt (e.g., `## YOUR ROLE: O1 — OPPONENT`) because some models (especially MiniMax) ignore system prompts.

3. **Max tokens**: All models set to 16384 max output tokens. Prompts require "at least 800 words" (synthesis: "at least 1000 words").

4. **Moderator summaries**: Generated by Claude Opus after every round. Include "Settled Issues" and "Suggested New Angles" to prevent repetition.

5. **iOS mobile**: All form elements use 16px font-size to prevent Safari auto-zoom. Touch targets have explicit `touch-action: manipulation` CSS.

6. **Allowed file directories** (for file browser context import):
   - `/Users/minime/research_project/`
   - `/Users/minime/Documents/GitHub/`
   - `/Users/minime/GitHub/`
   - `/Users/minime/Library/Mobile Documents/iCloud~md~obsidian/`

   Allowed extensions: `.md`, `.txt`, `.csv`, `.json`, `.py`, `.tex`, `.bib`
