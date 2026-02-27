"""Forge orchestration engine — competitive paper introduction improvement."""

import asyncio
import json
import re
from datetime import datetime

from . import llm_client, forge_prompts, session_store
from .models import RoundResponse


def _get_model_for_position(session_state, position: str) -> str:
    """Get the model name assigned to a position."""
    for pa in session_state.positions:
        if pa.position == position:
            return pa.model_name
    raise ValueError(f"No model assigned to position {position}")


async def _call_and_record(
    session_id: str,
    position: str,
    model_name: str,
    phase: str,
    system_prompt: str,
    user_prompt: str,
    lock: asyncio.Lock,
) -> RoundResponse:
    """Call a model and record the response atomically."""
    result = await llm_client.call_model(model_name, system_prompt, user_prompt)

    response = RoundResponse(
        position=position,
        model_name=model_name,
        phase=phase,
        text=result.text,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        latency_ms=result.latency_ms,
        error=result.error,
    )

    async with lock:
        session_store.append_response(session_id, response)

    return response


def _parse_judge_scores(judge_text: str) -> dict | None:
    """Extract structured scores from judge response."""
    # Look for JSON block in the judge's response
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', judge_text, re.DOTALL)
    if not json_match:
        # Try without code fence
        json_match = re.search(r'(\{"scores".*?\})\s*\n', judge_text, re.DOTALL)
    if not json_match:
        return None

    try:
        data = json.loads(json_match.group(1))
        return data
    except json.JSONDecodeError:
        return None


async def _run_judge(
    session_id: str,
    phase_key: str,
    session_state,
    draft_phase: str,
    lock: asyncio.Lock,
) -> str:
    """Run the judge on all drafts from a given phase."""
    responses = [r for r in session_state.responses if r.phase == draft_phase and not r.error]

    # Build draft sections for judge prompt
    draft_texts = {}
    model_names = {}
    for r in responses:
        draft_texts[r.position] = r.text
        model_names[r.position] = r.model_name

    positions = ["W1", "W2", "W3", "W4"]
    story_section = forge_prompts.build_story_section(session_state.story)
    evidence_section = forge_prompts.build_evidence_section(session_state.evidence)

    user_prompt = forge_prompts.JUDGE_USER.format(
        story_section=story_section,
        evidence_section=evidence_section,
        model_1=model_names.get("W1", "unknown"),
        model_2=model_names.get("W2", "unknown"),
        model_3=model_names.get("W3", "unknown"),
        model_4=model_names.get("W4", "unknown"),
        draft_w1=draft_texts.get("W1", "(no draft)"),
        draft_w2=draft_texts.get("W2", "(no draft)"),
        draft_w3=draft_texts.get("W3", "(no draft)"),
        draft_w4=draft_texts.get("W4", "(no draft)"),
    )

    system = forge_prompts.inject_instructions(
        forge_prompts.JUDGE_SYSTEM, session_state.instructions
    )

    result = await llm_client.call_model("claude", system, user_prompt)

    # Record judge response
    judge_response = RoundResponse(
        position="judge",
        model_name="claude",
        phase=f"{phase_key}_judge",
        text=result.text,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        latency_ms=result.latency_ms,
        error=result.error,
    )
    async with lock:
        session_store.append_response(session_id, judge_response)
        session_store.update_summary(session_id, f"{phase_key}_judge", result.text)

    # Parse scores and update session
    parsed = _parse_judge_scores(result.text)
    if parsed:
        async with lock:
            state = session_store.load_session(session_id)
            state.scores[phase_key] = parsed.get("scores", {})
            state.best_draft = parsed.get("winner", "")
            session_store.save_session(state)

    return result.text


async def run_draft(session_id: str, lock: asyncio.Lock):
    """Draft round: All 4 models write independent introductions in parallel."""
    session_store.update_status(session_id, "draft_running")
    state = session_store.load_session(session_id)

    mode_desc = forge_prompts.MODE_DESCRIPTIONS.get(state.mode, forge_prompts.MODE_DESCRIPTIONS["joint"])
    story_section = forge_prompts.build_story_section(state.story)
    evidence_section = forge_prompts.build_evidence_section(state.evidence)
    context = forge_prompts.build_context_section(state.background, state.user_notes)

    tasks = []
    for pos in ["W1", "W2", "W3", "W4"]:
        model_name = _get_model_for_position(state, pos)
        system = forge_prompts.inject_instructions(
            forge_prompts.DRAFT_SYSTEM.format(
                model_name=model_name,
                mode_description=mode_desc,
            ),
            state.instructions,
        )
        user = forge_prompts.DRAFT_USER.format(
            story_section=story_section,
            evidence_section=evidence_section,
            context=context,
        )
        tasks.append(_call_and_record(session_id, pos, model_name, "draft", system, user, lock))

    results = await asyncio.gather(*tasks)

    # Save markdown export
    md_parts = [
        f"# Forge — Draft Round\n\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | Mode: {state.mode}\n\n"
        f"**Story:** {state.story[:200]}{'...' if len(state.story) > 200 else ''}\n\n"
        f"**Evidence:** {state.evidence[:200]}{'...' if len(state.evidence) > 200 else ''}\n"
    ]
    for r in results:
        status = f"**ERROR: {r.error}**" if r.error else r.text
        md_parts.append(f"## {r.position} — {r.model_name}\n\n{status}\n")
    session_store.save_markdown(session_id, "draft.md", "\n---\n\n".join(md_parts))

    # Run judge
    session_store.update_status(session_id, "draft_judging")
    state = session_store.load_session(session_id)  # reload with new responses
    judge_text = await _run_judge(session_id, "draft", state, "draft", lock)

    # Save judge markdown
    session_store.save_markdown(session_id, "draft_judge.md",
        f"# Forge — Draft Round Judge\n\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"{judge_text}\n"
    )

    # Update round counter
    state = session_store.load_session(session_id)
    state.current_round = 1
    session_store.save_session(state)

    session_store.update_status(session_id, "draft_pause")


async def run_refine(session_id: str, lock: asyncio.Lock):
    """Refine round: All 4 models try to beat the current best."""
    state = session_store.load_session(session_id)
    round_num = state.current_round + 1
    refine_phase = f"refine_{round_num}"

    session_store.update_status(session_id, f"refine_{round_num}_running")

    mode_desc = forge_prompts.MODE_DESCRIPTIONS.get(state.mode, forge_prompts.MODE_DESCRIPTIONS["joint"])
    story_section = forge_prompts.build_story_section(state.story)
    evidence_section = forge_prompts.build_evidence_section(state.evidence)
    context = forge_prompts.build_context_section(state.background, state.user_notes)

    # Find current best draft text
    best_pos = state.best_draft
    best_model = "unknown"
    best_text = "(no previous best)"
    best_score = 0

    # Determine which phase to pull the best from
    if round_num == 2:
        prev_phase = "draft"
        prev_judge_key = "draft"
    else:
        prev_phase = f"refine_{round_num - 1}"
        prev_judge_key = f"refine_{round_num - 1}"

    for r in state.responses:
        if r.position == best_pos and r.phase == prev_phase and not r.error:
            best_text = r.text
            best_model = r.model_name
            break

    # Get best score
    prev_scores = state.scores.get(prev_judge_key, {})
    if best_pos in prev_scores:
        best_score = prev_scores[best_pos].get("total", 0)

    # Get judge critique
    judge_key = f"{prev_judge_key}_judge"
    judge_critique = state.summaries.get(judge_key, "(no judge critique available)")

    # Get all drafts from previous round
    all_drafts = forge_prompts.build_all_drafts_text(state.responses, prev_phase)

    tasks = []
    for pos in ["W1", "W2", "W3", "W4"]:
        model_name = _get_model_for_position(state, pos)
        system = forge_prompts.inject_instructions(
            forge_prompts.REFINE_SYSTEM.format(
                model_name=model_name,
                round_num=round_num,
                mode_description=mode_desc,
                best_score=best_score,
            ),
            state.instructions,
        )
        user = forge_prompts.REFINE_USER.format(
            best_model=best_model,
            best_score=best_score,
            best_draft=best_text,
            judge_critique=judge_critique,
            all_drafts=all_drafts,
            story_section=story_section,
            evidence_section=evidence_section,
            context=context,
        )
        tasks.append(_call_and_record(
            session_id, pos, model_name, refine_phase, system, user, lock
        ))

    results = await asyncio.gather(*tasks)

    # Save markdown
    md_parts = [
        f"# Forge — Refine Round {round_num}\n\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        f"Previous best: {best_pos} ({best_model}) score {best_score}/50\n"
    ]
    for r in results:
        status = f"**ERROR: {r.error}**" if r.error else r.text
        md_parts.append(f"## {r.position} — {r.model_name}\n\n{status}\n")
    session_store.save_markdown(session_id, f"refine_{round_num}.md", "\n---\n\n".join(md_parts))

    # Run judge
    session_store.update_status(session_id, f"refine_{round_num}_judging")
    state = session_store.load_session(session_id)
    judge_text = await _run_judge(session_id, f"refine_{round_num}", state, refine_phase, lock)

    # Save judge markdown
    session_store.save_markdown(session_id, f"refine_{round_num}_judge.md",
        f"# Forge — Refine Round {round_num} Judge\n\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"{judge_text}\n"
    )

    # Update round counter
    state = session_store.load_session(session_id)
    state.current_round = round_num
    session_store.save_session(state)

    session_store.update_status(session_id, f"refine_{round_num}_pause")


async def run_synthesis(session_id: str, lock: asyncio.Lock):
    """Final synthesis: produce polished introduction + gap analysis."""
    session_store.update_status(session_id, "synthesis_running")
    state = session_store.load_session(session_id)

    story_section = forge_prompts.build_story_section(state.story)
    evidence_section = forge_prompts.build_evidence_section(state.evidence)
    full_history = forge_prompts.build_full_history(state)
    notes_text = "\n".join(f"- {n.text}" for n in state.user_notes) if state.user_notes else "None"

    system = forge_prompts.inject_instructions(forge_prompts.SYNTHESIS_SYSTEM, state.instructions)
    user = forge_prompts.SYNTHESIS_USER.format(
        story_section=story_section,
        evidence_section=evidence_section,
        full_history=full_history,
        user_notes=notes_text,
    )

    result = await llm_client.call_model("claude", system, user)

    # Save synthesis markdown
    session_store.save_markdown(session_id, "synthesis.md",
        f"# Forge — Final Synthesis\n\n"
        f"*{datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"
        f"**Story:** {state.story[:300]}{'...' if len(state.story) > 300 else ''}\n\n"
        f"**Evidence:** {state.evidence[:300]}{'...' if len(state.evidence) > 300 else ''}\n\n"
        f"---\n\n{result.text}\n"
    )

    # Record as response
    response = RoundResponse(
        position="synthesizer",
        model_name="claude",
        phase="synthesis",
        text=result.text,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        latency_ms=result.latency_ms,
        error=result.error,
    )
    async with lock:
        session_store.append_response(session_id, response)

    session_store.update_status(session_id, "complete")
