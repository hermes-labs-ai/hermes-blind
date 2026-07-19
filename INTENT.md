# hermes-blind — intent

## Purpose

Provide small, inspectable language scaffolds for two recurring failure
surfaces in LLM workflows:

1. an evaluator may rely on context or prior exposure instead of target
   evidence; and
2. a long agent session may lose parts of the user's original direction.

## Accepted scope

- prepend a versioned evaluation scaffold while preserving the caller prompt;
- parse an optional disclosure line from model output;
- extract turn-one goal sentences from Claude Code and Codex JSONL;
- emit a compact recovery block for explicit human or agent reuse;
- provide reusable intent and target-scope preambles for rubric framing;
- remain deterministic, local, dependency-free, and inspectable.

## Non-goals

- automatic drift detection;
- automatic insertion into a live model session;
- proof that the scaffold changes downstream model behavior;
- security enforcement or adversarial prompt-injection defense;
- replacement for context isolation;
- ingestion, upload, or storage of user sessions.

## Evidence contract

Mechanical claims require deterministic tests and clean-package verification.
Behavioral claims require an independent controlled evaluation. Anchor
extraction recall may support an extraction claim only; it must not be
promoted into a drift-recovery claim.

## Design invariants

1. `null` is an exact no-op.
2. Wrapped prompts preserve the caller's prompt at the tail.
3. Recovery output is deterministic for fixed input bytes and options.
4. Absolute session paths are not emitted by default.
5. No model, network, or non-stdlib runtime dependency.
6. Unfinished research harnesses remain outside the public runtime.
