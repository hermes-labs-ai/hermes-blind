"""Unit tests for hermes_blind.scaffold — structure only, no LLM calls."""

from __future__ import annotations

import pytest

from hermes_blind import DEFAULT_VARIANT, VARIANTS, extract_disclosure, wrap
from hermes_blind.scaffold import token_estimate


class TestWrap:
    def test_null_variant_passthrough(self):
        """The null variant is a no-op — used by the ablation harness as control."""
        assert wrap("hello", variant="null") == "hello"

    def test_default_variant_prepends_scaffold(self):
        out = wrap("Score this: foo bar")
        assert "HERMES-BLIND" in out
        assert out.endswith("Score this: foo bar")

    def test_all_variants_preserve_original_prompt(self):
        """Every variant must keep the caller's prompt intact at the end."""
        caller_prompt = "Evaluate the paper in evidence/paper.md."
        for variant in VARIANTS:
            wrapped = wrap(caller_prompt, variant=variant)
            assert wrapped.endswith(caller_prompt), f"variant {variant} mutated prompt"

    def test_unknown_variant_raises(self):
        with pytest.raises(ValueError, match="Unknown variant"):
            wrap("prompt", variant="not-a-real-variant")

    def test_v1_contains_four_mechanisms(self):
        """The v1 scaffold must contain the four designed mechanisms."""
        v1 = VARIANTS["v1"].lower()
        assert "prior exposure" in v1, "missing disclosure ritual"
        assert "quoted evidence" in v1 or "evidence" in v1, "missing evidence-gate"
        assert "hedge" in v1, "missing hedging license"
        # output-shape discipline isn't in v1 (it's in 'full'); don't assert here


class TestTokenOrdering:
    """Ablation relies on strict length ordering. If this fails, the sweep
    isn't measuring what we think it is."""

    def test_variants_ordered_by_length(self):
        order = ["null", "micro", "short", "v1", "full"]
        tokens = [token_estimate(v) for v in order]
        assert tokens == sorted(tokens), (
            f"variants not in ascending token order: {dict(zip(order, tokens, strict=True))}"
        )

    def test_micro_is_shortest_non_null(self):
        assert token_estimate("micro") > 0
        assert token_estimate("micro") < token_estimate("short")

    def test_full_is_longest(self):
        lengths = {v: token_estimate(v) for v in VARIANTS}
        assert lengths["full"] == max(lengths.values())


class TestExtractDisclosure:
    def test_prior_exposure_colon_form(self):
        response = "Prior exposure: I've seen this target before.\n\nScore: 7/10"
        assert extract_disclosure(response) == "I've seen this target before."

    def test_prior_exposure_dash_form(self):
        response = "Prior exposure - none\n\nScoring..."
        # "none" is treated as null-disclosure; should return empty-ish
        result = extract_disclosure(response)
        assert result in (None, "none", "")

    def test_disclosed_bracket_form(self):
        response = "[Disclosed]: target is a v2 revision\n\nScoring"
        assert extract_disclosure(response) == "target is a v2 revision"

    def test_no_disclosure_returns_none(self):
        response = "Score: 5/10\n\nReasoning: evidence is weak."
        assert extract_disclosure(response) is None

    def test_empty_response_returns_none(self):
        assert extract_disclosure("") is None

    def test_case_insensitive_matching(self):
        response = "PRIOR EXPOSURE: known"
        assert extract_disclosure(response) == "known"

    def test_only_searches_first_300_chars(self):
        """Disclosure should be upfront; anything buried deep is probably
        not a real disclosure, just incidental text."""
        padding = "x" * 400
        response = padding + "\nPrior exposure: buried disclosure"
        assert extract_disclosure(response) is None


class TestScaffoldInvariants:
    """Invariants the caller relies on — if any break, downstream tools break."""

    def test_default_variant_exists(self):
        assert DEFAULT_VARIANT in VARIANTS

    def test_null_variant_is_empty_string(self):
        assert VARIANTS["null"] == ""

    def test_all_non_null_variants_end_with_double_newline(self):
        """Double newline separates scaffold from caller prompt; if missing,
        scaffold and prompt run together and model may not parse structure."""
        for name, text in VARIANTS.items():
            if name == "null":
                continue
            assert text.endswith("\n\n"), f"variant {name!r} missing \\n\\n tail"

    def test_v1_token_budget(self):
        """v1 should be ≤60 tokens — if it balloons, rename to 'medium'."""
        assert token_estimate("v1") <= 60, (
            f"v1 is now {token_estimate('v1')} tokens — too long for this name"
        )
