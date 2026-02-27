"""Debate orchestration engine — controls round flow and model calls."""

import asyncio
from datetime import datetime

from . import llm_client, prompts, session_store
from .models import RoundResponse


def _get_model_for_position(session_state, position: str) -> str:
    """Get the model name assigned to a position."""
    for pa in session_state.positions:
        if pa.position == position:
            return pa.model_name
    raise ValueError(f"No model assigned to position {position}")


def _session_header(state) -> str:
    """Build a markdown header with session metadata (idea, background, instructions)."""
    parts = [f"**Title:** {state.title}\n"]
    parts.append(f"**Research Idea:**\n\n{state.idea}\n")
    if state.instructions:
        parts.append(f"**Instructions:** {state.instructions}\n")
    if state.background:
        bg = state.background
        if len(bg) > 2000:
            bg = bg[:2000] + "\n\n*(background truncated in export — full text in session.json)*"
        parts.append(f"**Background Context:**\n\n{bg}\n")
    return "\n".join(parts)


def _notes_section(state, up_to_phase: str = "") -> str:
    """Build a markdown section for user notes added so far."""
    notes = state.user_notes
    if not notes:
        return ""
    parts = ["\n**User Notes:**\n"]
    for n in notes:
        parts.append(f"- _{n.after_phase}_ — {n.text}")
    return "\n".join(parts) + "\n"


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


async def _generate_summary(session_id: str, round_key: str, round_name: str, lock: asyncio.Lock):
    """Generate a moderator summary for a round using Claude. Non-blocking on failure."""
    try:
        return await asyncio.wait_for(
            _generate_summary_impl(session_id, round_key, round_name, lock),
            timeout=180.0,
        )
    except (asyncio.TimeoutError, Exception) as e:
        # Don't block the round if summary fails
        fallback = f"(Summary generation failed: {e})"
        async with lock:
            session_store.update_summary(session_id, round_key, fallback)
        return fallback


async def _generate_summary_impl(session_id: str, round_key: str, round_name: str, lock: asyncio.Lock):
    """Internal summary generation."""
    state = session_store.load_session(session_id)

    # Collect responses for this round
    if round_key == "r1":
        phases = ["r1"]
    elif round_key.startswith("debate_"):
        num = round_key.split("_")[1]
        phases = [f"debate_{num}_attack", f"debate_{num}_defense"]
    else:
        phases = [round_key]

    responses = [r for r in state.responses if r.phase in phases]

    responses_text = prompts.format_responses_for_summary(responses)
    notes_text = "\n".join(f"- {n.text}" for n in state.user_notes) if state.user_notes else "None"

    system = prompts.inject_instructions(prompts.SUMMARY_SYSTEM, state.instructions)
    user = prompts.SUMMARY_USER.format(
        round_name=round_name,
        responses=responses_text,
        user_notes=notes_text,
    )

    result = await llm_client.call_model("claude", system, user)

    async with lock:
        session_store.update_summary(session_id, round_key, result.text)

    return result.text


async def run_round1(session_id: str, lock: asyncio.Lock):
    """Round 1: All 4 models as neutral discussants (parallel)."""
    session_store.update_status(session_id, "r1_running")
    state = session_store.load_session(session_id)

    # Build context with background
    context = ""
    if state.background:
        context = f"## Background Context\n\n{state.background}"

    tasks = []
    for pos in ["S1", "S2", "O1", "O2"]:
        model_name = _get_model_for_position(state, pos)
        system = prompts.inject_instructions(
            prompts.ROUND1_SYSTEM.format(model_name=model_name), state.instructions)
        user = prompts.ROUND1_USER.format(idea=state.idea, context=context)
        tasks.append(_call_and_record(session_id, pos, model_name, "r1", system, user, lock))

    results = await asyncio.gather(*tasks)

    # Save markdown
    md_parts = [f"# Round 1: Neutral Discussion\n\nStage {state.stage} | {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                + _session_header(state)]
    for r in results:
        status = f"**ERROR: {r.error}**" if r.error else r.text
        md_parts.append(f"## {r.position} — {r.model_name}\n\n{status}\n")
    session_store.save_markdown(session_id, "round1.md", "\n---\n\n".join(md_parts))

    # Generate summary
    await _generate_summary(session_id, "r1", "Round 1 (Neutral Discussion)", lock)

    session_store.update_status(session_id, "r1_pause")


async def run_debate_round(session_id: str, lock: asyncio.Lock):
    """Run one debate round (attack then defense). Supports infinite rounds with role swapping.

    Odd rounds (1, 3, 5...): O1+O2 attack, S1+S2 defend
    Even rounds (2, 4, 6...): S1+S2 attack (swap), O1+O2 defend (swap)
    """
    state = session_store.load_session(session_id)
    round_num = state.current_round + 1
    is_swap = (round_num % 2 == 0)

    attack_phase = f"debate_{round_num}_attack"
    defense_phase = f"debate_{round_num}_defense"

    if is_swap:
        attackers = ["S1", "S2"]
        defenders = ["O1", "O2"]
    else:
        attackers = ["O1", "O2"]
        defenders = ["S1", "S2"]

    # Phase 1: Attacks
    session_store.update_status(session_id, f"debate_{round_num}_attacks_running")
    context = prompts.build_context(state, attack_phase)

    attack_tasks = []
    for pos in attackers:
        model_name = _get_model_for_position(state, pos)
        if is_swap:
            system = prompts.SWAP_ATTACK_SYSTEM.format(
                model_name=model_name, position=pos, round_num=round_num)
        else:
            system = prompts.ATTACK_SYSTEM.format(model_name=model_name, position=pos)
        system = prompts.inject_instructions(system, state.instructions)
        user = prompts.ATTACK_USER.format(idea=state.idea, context=context, position=pos)
        attack_tasks.append(_call_and_record(
            session_id, pos, model_name, attack_phase, system, user, lock))

    attack_results = await asyncio.gather(*attack_tasks)

    # Save attack markdown
    swap_label = " (Role Swap)" if is_swap else ""
    state = session_store.load_session(session_id)  # reload to get latest notes
    md_parts = [f"# Debate Round {round_num}: Attacks{swap_label}\n\n"
                f"Stage {state.stage} | {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                + _notes_section(state)]
    for r in attack_results:
        status = f"**ERROR: {r.error}**" if r.error else r.text
        role_label = "NOW OPPONENT" if is_swap else "OPPONENT"
        md_parts.append(f"## {r.position} ({r.model_name}) — {role_label}\n\n{status}\n")
    session_store.save_markdown(session_id, f"debate_{round_num}_attacks.md", "\n---\n\n".join(md_parts))

    # Phase 2: Defenses (seeing attacks)
    session_store.update_status(session_id, f"debate_{round_num}_defenses_running")
    state = session_store.load_session(session_id)  # reload to get attacks
    context = prompts.build_context(state, defense_phase)
    attacks_text = "\n\n".join(
        f"### {r.position} ({r.model_name})\n\n{r.text}" for r in attack_results if not r.error
    )

    defense_tasks = []
    for pos in defenders:
        model_name = _get_model_for_position(state, pos)
        if is_swap:
            system = prompts.SWAP_DEFEND_SYSTEM.format(
                model_name=model_name, position=pos, round_num=round_num)
            user = prompts.SWAP_DEFEND_USER.format(
                idea=state.idea, attacks=attacks_text, context=context, round_num=round_num, position=pos)
        else:
            system = prompts.DEFEND_SYSTEM.format(model_name=model_name, position=pos)
            user = prompts.DEFEND_USER.format(idea=state.idea, attacks=attacks_text, context=context, position=pos)
        system = prompts.inject_instructions(system, state.instructions)
        defense_tasks.append(_call_and_record(
            session_id, pos, model_name, defense_phase, system, user, lock))

    defense_results = await asyncio.gather(*defense_tasks)

    # Save defense markdown
    md_parts = [f"# Debate Round {round_num}: Defenses{swap_label}\n\n"
                f"Stage {state.stage} | {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    for r in defense_results:
        status = f"**ERROR: {r.error}**" if r.error else r.text
        role_label = "NOW SUPPORTER" if is_swap else "SUPPORTER"
        md_parts.append(f"## {r.position} ({r.model_name}) — {role_label}\n\n{status}\n")
    session_store.save_markdown(session_id, f"debate_{round_num}_defenses.md", "\n---\n\n".join(md_parts))

    # Update round counter
    state = session_store.load_session(session_id)
    state.current_round = round_num
    session_store.save_session(state)

    # Generate summary
    await _generate_summary(session_id, f"debate_{round_num}",
                            f"Debate Round {round_num}{swap_label}", lock)

    session_store.update_status(session_id, f"debate_{round_num}_pause")


async def run_roundtable(session_id: str, lock: asyncio.Lock):
    """Roundtable: All 4 models as collaborative discussants (no forced sides)."""
    state = session_store.load_session(session_id)
    round_num = state.current_round + 1
    phase = f"roundtable_{round_num}"

    session_store.update_status(session_id, f"roundtable_{round_num}_running")
    context = prompts.build_context(state, phase)

    tasks = []
    for pos in ["S1", "S2", "O1", "O2"]:
        model_name = _get_model_for_position(state, pos)
        system = prompts.inject_instructions(
            prompts.ROUNDTABLE_SYSTEM.format(model_name=model_name, round_num=round_num),
            state.instructions)
        user = prompts.ROUNDTABLE_USER.format(idea=state.idea, context=context, round_num=round_num)
        tasks.append(_call_and_record(session_id, pos, model_name, phase, system, user, lock))

    results = await asyncio.gather(*tasks)

    # Save markdown
    state = session_store.load_session(session_id)  # reload to get latest notes
    md_parts = [f"# Roundtable Round {round_num}\n\n"
                f"Stage {state.stage} | {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                + _notes_section(state)]
    for r in results:
        status = f"**ERROR: {r.error}**" if r.error else r.text
        md_parts.append(f"## {r.position} — {r.model_name}\n\n{status}\n")
    session_store.save_markdown(session_id, f"roundtable_{round_num}.md", "\n---\n\n".join(md_parts))

    # Update round counter
    state = session_store.load_session(session_id)
    state.current_round = round_num
    session_store.save_session(state)

    # Generate summary
    await _generate_summary(session_id, f"roundtable_{round_num}",
                            f"Roundtable Round {round_num}", lock)

    session_store.update_status(session_id, f"roundtable_{round_num}_pause")


async def run_synthesis(session_id: str, lock: asyncio.Lock):
    """Final synthesis by Claude moderator."""
    session_store.update_status(session_id, "synthesis_running")
    state = session_store.load_session(session_id)

    full_transcript = prompts.build_full_transcript(state)
    notes_text = "\n".join(f"- {n.text}" for n in state.user_notes) if state.user_notes else "None"

    system = prompts.inject_instructions(prompts.SYNTHESIS_SYSTEM, state.instructions)
    user = prompts.SYNTHESIS_USER.format(
        idea=state.idea,
        full_transcript=full_transcript,
        user_notes=notes_text,
    )

    result = await llm_client.call_model("claude", system, user)

    # Save synthesis
    session_store.save_markdown(session_id, "synthesis.md",
        f"# Synthesis — Stage {state.stage}\n\n"
        f"*{datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"
        + _session_header(state) + "\n---\n\n"
        + _notes_section(state)
        + f"{result.text}\n"
    )

    # Record as response
    response = RoundResponse(
        position="moderator",
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
