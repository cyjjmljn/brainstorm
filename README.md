# Brainstorm

**Let 4 AI models argue about your research ideas so you don't have to argue with yourself.**

Brainstorm is a local web app that runs structured academic debates between multiple AI models. You propose a research idea, and the models take turns supporting and attacking it from different angles — with role-swapping between rounds so no model gets stuck in one position. A moderator synthesizes everything into actionable feedback.

It runs entirely on your machine. Your ideas never leave your computer except as API calls to the model providers you configure.

![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Why This Exists

Getting real feedback on a research idea is unreasonably hard:

- **Submit to a journal** → wait 3 months for Reviewer 2 to tell you your identification strategy is "unconvincing"
- **Ask your supervisor** → your draft sits on their desk for a month, then they skim the abstract
- **Go to a seminar** → make small talk for 20 minutes, get one useful question if you're lucky
- **Argue with yourself in the shower** → doesn't count as peer review

Brainstorm gives you a structured academic debate in under 5 minutes. Four AI models independently assess your idea, then take turns attacking and defending it from different angles — with role-swapping so no model gets stuck in one position. A moderator synthesizes everything into actionable feedback.

For about **$1–2 per full session** (Round 1 + debate + synthesis), you get ~5,000 words of substantive critique — the kind that usually takes weeks of waiting or an entire seminar to extract. It won't replace real peer review, but it will catch the obvious holes before you waste months on a flawed approach.

It's especially useful for:
- **Early-stage research ideas** — stress-test before investing months of work
- **Grant proposals** — anticipate reviewer objections before the panel does
- **Paper drafts** — find the weak spots Reviewer 2 will find anyway
- **Methodology design** — get multiple perspectives on your identification strategy

### What Does It Cost?

A typical full session (Round 1 → 1 debate round → synthesis) makes ~13 API calls and generates ~5,000 words of feedback.

| Setup | Estimated Cost | Notes |
|-------|---------------|-------|
| All direct APIs (Claude + Gemini + Qwen + MiniMax) | ~$1.50 | Mixed pricing across providers |
| All via OpenRouter | ~$1–3 | Depends on model selection |
| Gemini-only (free tier) | $0 | Google AI Studio gives generous free quota |
| Local models (Ollama) | $0 | Just your electricity bill |

Costs scale with the number of debate rounds. Each additional round adds ~$0.30–0.80. The synthesis step is a single call to one model.

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

Copy `.env.example` to `.env` and configure for your situation. Brainstorm has 4 model "slots" — internally called `CLAUDE`, `GEMINI`, `QWEN`, `MINIMAX` — but you can put **any model** in any slot. The names are just labels.

**You need at least 2 working models** for a meaningful debate. Pick the setup that matches what you have:

---

### Scenario 1: Multiple API Keys (Power User)

You have accounts with multiple providers. Set each key directly:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
DASHSCOPE_API_KEY=sk-...
MINIMAX_API_KEY=eyJ...
```

That's it. Each model uses its default endpoint. This gives you the most diverse debate — different architectures, different training data, different blind spots.

| Model Slot | Default Provider | How to Get a Key | Free Tier? |
|------------|------------------|-----------------|------------|
| **Claude** | [Anthropic](https://console.anthropic.com/) | Create account → API Keys | No (pay-per-use) |
| **Gemini** | [Google AI Studio](https://aistudio.google.com/apikey) | Click "Create API Key" | Yes (generous) |
| **Qwen** | [DashScope](https://dashscope.console.aliyun.com/) | Sign up → API key | Yes (limited) |
| **MiniMax** | [MiniMax](https://platform.minimaxi.com/) | Sign up → API key | Yes (limited) |

---

### Scenario 2: One Provider, Multiple Models (OpenRouter, GitHub Copilot, etc.)

You only have one API key — say from [OpenRouter](https://openrouter.ai/) — but you want 4 different models debating. Use the **global fallback** variables:

```bash
# .env — OpenRouter example
BRAINSTORM_BASE_URL=https://openrouter.ai/api/v1
BRAINSTORM_API_KEY=sk-or-v1-...

# Pick 4 different models from your provider's catalog
CLAUDE_MODEL_ID=anthropic/claude-sonnet-4-6
GEMINI_MODEL_ID=google/gemini-3.1-pro-preview
QWEN_MODEL_ID=qwen/qwen3.5-plus
MINIMAX_MODEL_ID=minimax/minimax-m2.5
```

**How it works:** `BRAINSTORM_BASE_URL` and `BRAINSTORM_API_KEY` are global defaults. All 4 model slots use them unless overridden by per-model variables (like `CLAUDE_BASE_URL`).

<details>
<summary>More examples: GitHub Copilot, local models</summary>

**GitHub Copilot / Azure AI:**
```bash
BRAINSTORM_BASE_URL=https://models.inference.ai.azure.com
BRAINSTORM_API_KEY=ghp_...
CLAUDE_MODEL_ID=claude-sonnet-4-6
GEMINI_MODEL_ID=gemini-3.1-pro-preview
QWEN_MODEL_ID=Qwen3.5-Plus
MINIMAX_MODEL_ID=gpt-5-mini
```

**Local models (Ollama / LM Studio / vLLM):**
```bash
BRAINSTORM_BASE_URL=http://localhost:11434/v1
BRAINSTORM_API_KEY=not-needed
CLAUDE_MODEL_ID=llama4:maverick
GEMINI_MODEL_ID=qwen3:32b
QWEN_MODEL_ID=deepseek-r1:32b
MINIMAX_MODEL_ID=gemma3:27b
```

</details>

---

### Scenario 3: Proxy / Mixed Setup

You run a local proxy (e.g., for rate limiting, billing routing, or aggregation), or you want some models going through one provider and others through another. Override per-model:

```bash
# .env — Mix & match example
# Global default: OpenRouter for most models
BRAINSTORM_BASE_URL=https://openrouter.ai/api/v1
BRAINSTORM_API_KEY=sk-or-v1-...
GEMINI_MODEL_ID=google/gemini-3.1-pro-preview
QWEN_MODEL_ID=qwen/qwen3.5-plus
MINIMAX_MODEL_ID=minimax/minimax-m2.5

# Override: Claude goes direct to Anthropic
CLAUDE_BASE_URL=https://api.anthropic.com/v1/
CLAUDE_API_KEY=sk-ant-...
CLAUDE_MODEL_ID=claude-sonnet-4-6
```

```bash
# .env — Local proxy example
# All traffic goes through your proxy
BRAINSTORM_BASE_URL=http://localhost:3000/v1
BRAINSTORM_API_KEY=my-proxy-key

# Each slot uses a different upstream model via the proxy
CLAUDE_MODEL_ID=anthropic/claude-sonnet-4-6
GEMINI_MODEL_ID=google/gemini-3.1-pro-preview
QWEN_MODEL_ID=qwen/qwen3.5-plus
MINIMAX_MODEL_ID=minimax/minimax-m2.5
```

**Priority order:** Per-model variable (`CLAUDE_API_KEY`) > Global fallback (`BRAINSTORM_API_KEY`) > Provider-specific env var (`ANTHROPIC_API_KEY`). So if you already have per-model keys set, adding `BRAINSTORM_*` won't break anything.

---

### Using an External Env File

If you keep your API keys in a shared file (e.g., `~/.simulation.env`), point to it instead of duplicating keys:

```bash
# .env
ENV_FILE=/path/to/.simulation.env
```

Brainstorm loads `.env` first, then overlays `ENV_FILE` on top. Per-model overrides in `.env` still take priority.

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
- **Edit instructions** — Persistent instructions injected into every model's system prompt. You can set these at session creation or change them mid-session.

### Instructions (System Prompt)

Instructions control *how* the models behave — language, tone, length, focus area. They apply to every round until you change them. Set them when creating a session, or edit them anytime from the debate view.

**Example instructions:**

| Goal | Instruction |
|------|-------------|
| Language | `Respond in Chinese.` or `用中文討論。` |
| Length control | `Keep each response under 300 words.` |
| Tone | `Be ruthless. Pretend you're tenured.` |
| Focus area | `Focus on causal identification and endogeneity concerns.` |
| Methodology | `Assume we have access to administrative panel data. Discuss feasible estimators.` |
| Audience | `Write as if presenting to a grant review committee.` |
| Combined | `用中文回答。每段回應不超過500字。著重討論實驗設計的外部效度。` |

You can combine multiple instructions freely. They're just text — whatever you write gets prepended to the system prompt for all 4 models.

### Building on Previous Sessions

Every session is saved automatically. You can build on prior work in two ways:

**Import from a previous session** — When creating a new session, expand "Background Context" and select a previous session from the dropdown. Brainstorm imports its synthesis (or summaries if no synthesis exists) as background context for the new session. This lets you iterate: run a first session to explore broadly, then start a focused follow-up session that builds on what was already discussed.

**Start a new stage** — After synthesis, click "Start New Stage" to reset the debate cycle within the same session. All prior context (responses, summaries, notes) carries forward. Use this when you want to go deeper on the same idea without starting fresh.

**When to use which:**
- **Import** → the new idea is related but different (e.g., "Session 1 explored the theory; Session 2 focuses on experimental design")
- **New stage** → same idea, another round of refinement (e.g., "the models missed X, let me push them harder")

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
| **Global fallbacks** | | |
| `BRAINSTORM_BASE_URL` | — | Default base URL for all models (single-provider setup) |
| `BRAINSTORM_API_KEY` | — | Default API key for all models (single-provider setup) |
| **Per-provider keys** | | |
| `ANTHROPIC_API_KEY` | — | Anthropic API key for Claude |
| `GOOGLE_API_KEY` | — | Google API key for Gemini |
| `DASHSCOPE_API_KEY` | — | DashScope API key for Qwen |
| `MINIMAX_API_KEY` | — | MiniMax API key |
| **Per-model overrides** | | |
| `CLAUDE_MODEL_ID` | `claude-sonnet-4-6` | Model ID for the Claude slot |
| `CLAUDE_BASE_URL` | `https://api.anthropic.com/v1/` | API endpoint for Claude |
| `CLAUDE_API_KEY` | — | API key for Claude (overrides both global and `ANTHROPIC_API_KEY`) |
| `GEMINI_MODEL_ID` | `gemini-3.1-pro-preview` | Model ID for the Gemini slot |
| `QWEN_MODEL_ID` | `qwen3.5-plus` | Model ID for the Qwen slot |
| `MINIMAX_MODEL_ID` | `MiniMax-M2.5` | Model ID for the MiniMax slot |
| **Server** | | |
| `BRAINSTORM_PORT` | `8765` | Server port |
| `BRAINSTORM_ALLOWED_DIRS` | Project directory | Colon-separated paths for local file access |
| `ENV_FILE` | — | Path to an additional env file to load |

Each model slot (`CLAUDE`, `GEMINI`, `QWEN`, `MINIMAX`) supports `_MODEL_ID`, `_BASE_URL`, `_API_KEY`, and `_MAX_TOKENS` overrides. Priority: per-model > global fallback > provider-specific key > hardcoded default.

---

## License

[MIT](https://opensource.org/licenses/MIT) — do whatever you want with it. Use it, modify it, share it, build on it. No restrictions except keeping the license notice.
