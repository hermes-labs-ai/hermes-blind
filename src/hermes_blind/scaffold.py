"""The scaffold itself — four variants for the ablation study.

Each variant wraps the caller's prompt with a [HERMES-BLIND]...[/HERMES-BLIND]
block that forces: disclosure of prior exposure, evidence-gating, hedging
license, and (in longer variants) output-shape discipline.

Token counts are approximate (tiktoken `cl100k_base`); the point is relative
ordering across variants for the ablation, not absolute accuracy.
"""

from __future__ import annotations

import re

# --- scaffold variants ---
# The null variant is the control (no scaffold); used by the experiment
# harness so the same pipeline can be run with/without the scaffold by
# flipping a variant name rather than branching the caller.
VARIANTS: dict[str, str] = {
    "null": "",
    "micro": "[BLIND] Score on quoted evidence only. [/BLIND]\n\n",
    "short": (
        "[BLIND] Prior exposure? disclose. Evidence quotes only. "
        "Thin=hedge. [/BLIND]\n\n"
    ),
    "v1": (
        "[HERMES-BLIND]\n"
        "If you have prior exposure to this target or its author, "
        "state it in one line.\n"
        "Score using only quoted evidence from the target text below.\n"
        "Unknown or thin evidence = hedge; do not confabulate.\n"
        "[/HERMES-BLIND]\n\n"
    ),
    "full": (
        "[HERMES-BLIND]\n"
        "If you have prior exposure to this target or its author, "
        "state it in one line.\n"
        "Score using only quoted evidence from the target text below.\n"
        "Unknown or thin evidence = hedge; do not confabulate.\n"
        "Do not reason outside the expected output shape.\n"
        "Prefer hedging over a confident wrong score.\n"
        "[/HERMES-BLIND]\n\n"
    ),
}

DEFAULT_VARIANT = "v1"

# Regex for extracting the disclosure line from model responses.
# Models commonly format as: "Prior exposure: ..." or "[disclosed] ..."
# or just a bare first line after the scaffold is processed.
_DISCLOSURE_PATTERNS = [
    re.compile(r"prior exposure[:\-]\s*(.+?)(?:\n|$)", re.IGNORECASE),
    re.compile(r"\[disclos(?:ed|ure)\][:\-]?\s*(.+?)(?:\n|$)", re.IGNORECASE),
    re.compile(r"exposure[:\-]\s*(.+?)(?:\n|$)", re.IGNORECASE),
]


def wrap(prompt: str, variant: str = DEFAULT_VARIANT) -> str:
    """Prepend the hermes-blind scaffold to the given prompt.

    Parameters
    ----------
    prompt : str
        The caller's scoring/evaluation prompt.
    variant : str
        One of: null, micro, short, v1, full. Defaults to "v1".
        "null" is a no-op (returns prompt unchanged) used by the ablation
        harness as a control.

    Returns
    -------
    str
        The wrapped prompt. For the null variant, equal to the input prompt.

    Raises
    ------
    ValueError
        If the variant name is not in VARIANTS.
    """
    if variant not in VARIANTS:
        raise ValueError(
            f"Unknown variant: {variant!r}. "
            f"Known: {sorted(VARIANTS.keys())}"
        )
    return VARIANTS[variant] + prompt


def extract_disclosure(response: str) -> str | None:
    """Extract the disclosure line from a model response, if any.

    Returns None if no disclosure pattern matched, which itself is a signal —
    a model that never discloses may be ignoring the scaffold.

    Parameters
    ----------
    response : str
        The full text the model returned.

    Returns
    -------
    str or None
        The disclosed text (stripped), or None if no disclosure was found.
    """
    if not response:
        return None
    # Only check the first ~300 chars — disclosure should be upfront.
    head = response[:300]
    for pattern in _DISCLOSURE_PATTERNS:
        match = pattern.search(head)
        if match:
            text = match.group(1).strip()
            # Reject trivially empty or non-informative "none" responses
            # as non-disclosure (still a valid null-disclosure signal, but
            # distinguishable from "didn't see the scaffold at all").
            if text and text.lower() not in {"none", "n/a", "na", "-"}:
                return text
            return text or None
    return None


def token_estimate(variant: str) -> int:
    """Rough token count for a scaffold variant, word-count approximation.

    Not precise — use tiktoken if you need exact. Good enough for the
    ablation sweep's "order-of-magnitude" claim about minimality.
    """
    if variant not in VARIANTS:
        raise ValueError(f"Unknown variant: {variant!r}")
    scaffold = VARIANTS[variant]
    if not scaffold:
        return 0
    # Rough: ~1.3 tokens per word for English, plus punctuation padding
    words = len(scaffold.split())
    return int(words * 1.3) + 2
