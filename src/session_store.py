"""File-based session state management with atomic writes."""

import json
import uuid
from datetime import datetime
from pathlib import Path

from .models import SessionState, PositionAssignment, RoundResponse, UserNote

SESSIONS_DIR = Path("/Users/minime/research_project/brainstorm/sessions")


def create_session(title: str, idea: str, assignments: dict[str, str], background: str = "", instructions: str = "") -> SessionState:
    """Create a new brainstorm session."""
    session_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    positions = [
        PositionAssignment(position=pos, model_name=model)
        for pos, model in assignments.items()
    ]

    state = SessionState(
        session_id=session_id,
        title=title,
        idea=idea,
        background=background,
        instructions=instructions,
        positions=positions,
    )
    save_session(state)
    return state


def save_session(state: SessionState) -> None:
    """Atomic write: write to .tmp then rename."""
    state.updated_at = datetime.utcnow().isoformat()
    path = SESSIONS_DIR / state.session_id / "session.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    tmp.rename(path)


def load_session(session_id: str) -> SessionState:
    """Load session state from disk."""
    path = SESSIONS_DIR / session_id / "session.json"
    return SessionState.model_validate_json(path.read_text(encoding="utf-8"))


def list_sessions() -> list[dict]:
    """List all sessions with basic info."""
    sessions = []
    if not SESSIONS_DIR.exists():
        return sessions
    for d in sorted(SESSIONS_DIR.iterdir(), reverse=True):
        json_path = d / "session.json"
        if json_path.exists():
            try:
                state = SessionState.model_validate_json(json_path.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": state.session_id,
                    "title": state.title,
                    "status": state.status,
                    "stage": state.stage,
                    "created_at": state.created_at,
                    "updated_at": state.updated_at,
                })
            except Exception:
                pass
    return sessions


def update_status(session_id: str, status: str) -> None:
    """Update session status."""
    state = load_session(session_id)
    state.status = status
    save_session(state)


def append_response(session_id: str, response: RoundResponse) -> None:
    """Append a response and save atomically."""
    state = load_session(session_id)
    state.responses.append(response)
    save_session(state)


def update_summary(session_id: str, round_key: str, summary_text: str) -> None:
    """Update a round summary."""
    state = load_session(session_id)
    state.summaries[round_key] = summary_text
    save_session(state)


def append_note(session_id: str, note: UserNote) -> None:
    """Append a user note."""
    state = load_session(session_id)
    state.user_notes.append(note)
    save_session(state)

    # Also append to user_notes.md
    notes_path = SESSIONS_DIR / session_id / "user_notes.md"
    with open(notes_path, "a", encoding="utf-8") as f:
        f.write(f"\n## Note after {note.after_phase} (Stage {note.stage})\n\n")
        f.write(f"*{note.timestamp}*\n\n{note.text}\n\n---\n")


def save_markdown(session_id: str, filename: str, content: str) -> None:
    """Save a markdown file to the session directory."""
    path = SESSIONS_DIR / session_id / filename
    path.write_text(content, encoding="utf-8")


def get_responses_by_phase(session_id: str, phase: str) -> list[RoundResponse]:
    """Get all responses for a specific phase."""
    state = load_session(session_id)
    return [r for r in state.responses if r.phase == phase]
