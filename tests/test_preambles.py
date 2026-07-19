"""Tests for the rubric-synthesis preambles moved from hermes-rubric in v0.1.1."""

from __future__ import annotations

import io

import pytest

from hermes_blind import (
    INTENT_DEBIAS_PREAMBLE,
    SCOPE_CHOICES,
    SCOPE_PREAMBLES,
    compose_intent,
    detect_valence,
    intent_debias,
    scope_class_preamble,
    wrap_intent_for_rubric,
)

# ---- intent_debias ----

def test_intent_debias_prefixes_preamble():
    out = intent_debias("evaluate whether X is sound")
    assert out.startswith(INTENT_DEBIAS_PREAMBLE)
    assert "INTENT (from framer): evaluate whether X is sound" in out


# ---- scope_class_preamble ----

@pytest.mark.parametrize("scope", ["gate-plan", "sweep-plan", "results-bundle"])
def test_scope_class_preamble_returns_correct_string(scope):
    assert scope_class_preamble(scope) == SCOPE_PREAMBLES[scope]


def test_scope_class_preamble_unknown_raises():
    with pytest.raises(ValueError, match="Unknown scope"):
        scope_class_preamble("not-a-scope")


def test_scope_choices_matches_keys():
    assert set(SCOPE_CHOICES) == set(SCOPE_PREAMBLES.keys())


# ---- wrap_intent_for_rubric ----

def test_wrap_no_flags_returns_unchanged():
    intent = "score against listed criteria"
    assert wrap_intent_for_rubric(intent) == intent


def test_wrap_with_debias_only():
    out = wrap_intent_for_rubric("rate", debias=True)
    assert INTENT_DEBIAS_PREAMBLE in out
    assert "INTENT (from framer): rate" in out


def test_wrap_with_scope_only():
    out = wrap_intent_for_rubric("rate", scope_class="gate-plan")
    assert SCOPE_PREAMBLES["gate-plan"] in out
    assert "INTENT (from framer): rate" in out


def test_wrap_with_both_orders_debias_first():
    out = wrap_intent_for_rubric("rate", scope_class="gate-plan", debias=True)
    i_debias = out.index(INTENT_DEBIAS_PREAMBLE)
    i_scope = out.index(SCOPE_PREAMBLES["gate-plan"])
    i_intent = out.index("INTENT (from framer):")
    assert i_debias < i_scope < i_intent


def test_wrap_silences_valence_warning():
    """wrap_intent_for_rubric() should not write to stderr (warn_stream=None)."""
    # If it tried to write to stderr, this would not raise — but we explicitly
    # confirm the convenience wrapper passes warn_stream=None by checking that
    # compose_intent with warn_stream=None produces the same output.
    out = wrap_intent_for_rubric(
        "evaluate whether sound and ready", debias=True
    )
    expected = compose_intent(
        "evaluate whether sound and ready",
        intent_debias=True,
        warn_stream=None,
    )
    assert out == expected


# ---- detect_valence ----

def test_detect_valence_loaded_words():
    assert "sound" in detect_valence("evaluate whether the plan is sound")
    assert "ready" in detect_valence("is this ready to ship")
    assert "sound" in detect_valence("evaluate whether the plan is sound.")
    assert "ready" in detect_valence("is this ready?")
    assert "well-designed" in detect_valence("a well-designed plan")


def test_detect_valence_neutral():
    assert detect_valence("score against the listed criteria") == []


# ---- byte-identity with the strings hermes-rubric used to ship ----

def test_intent_debias_preamble_byte_identical():
    """Frozen string — must match what hermes-rubric v0.1.2 shipped."""
    expected = (
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
    assert INTENT_DEBIAS_PREAMBLE == expected


# ---- compose_intent retains stderr-warning behavior ----

def test_compose_intent_warns_on_valence():
    buf = io.StringIO()
    compose_intent(
        "evaluate whether sound and ready",
        intent_debias=True,
        warn_stream=buf,
    )
    err = buf.getvalue()
    assert "valence words" in err
    assert "sound" in err
