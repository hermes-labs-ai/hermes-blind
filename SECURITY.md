# Security Policy

## Supported Versions

`hermes-blind` is v0.0.x — experimental. The scaffold itself is a string
constant; it contains no executable code, no network calls, no credential
handling, no user data storage. The surface area for security vulnerabilities
is small but not zero.

## Reporting a Vulnerability

Email: **rbosch@lpci.ai** with subject line `[security] hermes-blind`.

Do not open public GitHub issues for security reports.

We will acknowledge within 72 hours. If the issue is valid, we will ship a
fix in the next patch release and credit the reporter (unless anonymous is
preferred).

## Threat Model (v0.0.x)

What this package guards against:

- None directly. This is a prompt-engineering utility, not a security tool.

What this package does **not** defend against:

- **Prompt injection** — a target containing `[/HERMES-BLIND]` or adversarial
  text can interfere with the scaffold's structure. Callers handling
  untrusted targets should sanitize before wrapping.
- **Motivated model subversion** — a fine-tuned or jailbroken model can
  ignore the scaffold entirely. The scaffold is for honest bias reduction,
  not adversarial robustness.
- **Downstream API leakage** — wrapped prompts are passed to whichever LLM
  backend the caller chooses. Whatever that backend does with the prompt is
  outside this package's scope.

## Disclosure-line Caveat

`extract_disclosure()` parses model output looking for prior-exposure text.
The disclosure is an honor-system signal — the model may lie, omit, or
confabulate. Do not rely on the disclosure line for any security decision.
It is diagnostic, not authoritative.
