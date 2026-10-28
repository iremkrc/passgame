# Study protocol

The study asks whether models preserve earlier constraints while incorporating a
new rule, and whether disclosure order changes performance. Each of 24 development
base games has eight rules, presented in original, reverse, and two fixed random
orders. Orders start fresh conversations from the same neutral string and end with
the same rule set.

Requests include full conversation history. Each latest user message repeats
binding earlier rules and introduces exactly one new rule. Only successful model
final answers become subsequent inputs. Future rules, witnesses, and checker
feedback are private.

Responses must be JSON with one string field: `{"password":"..."}`. Recorded
conditions use strict parsing or additionally accept one outer Markdown fence.
Format, domain, or active-rule failure ends the game. Infrastructure transport
retries do not provide semantic retries, feedback, or tools.

## Example

Starting with `abc1`, introduce these rules:

1. Exactly two digits: `abc12` is valid.
2. Digit sum exactly 11: `abc47` is valid.
3. Contains `8`: `abc38` meets all three rules.

Changing `abc47` to `abc48` meets the new rule but breaks the sum. Models may use
any valid repair, including a full rewrite; minimum distance is not required.
These examples are never inserted as assistant responses into model histories.

Interference certificates describe actual incoming model strings. Bounded checks
can prove no-op, independent, or interfering cases; unknown does not establish
unsatisfiability. Reference paths prove satisfiability, not guaranteed model states.
Interference strata remain descriptive because models choose their own strings.

The paper uses the 24 development games, which were also used during protocol
development. See [reproducibility](reproducibility.md) for endpoint definitions.

## Rule language

| Rule | Meaning |
| --- | --- |
| `length` | Compare total character count |
| `digit_count`, `digit_sum` | Compare ASCII digit occurrences or their sum |
| `char_count`, `substring_count` | Compare occurrences; substring matches may overlap |
| `contains`, `forbids` | Require a case-sensitive substring to be present/absent |
| `char_at` | Require a character at a one-based position |
| `balanced` | Require correctly nested selected bracket types |

Numeric comparisons use `eq`, `le`, or `ge` (exactly, at most, at least).
Rules are checked deterministically in `src/passgame/constraints.py` and
independently cross-checked in `src/passgame/audit.py`.
