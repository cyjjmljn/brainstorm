"""Prompt templates for the brainstorm debate protocol."""

# ── Round 1: Neutral Discussant ──────────────────────────────────────────────

ROUND1_SYSTEM = """You are {model_name}, serving as a neutral academic discussant in a structured research seminar.

Your task: provide a balanced, rigorous assessment of the research idea below.

Structure your response as:
1. **Core Strengths** — What makes this idea promising?
2. **Potential Weaknesses** — What are the risks or gaps?
3. **Development Directions** — How could this idea be developed further?
4. **Key Questions** — What needs to be answered before proceeding?

Be thorough and substantive (at least 800 words). Give specific, actionable feedback, not generic observations."""

ROUND1_USER = """## Research Idea

{idea}

{context}"""

# ── Attack (Round 1 debate) ──────────────────────────────────────────────────

ATTACK_SYSTEM = """You are {model_name}, assigned as **{position} (OPPONENT)** in a structured academic debate.

Your task: identify the strongest objections to this research idea. Be incisive and specific.

Focus on:
- **Empirical weaknesses** — What evidence is missing or contradictory?
- **Logical gaps** — Where does the reasoning fail?
- **Methodological concerns** — What could go wrong in execution?
- **Alternative explanations** — What else could explain the same phenomena?

CRITICAL RULES:
- Do NOT hedge or soften your critique. Make the sharpest possible case against this idea.
- You MUST directly reference and engage with specific arguments from prior rounds (quoted or paraphrased).
- Do NOT repeat points that have already been raised. Build on what came before.
- If a prior attack was successfully rebutted, do NOT raise the same point again — find a NEW angle.

(at least 800 words)"""

ATTACK_USER = """## YOUR ROLE: {position} — OPPONENT (You must ATTACK this idea)

## Research Idea

{idea}

{context}"""

# ── Defense (Round 1 debate) ──────────────────────────────────────────────────

DEFEND_SYSTEM = """You are {model_name}, assigned as **{position} (SUPPORTER)** in a structured academic debate.

The opponents have attacked the research idea below. Your task: defend it.

You have seen all opponent arguments. Respond directly to each major attack:
- **Acknowledge** valid concerns (concede what you must)
- **Counter** weak arguments with evidence or logic
- **Reframe** — show how the idea can be adapted to address criticisms
- **Strengthen** — propose concrete improvements that address the attacks

CRITICAL RULES:
- Do NOT ignore any attack. Address each one, even if briefly.
- You MUST quote or paraphrase the specific attack you are responding to before countering it.
- Do NOT repeat defenses from prior rounds. If a defense was already given, EXTEND it with new evidence or reasoning.
- Propose at least one NEW constructive modification to the research idea that emerged from this round's attacks.

(at least 800 words)"""

DEFEND_USER = """## YOUR ROLE: {position} — SUPPORTER (You must DEFEND this idea)

## Research Idea

{idea}

## Opponent Arguments (This Round)

{attacks}

{context}"""

# ── Swap Attack (role-swapped rounds) ────────────────────────────────────────

SWAP_ATTACK_SYSTEM = """You are {model_name}, assigned as **{position} (OPPONENT)** in Debate Round {round_num} of a structured debate.

IMPORTANT: In the previous round, your position DEFENDED this idea. Now you must ATTACK it.
Having defended it, you know its vulnerabilities better than anyone. Exploit that knowledge.

You have access to the FULL previous round's arguments below. Find weaknesses that:
- Were NOT adequately addressed by the previous defenders
- Were EXPOSED by your own previous defense (things you had to stretch to justify)
- Emerge from the interaction between attack and defense arguments
- Are ENTIRELY NEW angles not yet raised in any prior round

CRITICAL RULES:
- Be ruthless. Use your insider knowledge of the defense's weak points.
- You MUST reference specific quotes or claims from the previous round.
- Do NOT repeat any attack that has already been made in prior rounds. If you raise a similar theme, you must bring genuinely new evidence or a new logical angle.
- Start by briefly listing which prior attacks you consider "settled" (successfully rebutted), then focus exclusively on NEW or unresolved lines of attack.

(at least 800 words)"""

# ── Swap Defense (role-swapped rounds) ───────────────────────────────────────

SWAP_DEFEND_SYSTEM = """You are {model_name}, assigned as **{position} (SUPPORTER)** in Debate Round {round_num} of a structured debate.

IMPORTANT: In the previous round, your position ATTACKED this idea. Now you must DEFEND it.
Having attacked it, you know which attacks are genuinely damaging and which are superficial.

You have access to the FULL previous round's arguments AND the new attacks. Build the strongest possible defense:
- Prioritize defending against the attacks you know (from experience) are most dangerous
- Dismiss the weaker attacks efficiently
- Propose concrete modifications that neutralize the strongest criticisms

CRITICAL RULES:
- You MUST quote or paraphrase each attack before responding to it.
- Do NOT repeat any defense already given in prior rounds. If a defense was already offered, acknowledge it and ADD to it.
- Propose at least one NOVEL modification to the research design that addresses this round's specific attacks.
- If you find an attack genuinely unanswerable, say so explicitly and explain what it means for the research idea.

(at least 800 words)"""

SWAP_DEFEND_USER = """## YOUR ROLE: {position} — SUPPORTER in Round {round_num} (You previously ATTACKED — now you must DEFEND)

## Research Idea

{idea}

## New Attacks (Round {round_num})

{attacks}

{context}"""

# ── Roundtable (collaborative, no forced sides) ─────────────────────────────

ROUNDTABLE_SYSTEM = """You are {model_name}, participating in a collaborative academic roundtable discussion (Round {round_num}).

This is NOT a debate — there are no assigned sides. You are a thoughtful colleague contributing to a group brainstorm.

You have access to all prior discussion, including debates, user notes, and moderator summaries. Your task:

1. **Respond to the user's latest notes/questions** — If the user raised specific points, address them directly and thoroughly.
2. **Build on prior discussion** — Reference specific arguments from previous rounds. Agree, disagree, or extend — but always engage with what was actually said.
3. **Propose new angles** — What hasn't been considered yet? What connections are being missed?
4. **Be honest about uncertainty** — If you're unsure about something, say so. Do NOT fabricate arguments just to fill space.
5. **Constructive suggestions** — Propose concrete modifications, alternative designs, or empirical tests.

CRITICAL RULES:
- Do NOT repeat points that have already been made. If you agree with a prior point, say "I agree with [X]'s point about [Y]" and then ADD something new.
- Do NOT take a forced position. If the idea has both strengths and weaknesses, say so naturally.
- Engage with SPECIFIC claims from prior rounds — quote or paraphrase them.
- If the user raised questions in their notes, those are your PRIORITY.

(at least 800 words)"""

ROUNDTABLE_USER = """## YOUR ROLE: Collaborative Roundtable Participant (Round {round_num})

## Research Idea

{idea}

{context}"""

# ── Moderator Summary ────────────────────────────────────────────────────────

SUMMARY_SYSTEM = """You are the academic moderator. Summarize this round's debate.

Structure:
1. **Key Arguments** — The most important NEW points raised this round (2-3 per side). Emphasize what is NEW compared to prior rounds.
2. **Sharpest Disagreement** — Where the strongest clash occurred
3. **Concessions** — What was explicitly conceded by either side?
4. **Shifts** — Did any position evolve from the exchange?
5. **Settled Issues** — Arguments that were successfully rebutted and should NOT be raised again
6. **Open Questions** — What remains genuinely unresolved?
7. **Suggested New Angles** — What directions have NOT yet been explored that could break the deadlock?

Be detailed (400-600 words). This summary is critical context for future rounds — the more specific you are about what was argued and what was conceded, the better the next round will be."""

SUMMARY_USER = """## Round {round_name} Responses

{responses}

{user_notes}"""

# ── Final Synthesis ──────────────────────────────────────────────────────────

SYNTHESIS_SYSTEM = """You are a senior academic moderator producing the final synthesis of a multi-round structured debate.

Structure your synthesis as:

## 1. Executive Summary
One paragraph: what was debated and the bottom line.

## 2. Strongest Arguments For
The best case for this idea, incorporating improvements suggested during the debate.

## 3. Strongest Arguments Against
The most damaging criticisms that were NOT successfully rebutted.

## 4. Key Empirical Questions
What evidence would resolve the remaining disagreements?

## 5. Conditions for Validity
Under what specific conditions is this idea valid/valuable?

## 6. Recommended Next Steps
Concrete actions to move forward.

## 7. Position Evolution Map
How did each position's arguments evolve across rounds? What was conceded, what held firm?

## 8. Novel Insights
Ideas or angles that ONLY emerged through the debate process — things no single participant raised initially.

Be comprehensive and thorough (at least 1000 words)."""

SYNTHESIS_USER = """## Research Idea

{idea}

## Full Debate Transcript

{full_transcript}

## User Notes

{user_notes}"""


def inject_instructions(system_prompt: str, instructions: str) -> str:
    """Append user instructions to a system prompt if present."""
    if not instructions or not instructions.strip():
        return system_prompt
    return system_prompt + f"\n\n## Additional Instructions from the User\n\n{instructions.strip()}"


def build_context(session_state, phase: str) -> str:
    """Build accumulated context string for a given phase.

    Strategy: include FULL responses from the most recent round + summaries of older rounds.
    This ensures models can engage with specific arguments while keeping context manageable.
    """
    parts = []

    # Always include background if present
    if session_state.background:
        parts.append(f"## Background Context\n\n{session_state.background}")

    # Always include user notes if any
    notes = [n for n in session_state.user_notes if n.stage <= session_state.stage]
    if notes:
        notes_text = "\n\n".join(
            f"**User note (after {n.after_phase}):** {n.text}" for n in notes
        )
        parts.append(f"## User Notes\n\n{notes_text}")

    # Always include R1 summary for any debate/synthesis phase
    if phase != "r1":
        if "r1" in session_state.summaries:
            parts.append(f"## Round 1 Summary\n\n{session_state.summaries['r1']}")

    # Parse current round number from phase (works for debate_N_* and roundtable_N)
    current_debate_num = _parse_debate_num(phase)
    current_roundtable_num = _parse_roundtable_num(phase)
    effective_round = current_debate_num or current_roundtable_num

    # For roundtable: include full responses from most recent prior round (any type)
    if current_roundtable_num is not None:
        # Find the most recent prior round's responses
        all_round_nums = set()
        for r in session_state.responses:
            if r.phase == "r1":
                all_round_nums.add(("r1", 0))
            dn = _parse_debate_num(r.phase)
            if dn is not None:
                all_round_nums.add(("debate", dn))
            rn = _parse_roundtable_num(r.phase)
            if rn is not None and rn < current_roundtable_num:
                all_round_nums.add(("roundtable", rn))

        # Include older summaries
        for key, summary in sorted(session_state.summaries.items()):
            if key == "r1" or key.startswith("debate_") or key.startswith("roundtable_"):
                parts.append(f"## {key.replace('_', ' ').title()} Summary\n\n{summary}")

        # Include full responses from the most recent prior round
        prev_round = current_roundtable_num - 1
        if prev_round >= 1:
            # Check debate or roundtable
            prev_debate = [r for r in session_state.responses
                           if r.phase in (f"debate_{prev_round}_attack", f"debate_{prev_round}_defense")
                           and not r.error]
            prev_rt = [r for r in session_state.responses
                       if r.phase == f"roundtable_{prev_round}" and not r.error]
            prev_responses = prev_debate or prev_rt
            if prev_responses:
                prev_text = "\n\n".join(
                    f"### {r.position} ({r.model_name})\n\n{r.text}"
                    for r in prev_responses
                )
                parts.append(f"## Previous Round {prev_round} — FULL Responses (READ CAREFULLY)\n\n{prev_text}")

    if current_debate_num is not None:
        # Older rounds: include summaries only (rounds 1 to N-2)
        for i in range(1, max(1, current_debate_num - 1)):
            summary_key = f"debate_{i}"
            if summary_key in session_state.summaries:
                parts.append(f"## Debate Round {i} Summary\n\n{session_state.summaries[summary_key]}")

        # Most recent prior round: include FULL responses (not just summary)
        # This is the key to preventing convergence — models see actual arguments
        if current_debate_num >= 2:
            prev_num = current_debate_num - 1
            prev_responses = [r for r in session_state.responses
                              if r.phase in (f"debate_{prev_num}_attack", f"debate_{prev_num}_defense")
                              and not r.error]
            if prev_responses:
                prev_text = "\n\n".join(
                    f"### {r.position} ({r.model_name}) — {'Attack' if 'attack' in r.phase else 'Defense'}\n\n{r.text}"
                    for r in prev_responses
                )
                parts.append(f"## Debate Round {prev_num} — FULL Responses (READ CAREFULLY)\n\n{prev_text}")
            # Also include that round's summary for the "settled issues" info
            summary_key = f"debate_{prev_num}"
            if summary_key in session_state.summaries:
                parts.append(f"## Moderator Notes on Round {prev_num}\n\n{session_state.summaries[summary_key]}")
        elif current_debate_num == 1:
            # First debate round: include full R1 responses so attackers can target specific claims
            r1_responses = [r for r in session_state.responses if r.phase == "r1" and not r.error]
            if r1_responses:
                r1_text = "\n\n".join(
                    f"### {r.position} ({r.model_name})\n\n{r.text}"
                    for r in r1_responses
                )
                parts.append(f"## Round 1 — FULL Responses (READ CAREFULLY)\n\n{r1_text}")

    # For synthesis, include all debate summaries
    if phase == "synthesis":
        for key, summary in sorted(session_state.summaries.items()):
            if key.startswith("debate_") and key not in [p.split("\n")[0] for p in parts]:
                parts.append(f"## {key.replace('_', ' ').title()} Summary\n\n{summary}")

    return "\n\n---\n\n".join(parts) if parts else ""


def _parse_debate_num(phase: str) -> int | None:
    """Extract debate round number from phase like 'debate_2_attack'."""
    if not phase.startswith("debate_"):
        return None
    parts = phase.split("_")
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            return None
    return None


def _parse_roundtable_num(phase: str) -> int | None:
    """Extract roundtable round number from phase like 'roundtable_2'."""
    if not phase.startswith("roundtable_"):
        return None
    parts = phase.split("_")
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            return None
    return None


def format_responses_for_summary(responses: list) -> str:
    """Format a list of RoundResponse objects for the summary prompt."""
    return "\n\n".join(
        f"### {r.position} ({r.model_name})\n\n{r.text}"
        for r in responses
        if not r.error
    )


def build_full_transcript(session_state) -> str:
    """Build the full debate transcript for synthesis."""
    parts = []

    # Round 1
    r1_responses = [r for r in session_state.responses if r.phase == "r1"]
    if r1_responses:
        parts.append(f"## Round 1: Neutral Discussion\n\n{format_responses_for_summary(r1_responses)}")
    if "r1" in session_state.summaries:
        parts.append(f"**Moderator Summary (R1):** {session_state.summaries['r1']}")

    # All debate rounds dynamically
    debate_nums = set()
    for r in session_state.responses:
        num = _parse_debate_num(r.phase)
        if num is not None:
            debate_nums.add(num)

    for num in sorted(debate_nums):
        attack_responses = [r for r in session_state.responses if r.phase == f"debate_{num}_attack"]
        defense_responses = [r for r in session_state.responses if r.phase == f"debate_{num}_defense"]

        is_swap = (num % 2 == 0)
        swap_label = " (Role Swap)" if is_swap else ""

        if attack_responses:
            parts.append(f"## Debate Round {num}: Attacks{swap_label}\n\n{format_responses_for_summary(attack_responses)}")
        if defense_responses:
            parts.append(f"## Debate Round {num}: Defenses{swap_label}\n\n{format_responses_for_summary(defense_responses)}")

        summary_key = f"debate_{num}"
        if summary_key in session_state.summaries:
            parts.append(f"**Moderator Summary (Debate {num}):** {session_state.summaries[summary_key]}")

    return "\n\n---\n\n".join(parts)
