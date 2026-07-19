"""Intent-debias and scope-class preambles for rubric synthesis.

These are prepended to a framer's intent before rubric synthesis so the
synthesizer generates dimensions appropriate to (a) the target's *kind*
(scope-class) and (b) the framer's possible bias (intent-debias).

This module was originally inside hermes-rubric (G7 flags). It now lives in
hermes-blind because it is bias-compensation scaffolding — the same domain as
the [HERMES-BLIND] wrapper. hermes-rubric depends on hermes-blind for these
strings; the two repos remain independently publishable OSS.

Public API:
    INTENT_DEBIAS_PREAMBLE
    SCOPE_PREAMBLES
    SCOPE_CHOICES
    VALENCE_WORDS
    detect_valence(intent) -> list[str]
    intent_debias(intent) -> str
    scope_class_preamble(scope) -> str
    wrap_intent_for_rubric(intent, scope_class=None, debias=False) -> str
    compose_intent(intent, *, scope_class=None, intent_debias=False, warn_stream=sys.stderr) -> str
"""
from __future__ import annotations

import re
import sys

INTENT_DEBIAS_PREAMBLE = (
    "INTENT-DEBIAS NOTICE: The supplied intent below was written by the "
    "person whose work is being evaluated, and may presuppose a preferred "
    "outcome (e.g., 'evaluate whether X is sound' is loaded toward "
    "soundness). Before generating dimensions:\n"
    "  1. State in one sentence whether the intent presupposes a preferred "
    "outcome, and if so, which one.\n"
    "  2. Generate dimensions that would discriminate even if the OPPOSITE "
    "outcome were true.\n"
    "  3. Treat valence-loaded adjectives in the intent ('sound', 'ready', "
    "'rigorous', 'broken', 'flawed') as REQUESTED FOCUS AREAS, not as "
    "verdicts to confirm. The dimension should measure the property, not "
    "presume its level.\n"
    "If the intent is purely evaluative (e.g., 'evaluate against criteria X' "
    "with no adjective load), state 'no preferred outcome detected' and "
    "proceed normally."
)

SCOPE_PREAMBLES: dict[str, str] = {
    "gate-plan": (
        "SCOPE-CLASS NOTICE: The target is a GATE PLAN — a deliberately narrow "
        "subset of a larger pre-registered sweep, designed to make a cheap "
        "go/no-go decision before committing to the full sweep. Judge it on:\n"
        "  - DECISION RELEVANCE: are the gate's pass/fail outcomes mapped to "
        "concrete downstream actions (proceed / publish null / rerun / ship)?\n"
        "  - SIGNAL ADEQUACY: is the run budget sized to detect the effect IF "
        "it exists, not to validate it for publication?\n"
        "  - SCOPE-BOUNDARY CLARITY: does the plan name what it does NOT test "
        "and defer those cleanly to the full sweep?\n"
        "  - SUBSET FIDELITY: do variant strings, seeds, model pins, null-result "
        "commitments carry over from the parent sweep without drift?\n"
        "DO NOT penalize a gate plan for not testing every dimension of the full "
        "sweep — that is its purpose. DO penalize unscoped narrowness, "
        "unexplained deferrals, or claims that exceed gate-adequate evidence."
    ),
    "sweep-plan": (
        "SCOPE-CLASS NOTICE: The target is a FULL SWEEP PLAN — a pre-registered "
        "experimental design intended to validate or falsify a hypothesis. Judge "
        "it on coverage, statistical power, mechanism isolation, cross-condition "
        "generalization, ground-truth construction, and confound control."
    ),
    "results-bundle": (
        "SCOPE-CLASS NOTICE: The target is a RESULTS BUNDLE — post-execution "
        "artifacts (jsonl logs, analysis, sealed manifest). Judge it on "
        "tamper-evidence, completeness of pre-registered endpoint evaluation, "
        "honest null-result reporting, and reproducibility of the analysis."
    ),
}

SCOPE_CHOICES = tuple(SCOPE_PREAMBLES.keys())

VALENCE_WORDS: tuple[str, ...] = (
    "sound", "soundness", "ready", "rigorous", "robust", "valid", "good",
    "broken", "flawed", "weak", "strong", "well-designed", "elegant",
)


def detect_valence(intent: str) -> list[str]:
    """Return list of valence-loaded words present in the intent (advisory)."""
    return [
        word
        for word in VALENCE_WORDS
        if re.search(
            rf"(?<!\w){re.escape(word)}(?!\w)",
            intent,
            flags=re.IGNORECASE,
        )
    ]


def intent_debias(intent: str) -> str:
    """Return the intent prefixed with the intent-debias preamble.

    Convenience wrapper for callers that don't need the full
    ``compose_intent`` ordering machinery.
    """
    return INTENT_DEBIAS_PREAMBLE + "\n\nINTENT (from framer): " + intent


def scope_class_preamble(scope: str) -> str:
    """Return the preamble string for a given scope class.

    Parameters
    ----------
    scope : str
        One of ``SCOPE_CHOICES`` (gate-plan / sweep-plan / results-bundle).

    Raises
    ------
    ValueError
        If ``scope`` is not a known scope class.
    """
    if scope not in SCOPE_PREAMBLES:
        raise ValueError(
            f"Unknown scope {scope!r}; expected one of {SCOPE_CHOICES}"
        )
    return SCOPE_PREAMBLES[scope]


def wrap_intent_for_rubric(
    intent: str,
    scope_class: str | None = None,
    debias: bool = False,
) -> str:
    """Wrap a framer's intent with optional debias + scope-class preambles.

    Convenience wrapper around ``compose_intent`` with a non-keyword
    boolean parameter. Suppresses the stderr valence warning (use
    ``compose_intent`` directly if you want it).

    If neither ``scope_class`` nor ``debias`` is set, returns ``intent``
    unchanged.
    """
    return compose_intent(
        intent,
        scope_class=scope_class,
        intent_debias=debias,
        warn_stream=None,
    )


def compose_intent(
    intent: str,
    *,
    scope_class: str | None = None,
    intent_debias: bool = False,
    warn_stream=sys.stderr,
) -> str:
    """Compose an intent string with optional debias + scope-class preambles.

    Order: intent-debias first (most external anchor), scope-class second
    (target-type-specific guidance), original intent last (the framer's
    request, now contextualized by the two preambles).

    If neither flag is set, returns ``intent`` unchanged so callers see
    identical behavior to pre-G7.
    """
    if not intent_debias and not scope_class:
        return intent

    parts: list[str] = []
    if intent_debias:
        valence = detect_valence(intent)
        if valence and warn_stream is not None:
            warn_stream.write(
                f"[hermes-rubric] valence words in intent: {valence} — "
                "intent-debias preamble will neutralize\n"
            )
        parts.append(INTENT_DEBIAS_PREAMBLE)
    if scope_class:
        if scope_class not in SCOPE_PREAMBLES:
            raise ValueError(
                f"Unknown scope_class {scope_class!r}; expected one of {SCOPE_CHOICES}"
            )
        parts.append(SCOPE_PREAMBLES[scope_class])
    parts.append("INTENT (from framer): " + intent)
    return "\n\n".join(parts)
