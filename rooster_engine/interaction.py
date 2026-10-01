from __future__ import annotations

from .guard import Action, Risk


def parse_chat_action(message: str) -> Action | None:
    """Map only explicitly supported chat intents to exact guarded actions."""
    normalized = " ".join(message.strip().lower().split())
    if not normalized:
        return None

    run_test_phrases = (
        "run the test suite",
        "run test suite",
        "run the tests",
        "run tests",
        "execute the test suite",
        "execute test suite",
    )
    if any(phrase in normalized for phrase in run_test_phrases):
        return Action(
            tool="run_tests",
            reason="User explicitly requested the repository test suite from the interactive chat.",
            action="Run the fixed repository unittest discovery suite",
            evidence="Repository test-suite output and exit status",
            risk=Risk.MEDIUM,
            target="tests",
        )

    return None
