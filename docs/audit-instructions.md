# Human audit worksheet

The project plan calls for a second-researcher review before held-out model evaluation. Automated validation has a separate status and cannot sign this worksheet.

## Current version-3 progressive suite

Review the 12 individual held-out games in `data/sequential-v3/audit-sample.jsonl`, two per family. Export an unsigned worksheet using `uv run --locked python -m passgame.export --dataset data/sequential-v3 --output outputs/readable-v3`.

For each game, verify that the neutral initial string fails the first rule; that all eight reference outputs satisfy their active prefixes; that each example step requires a change; and that the final witness satisfies the entire rule set. At each recorded reference challenge, check the complete one-edit new-valid neighborhood and the two-edit full-valid witness, including insertion/deletion alternatives and the minimum number of distinct old predicates broken. These certificates apply to the example path only. Actual model trajectories must be classified separately, and any valid answer is accepted.

Record the reviewer, date, sample hash, discrepancies and resolutions in `docs/audit-signoff-v3.md`. Only a human reviewer can sign off; update `human_audit_status` in `data/sequential-v3/manifest.json` to `complete` only after that review. The generator/exporter never does so. A v2 audit does not automatically sign off the new dataset. Keep completed snapshots unchanged.

## Historical version-2 focal pairs

Review the 20 paired cases in `data/audit-sample.jsonl` (40 focal states), spanning all six interaction families, interference degrees one/two/three, and active-rule counts 3/5/6/8. For each case:

1. Read the rule descriptions from `src/passgame/constraints.py` and independently score both incoming strings against every old rule.
2. Check that the new rule is false on both incoming strings.
3. Check the certified one-edit independent witness, the two-edit interfering witness, and their edit distances.
4. Check the interfering lower bound by considering substitution, insertion and deletion, not only the obvious edit.
   For multi-rule cases, verify the minimum number of old rules broken over every shortest new-only edit, the minimum-break witness and its broken rule IDs. The rule IDs can differ across repairs; the guaranteed minimum is a count. Verify that distinct substantive predicates produce the count.
5. Confirm identical old/new constraints, equal input lengths, split membership and any character-count matching claim.
6. Inspect cases with multiple valid answers and confirm that scoring accepts all satisfying artifacts, not just the supplied witness.

Record reviewer name, date, sample hash, discrepancies and their resolution in a new `docs/audit-signoff.md`. On a provisional pilot/main-preparation child, update `human_audit_status` in `data/manifest.json` to `complete` only after the reviewer signs off. Do not edit an already evaluated baseline snapshot. Data file hashes must remain unchanged unless a documented generation bug requires a new benchmark version and a fresh review.

If the team elects to change this human-audit requirement, record that design change explicitly before paid held-out evaluation rather than claiming an audit happened.
