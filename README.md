# Brainstorm

**Let 4 AI models argue about your research ideas so you don't have to argue with yourself.**

Brainstorm is a local web app that runs structured academic debates between multiple AI models. You propose a research idea, and the models take turns supporting and attacking it from different angles — with role-swapping between rounds so no model gets stuck in one position. A moderator synthesizes everything into actionable feedback.

It runs entirely on your machine. Your ideas never leave your computer except as API calls to the model providers you configure.

![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Why This Exists

When you're developing a research idea, you need someone to push back on it — but it's hard to get that kind of structured feedback quickly. Brainstorm simulates an academic seminar where multiple perspectives clash, evolve, and eventually converge on the strongest version of your idea.

It's especially useful for:
- **Early-stage research ideas** — stress-test before investing months of work
- **Grant proposals** — anticipate reviewer objections
- **Paper drafts** — find the weak spots in your argument
- **Methodology design** — get multiple perspectives on your approach

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/cyjjmljn/brainstorm.git
cd brainstorm

# 2. Set up API keys
cp .env.example .env
# Open .env in any text editor and paste your API keys

# 3. Run
bash run.sh
```

That's it. Open `http://localhost:8765` in your browser.

**Requirements:** Python 3.10+ (the script creates a virtual environment automatically).

---

## Setting Up API Keys

Copy `.env.example` to `.env` and fill in your keys. **You need at least 2 models** for a meaningful debate — the more models, the more diverse the perspectives.

| Model | Provider | How to Get a Key | Free Tier? |
|-------|----------|-----------------|------------|
| **Claude** | [Anthropic](https://console.anthropic.com/) | Create account, go to API Keys | No (pay-per-use) |
| **Gemini** | [Google AI Studio](https://aistudio.google.com/apikey) | Click "Create API Key" | Yes (generous free tier) |
| **Qwen** | [DashScope](https://dashscope.console.aliyun.com/) | Sign up, get API key | Yes (limited free credits) |
| **MiniMax** | [MiniMax](https://platform.minimaxi.com/) | Sign up, get API key | Yes (limited free credits) |

If you only have one or two API keys, that's fine — just fill in what you have.

### Using Other Models

Any model with an OpenAI-compatible API works. Override the endpoint in `.env`:

```bash
# Example: use a local Ollama model instead of Claude
CLAUDE_BASE_URL=http://localhost:11434/v1
CLAUDE_MODEL_ID=llama3
CLAUDE_API_KEY=not-needed

# Example: use OpenAI's GPT models
CLAUDE_BASE_URL=https://api.openai.com/v1
CLAUDE_MODEL_ID=gpt-4o
CLAUDE_API_KEY=sk-your-openai-key
```

---

## How It Works

### The Debate Flow

```
 You write a research idea
         |
         v
   Round 1 (Neutral)          All 4 models independently assess your idea
         |                     — strengths, weaknesses, directions, questions
         v
   Moderator Summary           Synthesizes Round 1 into key themes
         |
         v
   Debate Round 1              S1, S2 attack  /  O1, O2 defend
         |                     (or vice versa — roles are assigned)
         v
   Moderator Summary           What was argued, what was conceded
         |
    [You can add notes here to steer the discussion]
         |
         v
   Debate Round 2              Roles SWAP — last round's attackers now defend
         |                     They know the defense's weak points from the inside
         v
   ... more rounds ...         Keep going until you're satisfied
         |
         v
   Final Synthesis             Comprehensive summary of all arguments,
                               concessions, open questions, and next steps
```

### Three Discussion Modes

**Debate Rounds** — Adversarial. Two models attack, two defend. Roles swap each round so everyone experiences both sides. This is the core feature — it produces the sharpest, most rigorous feedback.

**Roundtable Rounds** — Collaborative. All models discuss freely as colleagues, without assigned sides. Useful when you want constructive brainstorming rather than adversarial stress-testing. You can alternate between debate and roundtable rounds.

**Synthesis** — The moderator produces a comprehensive final report covering the strongest arguments for and against, unresolved questions, conditions for validity, and recommended next steps.

### Steering the Discussion

Between any two rounds, you can:

- **Add notes** — Tell the models what to focus on, ask specific questions, or redirect the discussion. Notes are included in the context for all subsequent rounds.
- **Add context** — Paste text or attach local files (papers, data descriptions, methodology notes) as background information.
- **Set instructions** — Persistent instructions that apply to all rounds (e.g., "Respond in Chinese", "Focus on causal identification", "Assume we have access to administrative data").

### Session Persistence

Every session is saved as JSON + Markdown files in the `sessions/` folder. You can close the browser and come back later — your sessions are still there. You can also import the synthesis from a previous session as background for a new one, building on prior brainstorming.

---

## API Reference

All functionality is available through a REST API, so you can integrate Brainstorm into other tools or scripts.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/sessions` | List all sessions |
| `POST` | `/api/sessions` | Create a new session |
| `GET` | `/api/sessions/{id}` | Get full session data |
| `GET` | `/api/sessions/{id}/status` | Lightweight status check (for polling) |
| `POST` | `/api/sessions/{id}/run/r1` | Start Round 1 (neutral assessment) |
| `POST` | `/api/sessions/{id}/run/debate` | Start a debate round |
| `POST` | `/api/sessions/{id}/run/roundtable` | Start a roundtable round |
| `POST` | `/api/sessions/{id}/run/synthesis` | Generate final synthesis |
| `POST` | `/api/sessions/{id}/notes` | Add a user note |
| `POST` | `/api/sessions/{id}/context` | Add background context (text/files) |
| `POST` | `/api/sessions/{id}/instructions` | Update session instructions |

Rounds run asynchronously — the API returns `202 Accepted` immediately and you poll `/api/sessions/{id}/status` until completion.

---

## Project Structure

```
brainstorm/
├── src/
│   ├── main.py           ← Web server and API routes
│   ├── llm_client.py     ← Talks to all AI models (OpenAI-compatible)
│   ├── debate_engine.py  ← Orchestrates rounds (parallel API calls)
│   ├── prompts.py        ← All prompt templates
│   ├── models.py         ← Data schemas
│   └── session_store.py  ← File-based session storage
├── static/app.js         ← Frontend logic
├── templates/index.html  ← Single-page UI (mobile-friendly)
├── sessions/             ← Your session data (gitignored)
├── .env                  ← Your API keys (gitignored)
├── .env.example          ← Template for .env
├── requirements.txt      ← Python dependencies
└── run.sh                ← Start script
```

**Tech stack:** FastAPI (async Python), vanilla JavaScript (no build step), file-based storage (no database).

---

## Configuration Reference

All configuration is done through environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic API key for Claude |
| `GOOGLE_API_KEY` | — | Google API key for Gemini |
| `DASHSCOPE_API_KEY` | — | DashScope API key for Qwen |
| `MINIMAX_API_KEY` | — | MiniMax API key |
| `CLAUDE_MODEL_ID` | `claude-sonnet-4-6` | Model ID for the Claude slot |
| `CLAUDE_BASE_URL` | `https://api.anthropic.com/v1/` | API endpoint for Claude |
| `GEMINI_MODEL_ID` | `gemini-2.5-pro` | Model ID for the Gemini slot |
| `QWEN_MODEL_ID` | `qwen-plus` | Model ID for the Qwen slot |
| `MINIMAX_MODEL_ID` | `MiniMax-M2.5` | Model ID for the MiniMax slot |
| `BRAINSTORM_PORT` | `8765` | Server port |
| `BRAINSTORM_ALLOWED_DIRS` | Project directory | Colon-separated paths for local file access |
| `ENV_FILE` | — | Path to an additional env file to load |

Each model slot (`CLAUDE`, `GEMINI`, `QWEN`, `MINIMAX`) supports `_MODEL_ID`, `_BASE_URL`, `_API_KEY`, and `_MAX_TOKENS` overrides.

---

## License

[MIT](https://opensource.org/licenses/MIT) — do whatever you want with it. Use it, modify it, share it, build on it. No restrictions except keeping the license notice.
