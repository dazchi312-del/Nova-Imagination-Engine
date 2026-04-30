# ADR-136: Presence as Scope Discipline (Reflector Axis)

**Status:** Accepted
**Date:** 2026-04-29
**Session:** 39
**Author:** dazchicago
**Supersedes:** None
**Related:** None (forthcoming ADR on Presence-as-pause / Presence-as-axis relationship)

## Context

The Reflector scoring schema (`nova/core/loop.py:ReflectorScore`) defines a
`presence` field, and the parser (`_parse_reflector_response`) extracts it
via `grab("PRESENCE")`. However, `REFLECTOR_RUBRIC` — the contract sent to
phi4 — does not request a PRESENCE score. Phi4 has been faithfully scoring
only the three axes it was asked for (elegance, creative_alignment,
safety_risk) plus the OVERALL composite. The `presence` field has therefore
serialized as `null` in every iteration artifact since the schema was
introduced.

Smoke test `smoke_qwen_ad010` (2026-04-29) confirmed `presence: null` is a
live reflector issue, not a dry-run artifact.

Before patching the rubric, the *definition* of Presence-as-axis must be
canonical, because once phi4 begins scoring it, the calibration of
thousands of downstream iterations depends on a stable semantic anchor.

## Decision

Presence, as a Reflector scoring axis, is defined as **scope discipline**:

> Does every element of the code earn its place against the stated goal,
> or does the code introduce unrequested matter — extra libraries,
> adjacent problems, decorative scaffolding, speculative abstractions,
> premature optimization?
>
> - **1.00** = nothing extraneous; the code is exactly as large as the
>   goal requires.
> - **0.50** = the code addresses the goal but includes one or two
>   unrequested elements (an extra import used once, a helper that
>   wasn't asked for, a speculative parameter).
> - **0.00** = substantially wandering; significant code exists that the
>   goal did not ask for.

## Orthogonality to Other Axes

Presence is deliberately scoped to be orthogonal to the other axes:

| Axis | Question |
|---|---|
| ELEGANCE | Is the code clear, simple, idiomatic? |
| CREATIVE_ALIGNMENT | Did the code solve the stated goal well? |
| SAFETY_RISK | Does the code contain sketchy or opaque patterns? |
| **PRESENCE** | **Did the code engage *only* the stated goal?** |

CREATIVE_ALIGNMENT measures the *quality* of engagement with the goal;
PRESENCE measures the *scope* of engagement. A code iteration may score
high on creative_alignment (solved the goal well) and low on presence
(but did so with substantial unrequested matter). The qwen2.5 matplotlib
over-reach pattern — asked for a data summary, returned a summary plus
a plot with styling — is the canonical real-world example: high
alignment, low presence.

Conversely, verbose but disciplined code may score moderate on elegance
and high on presence — these axes do not entail each other.

## Examples

**Goal:** "write a function that returns the sum of two integers"

- **Presence 1.00:** `def add(a: int, b: int) -> int: return a + b`
- **Presence 0.70:** the above plus a docstring with a usage example
  (helpful, but unrequested).
- **Presence 0.40:** the above plus input validation, type coercion,
  and a `__main__` block demonstrating use.
- **Presence 0.10:** a `Calculator` class with `add`, `subtract`,
  `multiply`, `divide`, logging, and CLI argument parsing.

The qwen2.5 matplotlib over-reach pattern is the canonical real-world
Presence ~0.30 case: the goal was engaged, but with substantial
unrequested decoration.

## Relation to Presence-as-Pause

`_run_one_iteration` implements a behavioral form of Presence as
`min_consideration_ms` — a pre-generation pause. ADR-136 establishes the
*evaluative* form: a post-generation score on the output itself.

Both express the same underlying discipline (*do not rush past the actual
ask*) on different surfaces:

- **Pre-generation:** do not generate before you have considered.
- **Post-generation:** do not include what was not asked for.

These are intended to reinforce one another but are independently measured
and independently tunable. A future ADR will formalize their relationship.

## Rejected Framings

- *"restraint"* — moralistic; biases the model toward self-assessment of
  virtue rather than output assessment.
- *"focus"* — cognitive framing; describes attention rather than artifact.
- *"economy"* — reads as performance/efficiency, not scope.
- *"fidelity to scope"* — accurate but stylistically stiff.
- *"stay with the goal"* — metaphorical; insufficient operational
  discriminator for phi4.

"Scope discipline" was selected for operational clarity and absence of
moral or cognitive connotation.

## Consequences

1. `REFLECTOR_RUBRIC` in `nova/core/loop.py` must be updated to request
   PRESENCE scores from phi4, with the definition above embedded inline
   (including the 0.50 midpoint anchor).
2. The header count ("four axes") must be corrected — five scored values,
   four of which are axes and one of which (OVERALL) is a composite.
3. Existing iteration artifacts with `presence: null` are historical
   record; they are not retroactively rescored.
4. A future ADR will address the relationship between Presence-as-pause
   and Presence-as-axis as evidence accumulates from live scoring.
5. Tutor mode (forthcoming) may require an adjusted Presence rubric,
   since pedagogical scaffolding is intentionally "unrequested matter."
   This will be addressed in a separate ADR.
