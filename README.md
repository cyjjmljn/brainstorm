# Brainstorm — Multi-Model Research Debate Platform

A structured research brainstorming tool that uses 4 AI models in academic debate format. Models take turns as supporters and opponents of your research idea, with role-swapping across rounds. A moderator summarizes each round and produces a final synthesis.

**How it works:** You propose a research idea. Four AI models independently assess it (Round 1), then engage in structured debate rounds where they attack and defend the idea from different angles. A moderator synthesizes all arguments into actionable feedback.

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/brainstorm.git
cd brainstorm

# 2. Configure API keys
cp .env.example .env
# Edit .env with your API keys (you need at least 2 models)

# 3. Run
bash run.sh
# Opens at http://localhost:8765
```

Requires Python 3.10+.

## Configuration

Copy `.env.example` to `.env` and add your API keys. You need at least 2 models configured for a meaningful debate.

| Model | Provider | API Key Variable | Free Tier? |
|-------|----------|-----------------|------------|
| Claude | Anthropic | `ANTHROPIC_API_KEY` | No |
| Gemini | Google | `GOOGLE_API_KEY` | Yes (limited) |
| Qwen | Alibaba (DashScope) | `DASHSCOPE_API_KEY` | Yes (limited) |
| MiniMax | MiniMax | `MINIMAX_API_KEY` | Yes (limited) |

You can override any model's endpoint, model ID, or max tokens via environment variables. See `.env.example` for details.

### Using with other OpenAI-compatible providers

Any model with an OpenAI-compatible API works. Override the base URL and model ID:

```bash
# Example: use a local Ollama model as "claude"
CLAUDE_BASE_URL=http://localhost:11434/v1
CLAUDE_MODEL_ID=llama3
CLAUDE_API_KEY=not-needed
```

## How a Session Works

```
 Your Idea
    │
    ▼
 Round 1 (Neutral)     ← All 4 models independently assess the idea
    │
    ▼
 Moderator Summary     ← Synthesizes Round 1 findings
    │
    ▼
 Debate Rounds (1..N)  ← Models attack/defend with role-swapping
    │                      (you can add notes between rounds)
    ▼
 Synthesis             ← Final moderator synthesis of all rounds
```

**Debate format:**
- **S1, S2** (Supporters): Defend the idea, propose improvements
- **O1, O2** (Opponents): Challenge assumptions, find weaknesses
- Roles swap each round — last round's defenders become attackers

**You can:**
- Add notes/context between rounds to steer the debate
- Run as many debate rounds as you want
- Run "roundtable" rounds (collaborative instead of adversarial)
- Import context from previous sessions
- Attach local files as background context

## Architecture

```
brainstorm/
├── src/
│   ├── main.py           ← FastAPI app + REST API
│   ├── models.py         ← Pydantic schemas
│   ├── llm_client.py     ← Unified async LLM client
│   ├── debate_engine.py  ← Round orchestration
│   ├── session_store.py  ← File-based state (JSON + Markdown)
│   └── prompts.py        ← Prompt templates
├── static/app.js         ← Frontend (vanilla JS)
├── templates/index.html  ← Single-page mobile-first UI
├── sessions/             ← Session data (gitignored)
├── .env.example          ← API key template
├── requirements.txt
└── run.sh                ← Start script
```

- **Backend:** FastAPI + uvicorn (async Python)
- **Frontend:** Vanilla JavaScript, no build step, mobile-first
- **State:** File-based JSON + Markdown (no database needed)
- **LLM calls:** All models via OpenAI-compatible `openai.AsyncOpenAI`

## REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sessions` | Create a new session |
| `GET` | `/api/sessions` | List all sessions |
| `GET` | `/api/sessions/{id}` | Get full session state |
| `GET` | `/api/sessions/{id}/status` | Lightweight status (for polling) |
| `POST` | `/api/sessions/{id}/run/r1` | Start Round 1 |
| `POST` | `/api/sessions/{id}/run/debate` | Start a debate round |
| `POST` | `/api/sessions/{id}/run/roundtable` | Start a roundtable round |
| `POST` | `/api/sessions/{id}/run/synthesis` | Generate final synthesis |
| `POST` | `/api/sessions/{id}/notes` | Add a user note |
| `POST` | `/api/sessions/{id}/context` | Add background context |
| `POST` | `/api/sessions/{id}/instructions` | Update session instructions |

## License

MIT
