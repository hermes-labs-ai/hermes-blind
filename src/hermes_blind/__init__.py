"""hermes-blind — context-compensation scaffold for LLM evaluation prompts.

Prepend a ~40-token language scaffold to any scoring/evaluation prompt to
reduce four kinds of bias: self-scoring, user-preference, session-carryover,
prior-position-commitment. Backend-agnostic; complements --bare mode.

Usage:

    from hermes_blind import wrap
    prompt = wrap("Rate this paper 0-10...")

    # With a named variant
    prompt = wrap("...", variant="micro")

    # Extract the disclosure line from the model's response
    from hermes_blind import extract_disclosure
    disclosure = extract_disclosure(model_response)
"""

from .scaffold import DEFAULT_VARIANT, VARIANTS, extract_disclosure, wrap

__version__ = "0.0.6"
__all__ = ["wrap", "extract_disclosure", "VARIANTS", "DEFAULT_VARIANT"]
