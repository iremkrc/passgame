# Human quality audit

Held-out model evaluation requires a second-researcher review. Automated validation
cannot sign the human worksheet. The reported study uses the development split.

Review the 12 games in `data/audit-sample.jsonl`, two per interaction family.
Export an unsigned worksheet:

```sh
uv run --locked python -m passgame.export --dataset data --output outputs/audit
```

For every game verify the neutral starting string, all eight valid reference
prefixes, the required change at every reference turn, and the final witness.
For recorded interference challenges check the full one-edit new-valid
neighbourhood and two-edit full-valid witness, including insertion/deletion
alternatives and the minimum number of old rules broken. These labels describe
the private reference path; classify actual model strings independently.

Record reviewer, date, sample hash, discrepancies, and resolutions in a signed
review document. Set `human_audit_status` in `data/manifest.json` to `complete` only
after the review. Generation and export never sign the audit. Preserve evaluated
evidence and create a fresh dataset/output directory for substantive changes.
