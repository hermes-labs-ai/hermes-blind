# Security policy

## Reporting

Email **roli@hermes-labs.ai** with subject `[security] hermes-blind`.
Please do not open a public issue for a suspected vulnerability.

## Threat model

hermes-blind is a local, standard-library-only text transformation package.
It makes no network requests and handles no credentials.

Recovery mode reads a local session JSONL chosen by the caller. The generated
markdown can contain user-authored text from the first turn. It omits the
absolute source path by default, but callers must still treat the output as
potentially sensitive and inspect it before sharing.

The package does not defend against prompt injection, model deception,
malicious session logs, or downstream data handling by an LLM provider.
`extract_disclosure()` is diagnostic only; its output must never authorize a
security decision.
