"""FastAPI brainstorm web app."""

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import debate_engine, session_store
from .models import UserNote

BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="Brainstorm")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Per-session locks for atomic state updates
_session_locks: dict[str, asyncio.Lock] = {}


def get_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


# ── Request schemas ──────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    title: str
    idea: str
    background: str = ""       # pasted text context
    background_files: list[str] = []  # local file paths to read
    import_session: str = ""   # session_id to import synthesis from
    instructions: str = ""     # persistent instructions for all rounds (e.g. "use Chinese")
    s1: str = "claude"
    s2: str = "gemini"
    o1: str = "qwen"
    o2: str = "minimax"


class AddNoteRequest(BaseModel):
    text: str


class AddContextRequest(BaseModel):
    text: str = ""
    files: list[str] = []


# ── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Helper: read local files for context ─────────────────────────────────────

# Directories allowed for local file reading (context import feature).
# Override via BRAINSTORM_ALLOWED_DIRS env var (colon-separated paths).
_default_allowed = [str(BASE_DIR)]
_env_dirs = os.environ.get("BRAINSTORM_ALLOWED_DIRS", "")
ALLOWED_DIRS = [d for d in _env_dirs.split(":") if d] if _env_dirs else _default_allowed
ALLOWED_EXTENSIONS = {".md", ".txt", ".csv", ".json", ".py", ".tex", ".bib"}


def read_local_file(filepath: str) -> str:
    """Read a local file if it's in an allowed directory and has allowed extension."""
    p = Path(filepath).resolve()
    if not any(str(p).startswith(d) for d in ALLOWED_DIRS):
        raise ValueError(f"File not in allowed directory: {filepath}")
    if p.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File type not allowed: {p.suffix}")
    if not p.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    content = p.read_text(encoding="utf-8", errors="replace")
    # Truncate very large files
    if len(content) > 50000:
        content = content[:50000] + "\n\n[... truncated at 50,000 characters ...]"
    return content


def build_background(
    text: str = "",
    files: list[str] = None,
    import_session_id: str = "",
) -> str:
    """Build background context from text, files, and/or previous session."""
    parts = []

    if text.strip():
        parts.append(f"## Background Context\n\n{text.strip()}")

    if files:
        for fpath in files:
            try:
                content = read_local_file(fpath)
                fname = Path(fpath).name
                parts.append(f"## File: {fname}\n\n```\n{content}\n```")
            except Exception as e:
                parts.append(f"## File: {fpath}\n\n(Error reading: {e})")

    if import_session_id:
        try:
            prev = session_store.load_session(import_session_id)
            import_parts = [f"## Previous Brainstorm: {prev.title}\n\n### Original Idea\n\n{prev.idea}"]

            # Import synthesis if available
            synth = prev.summaries.get("synthesis", "")
            if not synth:
                synth_responses = [r for r in prev.responses if r.phase == "synthesis"]
                if synth_responses:
                    synth = synth_responses[-1].text
            if synth:
                import_parts.append(f"### Synthesis\n\n{synth}")

            # If no synthesis, import all available summaries
            if not synth:
                for key, summary in sorted(prev.summaries.items()):
                    import_parts.append(f"### {key.replace('_', ' ').title()} Summary\n\n{summary}")

            parts.append("\n\n".join(import_parts))
        except Exception as e:
            parts.append(f"## Import Error\n\n(Could not import session {import_session_id}: {e})")

    return "\n\n---\n\n".join(parts)


# ── API Routes ───────────────────────────────────────────────────────────────

@app.get("/api/sessions")
async def api_list_sessions():
    return session_store.list_sessions()


@app.post("/api/sessions")
async def api_create_session(req: CreateSessionRequest):
    background = build_background(
        text=req.background,
        files=req.background_files,
        import_session_id=req.import_session,
    )
    assignments = {"S1": req.s1, "S2": req.s2, "O1": req.o1, "O2": req.o2}
    state = session_store.create_session(req.title, req.idea, assignments, background, req.instructions)
    return {"session_id": state.session_id, "status": state.status}


@app.get("/api/sessions/{session_id}")
async def api_get_session(session_id: str):
    try:
        state = session_store.load_session(session_id)
        return state.model_dump()
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")


@app.get("/api/sessions/{session_id}/status")
async def api_session_status(session_id: str):
    """Lightweight status endpoint for polling."""
    try:
        state = session_store.load_session(session_id)
        phase_counts = {}
        for r in state.responses:
            phase_counts[r.phase] = phase_counts.get(r.phase, 0) + 1

        return {
            "status": state.status,
            "stage": state.stage,
            "current_round": state.current_round,
            "phase_counts": phase_counts,
            "total_responses": len(state.responses),
            "has_summaries": list(state.summaries.keys()),
        }
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")


@app.post("/api/sessions/{session_id}/run/{phase}")
async def api_run_phase(session_id: str, phase: str):
    """Trigger a round. Returns 202 immediately; frontend polls status.

    Phases:
    - r1: neutral discussion (only once per stage)
    - debate: attack+defense round (can repeat infinitely)
    - synthesis: final synthesis
    """
    try:
        state = session_store.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    lock = get_lock(session_id)

    if phase == "r1":
        if state.status not in ("new",):
            raise HTTPException(400, f"Cannot run r1 from status {state.status}")
        asyncio.create_task(debate_engine.run_round1(session_id, lock))

    elif phase == "debate":
        # Can run from r1_pause or any debate/roundtable pause
        if not (state.status == "r1_pause" or state.status.endswith("_pause")):
            raise HTTPException(400, f"Cannot run debate from status {state.status}")
        asyncio.create_task(debate_engine.run_debate_round(session_id, lock))

    elif phase == "roundtable":
        # Collaborative discussion — same entry conditions as debate
        if not (state.status == "r1_pause" or state.status.endswith("_pause")):
            raise HTTPException(400, f"Cannot run roundtable from status {state.status}")
        asyncio.create_task(debate_engine.run_roundtable(session_id, lock))

    elif phase == "synthesis":
        if not state.status.endswith("_pause"):
            raise HTTPException(400, f"Cannot synthesize from status {state.status}")
        asyncio.create_task(debate_engine.run_synthesis(session_id, lock))

    else:
        raise HTTPException(400, f"Unknown phase: {phase}. Use r1, debate, or synthesis.")

    return {"status": "started", "phase": phase}


@app.post("/api/sessions/{session_id}/notes")
async def api_add_note(session_id: str, req: AddNoteRequest):
    try:
        state = session_store.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    note = UserNote(
        stage=state.stage,
        after_phase=state.status.replace("_pause", ""),
        text=req.text,
    )
    session_store.append_note(session_id, note)
    return {"status": "added"}


@app.post("/api/sessions/{session_id}/context")
async def api_add_context(session_id: str, req: AddContextRequest):
    """Add additional context (text or files) to an existing session."""
    try:
        state = session_store.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    new_context = build_background(text=req.text, files=req.files)
    if state.background:
        state.background += "\n\n---\n\n" + new_context
    else:
        state.background = new_context
    session_store.save_session(state)
    return {"status": "context_added", "background_length": len(state.background)}


class UpdateInstructionsRequest(BaseModel):
    instructions: str


@app.post("/api/sessions/{session_id}/instructions")
async def api_update_instructions(session_id: str, req: UpdateInstructionsRequest):
    """Update session instructions mid-session."""
    try:
        state = session_store.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    state.instructions = req.instructions
    session_store.save_session(state)
    return {"status": "updated"}


@app.post("/api/sessions/{session_id}/new-stage")
async def api_new_stage(session_id: str):
    """Start a new stage (repeat the cycle with accumulated context)."""
    try:
        state = session_store.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    if state.status != "complete":
        raise HTTPException(400, "Session must be complete to start new stage")

    state.stage += 1
    state.current_round = 0
    state.status = "new"
    session_store.save_session(state)
    return {"status": "new_stage", "stage": state.stage}


@app.get("/api/sessions/{session_id}/files/{filename}")
async def api_get_file(session_id: str, filename: str):
    """Get a markdown file from the session directory."""
    path = session_store.SESSIONS_DIR / session_id / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return {"content": path.read_text(encoding="utf-8")}


@app.post("/api/local-files")
async def api_list_local_files(req: dict):
    """List files in a local directory (for file picker)."""
    dirpath = req.get("path", "")
    if not dirpath:
        return {"files": [], "dirs": list(ALLOWED_DIRS)}

    p = Path(dirpath).resolve()
    if not any(str(p).startswith(d) for d in ALLOWED_DIRS):
        raise HTTPException(403, "Directory not in allowed list")
    if not p.is_dir():
        raise HTTPException(404, "Not a directory")

    items = []
    try:
        for child in sorted(p.iterdir()):
            if child.name.startswith("."):
                continue
            if child.is_dir():
                items.append({"name": child.name, "type": "dir", "path": str(child)})
            elif child.suffix.lower() in ALLOWED_EXTENSIONS:
                items.append({"name": child.name, "type": "file", "path": str(child)})
    except PermissionError:
        pass

    return {"files": items, "current": str(p)}
