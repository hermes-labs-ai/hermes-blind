"""Deterministic prompt and session-recovery scaffolds.

The wrap function prepends an evidence-gating scaffold to an evaluation
prompt. build_recovery_scaffold (in hermes_blind.apply) extracts a compact
turn-one anchor from Claude Code or Codex session JSONL.

The package is dependency-free and makes no model or network calls. Its
mechanics are tested; behavioral claims such as bias reduction or successful
drift recovery remain experimental.
"""

from .preambles import (
    INTENT_DEBIAS_PREAMBLE,
    SCOPE_CHOICES,
    SCOPE_PREAMBLES,
    VALENCE_WORDS,
    compose_intent,
    detect_valence,
    intent_debias,
    scope_class_preamble,
    wrap_intent_for_rubric,
)
from .scaffold import (
    DEFAULT_VARIANT,
    LENGTH_SWEEP_VARIANTS,
    MECHANISM_VARIANTS,
    VARIANTS,
    extract_disclosure,
    wrap,
)

__version__ = "0.1.3"
__all__ = [
    "wrap",
    "extract_disclosure",
    "VARIANTS",
    "DEFAULT_VARIANT",
    "LENGTH_SWEEP_VARIANTS",
    "MECHANISM_VARIANTS",
    "intent_debias",
    "scope_class_preamble",
    "wrap_intent_for_rubric",
    "compose_intent",
    "detect_valence",
    "INTENT_DEBIAS_PREAMBLE",
    "SCOPE_PREAMBLES",
    "SCOPE_CHOICES",
    "VALENCE_WORDS",
]
