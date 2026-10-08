# PassGame validation release: prespecified design

This document is frozen with the benchmark-validation baseline. It specifies diagnostic validation and a future model study; no diagnostic result is evidence about LLMs.

## Dataset and matching

Seed: 20261008. Four retained pair templates: numeric sum/digit-count budget; fixed position with character count; fixed position with required substring; fixed position with forbidden substring. Each pair has identical old/new rules, equal input length, new-only minimum distance one, and certified full distance one versus two. Non-numeric pairs additionally match character multiplicities in the incoming states. The nominal 3/5/8 active-rule strata include some easy/redundant rules and must not be called a calibrated complexity axis.

There are 24 development base pairs and 120 disjoint test base pairs (four families × three loads × ten test cases). Variants never cross splits. The native suite uses 30 test base sets with two initial strings; the order suite uses 20 test final sets with original, reverse and two seeded random orders. Final constraint witnesses prove every prefix satisfiable.

Controlled prefixes use already-valid unchanged artifacts at earlier turns. Controlled repair estimates therefore condition on an oracle-supplied valid prefix. Native trajectories start from `seed0!` or `seed9!` and use the model's own responses. They never inherit a fixed interference label after the current state changes. If complete certification cannot be obtained, the dynamic label is unknown.

## Evaluation and endpoints

No training. No LLM judge. One semantic attempt per turn. All active rules and the exact current artifact are repeated. No minimum-edit requirement, tool use, provider JSON enforcement, semantic retries or oracle repairs of model state. Format/domain failures preserve the previous state; transport failures are missing evidence and stop that episode.

Primary H1: independent-minus-interfering full-success difference on paired controlled repairs, per model. H2: unconditional new-success/retention-failure rate, its paired condition contrast, and descriptive retention failure conditional on new success. Retention is limited to rules satisfied on the incoming state. H3: original-minus-reverse final and whole-episode success differences, blocked by identical final set and initial string. Random-order results are descriptive.

Report 95% paired bootstrap intervals from 2,000 seeded resamples. Bootstrap base scenario blocks for controlled repairs and final-set blocks for order contrasts. No confirmatory p-values are planned for this release. If formal tests are later added, specify tests, familywise multiplicity treatment and meaningful effect sizes before accessing paid held-out responses. Do not claim equivalence from an interval crossing zero.

Record infrastructure missingness, format failures, semantic failure classes, denominators, first failure, right-censoring at the horizon, recovery and edit sizes. Fresh-solve controls have no retention or incoming-artifact edit metric. Model settings, IDs, prices, budget and exposure method remain pending and must be frozen on a pilot child before the held-out study.

## Audit gate and limitations

Every generated input, witness and certificate receives automated validation. Independent small-domain exhaustive checker tests cover all rule kinds. A 20-case stratified human audit is planned and remains pending until signed by a researcher; no automated process marks it complete. The pending gate blocks paid test evaluation but permits development pilots and diagnostic baseline checks. This follows the accepted project plan's instruction to audit before held-out model evaluation.

Model access, total spending ceiling, pilot-based precision estimates, and evidence from actual LLMs are not yet established. The baseline will report benchmark correctness and diagnostic behavior only. Balanced brackets are implemented but generated bracket cases and extra prompt ablations are outside this release. Model-derived H1–H3 conclusions remain pending.
