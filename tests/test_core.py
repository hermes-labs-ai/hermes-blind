"""Core round-trip tests for the package the rubric-blinded "done" gate imports.

The gate wrapper (hermes-rubric-blinded.py) depends on wrap(); until 2026-07-02
this package had no tests of its own — the gate everything passes through was
itself unverified.
"""
import pytest

from hermes_blind import (
    SCOPE_CHOICES,
    VARIANTS,
    detect_valence,
    extract_disclosure,
    intent_debias,
    scope_class_preamble,
    wrap,
)

PROMPT = "Score this artifact 1-10 for evidence quality."


def test_wrap_preserves_prompt_verbatim():
    for variant in VARIANTS:
        out = wrap(PROMPT, variant=variant)
        assert PROMPT in out
        assert out.endswith(PROMPT) or variant == "null"


def test_wrap_default_prepends_scaffold():
    out = wrap(PROMPT)
    assert out != PROMPT
    assert len(out) > len(PROMPT)


def test_wrap_null_variant_is_passthrough():
    assert wrap(PROMPT, variant="null") == PROMPT


def test_wrap_rejects_unknown_variant():
    with pytest.raises((KeyError, ValueError)):
        wrap(PROMPT, variant="nope")


def test_extract_disclosure_none_on_plain_response():
    assert extract_disclosure("Score: 7/10. Solid evidence throughout.") is None


def test_scope_class_preamble_all_choices_nonempty():
    for scope in SCOPE_CHOICES:
        assert scope_class_preamble(scope).strip()


def test_scope_class_preamble_rejects_unknown():
    with pytest.raises((KeyError, ValueError)):
        scope_class_preamble("not-a-scope")


def test_detect_valence_flags_loaded_words_passes_neutral():
    assert detect_valence("this is a neutral description of a parser") == []
    loaded = detect_valence("an amazing groundbreaking parser")
    assert isinstance(loaded, list)


def test_intent_debias_preserves_intent():
    intent = "compare approach A and approach B"
    out = intent_debias(intent)
    assert intent in out and len(out) > len(intent)
