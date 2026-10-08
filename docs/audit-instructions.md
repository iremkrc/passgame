# Human audit worksheet

The project plan calls for a second-researcher review before held-out model evaluation. Automated validation has a separate status and cannot sign this worksheet.

Review the 20 paired cases in `data/audit-sample.jsonl` (40 focal states), spanning all four interaction families and the three active-rule counts. For each case:

1. Read the rule descriptions from `src/passgame/constraints.py` and independently score both incoming strings against every old rule.
2. Check that the new rule is false on both incoming strings.
3. Check the certified one-edit independent witness, the two-edit interfering witness, and their edit distances.
4. Check the interfering lower bound by considering substitution, insertion and deletion, not only the obvious edit.
5. Confirm identical old/new constraints, equal input lengths, split membership and any character-count matching claim.
6. Inspect cases with multiple valid answers and confirm that scoring accepts all satisfying artifacts, not just the supplied witness.

Record reviewer name, date, sample hash, discrepancies and their resolution in a new `docs/audit-signoff.md`. On a provisional pilot/main-preparation child, update `human_audit_status` in `data/manifest.json` to `complete` only after the reviewer signs off. Do not edit an already evaluated baseline snapshot. Data file hashes must remain unchanged unless a documented generation bug requires a new benchmark version and a fresh review.

If the team elects to change this human-audit requirement, record that design change explicitly before paid held-out evaluation rather than claiming an audit happened.
