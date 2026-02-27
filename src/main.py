"""FastAPI brainstorm web app."""

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import debate_engine, forge_engine, session_store
from .models import PositionAssignment, UserNote

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


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    path = BASE_DIR / "static" / "favicon.ico"
    if path.exists():
        return FileResponse(path, media_type="image/x-icon")
    return HTMLResponse(status_code=204)


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


# ── Forge Routes ─────────────────────────────────────────────────────────────

class CreateForgeRequest(BaseModel):
    title: str
    story: str = ""
    evidence: str = ""
    mode: str = "joint"            # "story_driven", "evidence_driven", "joint"
    background: str = ""
    background_files: list[str] = []
    instructions: str = ""
    w1: str = "claude"
    w2: str = "gemini"
    w3: str = "qwen"
    w4: str = "minimax"


@app.get("/forge", response_class=HTMLResponse)
async def forge_index(request: Request):
    return templates.TemplateResponse("forge.html", {"request": request})


@app.get("/api/forge/sessions")
async def api_forge_list():
    all_sessions = session_store.list_sessions()
    # Filter to forge sessions only
    forge_sessions = []
    for s in all_sessions:
        try:
            state = session_store.load_session(s["session_id"])
            if state.session_type == "forge":
                forge_sessions.append(s)
        except Exception:
            pass
    return forge_sessions


@app.post("/api/forge/sessions")
async def api_forge_create(req: CreateForgeRequest):
    background = build_background(text=req.background, files=req.background_files)
    # Build idea from story + evidence for display
    idea_parts = []
    if req.story:
        idea_parts.append(f"Story: {req.story[:200]}")
    if req.evidence:
        idea_parts.append(f"Evidence: {req.evidence[:200]}")
    idea = " | ".join(idea_parts) if idea_parts else req.title

    assignments = {"W1": req.w1, "W2": req.w2, "W3": req.w3, "W4": req.w4}
    state = session_store.create_session(req.title, idea, assignments, background, req.instructions)

    # Set forge-specific fields
    state.session_type = "forge"
    state.story = req.story
    state.evidence = req.evidence
    state.mode = req.mode
    session_store.save_session(state)

    return {"session_id": state.session_id, "status": state.status}


@app.get("/api/forge/sessions/{session_id}")
async def api_forge_get(session_id: str):
    try:
        state = session_store.load_session(session_id)
        return state.model_dump()
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")


@app.get("/api/forge/sessions/{session_id}/status")
async def api_forge_status(session_id: str):
    try:
        state = session_store.load_session(session_id)
        return {
            "status": state.status,
            "current_round": state.current_round,
            "mode": state.mode,
            "scores": state.scores,
            "best_draft": state.best_draft,
            "total_responses": len(state.responses),
            "has_summaries": list(state.summaries.keys()),
        }
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")


@app.post("/api/forge/sessions/{session_id}/run/{phase}")
async def api_forge_run(session_id: str, phase: str):
    try:
        state = session_store.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    lock = get_lock(session_id)

    if phase == "draft":
        if state.status != "new":
            raise HTTPException(400, f"Cannot run draft from status {state.status}")
        asyncio.create_task(forge_engine.run_draft(session_id, lock))

    elif phase == "refine":
        if not state.status.endswith("_pause"):
            raise HTTPException(400, f"Cannot refine from status {state.status}")
        asyncio.create_task(forge_engine.run_refine(session_id, lock))

    elif phase == "synthesis":
        if not state.status.endswith("_pause"):
            raise HTTPException(400, f"Cannot synthesize from status {state.status}")
        asyncio.create_task(forge_engine.run_synthesis(session_id, lock))

    else:
        raise HTTPException(400, f"Unknown phase: {phase}. Use draft, refine, or synthesis.")

    return {"status": "started", "phase": phase}


@app.post("/api/forge/sessions/{session_id}/notes")
async def api_forge_note(session_id: str, req: AddNoteRequest):
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


@app.post("/api/forge/sessions/{session_id}/context")
async def api_forge_context(session_id: str, req: AddContextRequest):
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
    return {"status": "context_added"}


@app.post("/api/forge/sessions/{session_id}/instructions")
async def api_forge_instructions(session_id: str, req: UpdateInstructionsRequest):
    try:
        state = session_store.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    state.instructions = req.instructions
    session_store.save_session(state)
    return {"status": "updated"}


class UpdateModeRequest(BaseModel):
    mode: str


@app.post("/api/forge/sessions/{session_id}/mode")
async def api_forge_mode(session_id: str, req: UpdateModeRequest):
    if req.mode not in ("story_driven", "evidence_driven", "joint"):
        raise HTTPException(400, f"Invalid mode: {req.mode}")
    try:
        state = session_store.load_session(session_id)
    except FileNotFoundError:
        raise HTTPException(404, "Session not found")

    state.mode = req.mode
    session_store.save_session(state)
    return {"status": "updated", "mode": req.mode}


@app.get("/api/forge/sessions/{session_id}/files/{filename}")
async def api_forge_file(session_id: str, filename: str):
    path = session_store.SESSIONS_DIR / session_id / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return {"content": path.read_text(encoding="utf-8")}
