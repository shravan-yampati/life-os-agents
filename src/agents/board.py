"""Board of Directors — a multi-agent debate for major life decisions.

The centerpiece of the Life OS. A decision is fanned out to four persona advisor
agents, each arguing from a distinct lens. A fifth Synthesizer agent then weighs
the debate against the user's life-os-foundation (their real values and
NON-NEGOTIABLE constraints) and issues a final ruling.

The foundation's hard constraints are sacred: the Synthesizer must refuse any
option that violates them, no matter how persuasive the debate. This is the
"values-grounded" twist on a standard multi-agent debate — the agents don't just
argue, they argue against *this specific person's* documented goals.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from src.providers.factory import ProviderFactory

# brainstorms/ lives at the repo root, two levels up from src/agents/.
_FOUNDATION_PATH = (
    Path(__file__).resolve().parents[2] / "brainstorms" / "life-os-foundation.md"
)

# Each advisor argues from one lens. Kept short and sharp on purpose.
PERSONAS: Dict[str, str] = {
    "Financial CFO": (
        "You are the user's hard-nosed CFO. You care about cash flow, savings rate, "
        "runway, debt, and whether the numbers actually work. You quote figures and "
        "trade-offs and you are unsentimental about money."
    ),
    "Visionary CEO": (
        "You are the user's Visionary CEO. You care about long-term upside, leverage, "
        "compounding skills, and asymmetric bets. You push for ambition and growth — "
        "but you respect the user's stated values, not reckless hype."
    ),
    "Health Coach": (
        "You are the user's Health & Wellbeing Coach. You weigh stress, burnout, sleep, "
        "relationships, and sustainability. A 'win' that wrecks the user's health or "
        "marriage is a loss. You speak for the human behind the spreadsheet."
    ),
    "Devil's Advocate": (
        "You are the Devil's Advocate. Attack the decision: surface the biggest risks, "
        "the ways it fails, the hidden costs, and any violation of the user's "
        "non-negotiable constraints. Be specific, never vague."
    ),
}

SYNTHESIZER = (
    "You are the Synthesizer, chair of the user's personal Board of Directors. "
    "You have read the four advisors' opinions and the user's FOUNDATION (their real "
    "values, goals, risk posture, and NON-NEGOTIABLE constraints). Issue a final "
    "ruling in this exact structure:\n"
    "1. VERDICT: a clear call — Yes / No / Yes-but / Wait.\n"
    "2. WHY: 2-4 sentences grounded in the user's actual goals and the debate.\n"
    "3. CONSTRAINT CHECK: explicitly confirm no NON-NEGOTIABLE is violated (name any "
    "that are relevant).\n"
    "4. CONDITIONS: concrete guardrails or next steps.\n"
    "Never recommend anything that breaks a non-negotiable, however persuasive the "
    "argument. Match the user's preferred tone: direct, specific numbers, tough-love."
)


@dataclass
class Opinion:
    persona: str
    text: str


@dataclass
class Ruling:
    decision: str
    opinions: List[Opinion] = field(default_factory=list)
    verdict: str = ""


def load_foundation(path: Path = _FOUNDATION_PATH) -> str:
    """Loads the user's core-values foundation, or a safe placeholder."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "(No foundation document found — advise conservatively and flag the gap.)"


def _advisor_prompt(persona_brief: str, decision: str, foundation: str) -> str:
    return (
        f"{persona_brief}\n\n"
        f"--- USER FOUNDATION (their values & non-negotiables) ---\n{foundation}\n\n"
        f"--- DECISION TO WEIGH IN ON ---\n{decision}\n\n"
        "Give your opinion in 3-5 sentences, strictly from your lens. Reference the "
        "user's actual goals/constraints where relevant."
    )


def convene_board(decision: str, foundation_path: Path = _FOUNDATION_PATH) -> Ruling:
    """Runs the full debate: 4 advisors fan out, then the Synthesizer rules."""
    llm = ProviderFactory.get_llm()
    foundation = load_foundation(foundation_path)

    opinions: List[Opinion] = []
    for persona, brief in PERSONAS.items():
        text = llm.generate(
            _advisor_prompt(brief, decision, foundation),
            temperature=0.6,
            max_tokens=3072,  # headroom: gemini-2.5-flash thinking shares this budget
        )
        opinions.append(Opinion(persona=persona, text=text.strip()))

    debate = "\n\n".join(f"### {o.persona}\n{o.text}" for o in opinions)
    synth_prompt = (
        f"{SYNTHESIZER}\n\n"
        f"--- USER FOUNDATION ---\n{foundation}\n\n"
        f"--- THE DECISION ---\n{decision}\n\n"
        f"--- THE DEBATE ---\n{debate}\n\n"
        "Now issue the Board's ruling."
    )
    verdict = llm.generate(synth_prompt, temperature=0.3, max_tokens=3072).strip()
    return Ruling(decision=decision, opinions=opinions, verdict=verdict)


def _print_ruling(ruling: Ruling) -> None:
    print("\n" + "=" * 64)
    print("  BOARD OF DIRECTORS")
    print("=" * 64)
    print(f"  DECISION: {ruling.decision}\n")
    for o in ruling.opinions:
        print(f"-- {o.persona} --")
        print(o.text + "\n")
    print("=" * 64)
    print("  SYNTHESIZER'S RULING")
    print("=" * 64)
    print(ruling.verdict)
    print("=" * 64 + "\n")


def main() -> None:
    # Windows consoles default to cp1252 and choke on the LLM's Unicode (arrows,
    # em-dashes). Force UTF-8 output so the ruling always prints.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(
        description="Convene the Life OS Board of Directors on a major decision."
    )
    parser.add_argument("decision", help="The major life decision to debate")
    args = parser.parse_args()
    _print_ruling(convene_board(args.decision))


if __name__ == "__main__":
    main()
