# PassGame version 2: prespecified design

This amendment implements multiple-rule interference and sequential disclosure at the user's request, before any LLM evaluation. The original validation release is preserved on its completed experiment branch. Diagnostic results establish benchmark correctness, not LLM behavior.

## Dataset and matching

Seed: 20261008. Preserve the four original templates and their rules, parameters and incoming states. Append two numeric families with certified interference degrees two and three, using a separate random stream seeded 20261009. Degree k means every shortest new-only repair breaks at least k old rules, and at least one breaks exactly k. The failing rule IDs may differ across repairs.

Two-rule interference uses exact digit count, an upper digit-sum budget, exact multiplicity of a protected digit, and exact length. Three-rule interference also requires a digit adjacency pattern. The new rule fixes a digit at a specified position. Pairs match old/new constraints, input length and character multiplicities. Independent full distance is one; interfering full distance is two. The complete radius-one certificate includes substitutions, insertions and deletions and is independently audited. Distinct constraints produce the multiple-rule breakage.

Version 2 has 32 development pairs and 160 test pairs: 120 original test pairs and 40 multi-rule test pairs. Original loads are 3/5/8, degree-two loads 5/8, degree-three loads 6/8. Load includes old rules plus the new rule and is not a calibrated complexity measure. Cross-template degree comparisons are descriptive and may include family/load differences.

The native suite uses 30 test base sets, balanced across six families, with two initial strings per set. The order suite uses 20 test final sets with original, reverse and two seeded random orders. Development suites contain all six families. Final witnesses prove all prefixes satisfiable. A 20-pair human audit spans the six families and degrees one/two/three.

## LLM exposure and trajectories

No training, LLM judge, tools or provider JSON enforcement. One semantic attempt per turn. Reveal exactly one new rule per user message alongside the current password. Earlier rules remain binding and appear only in their original conversation turns. Preserve original conversation history; do not repeat or summarize the cumulative rule list. Every assistant message and intermediate password comes from the evaluated model. The evaluator retains the full rule set and certificates privately for scoring.

LLM runs may use only native/order tracks. Scripted controlled prefixes and all-at-once fresh-solve prompts are offline diagnostics only and rejected for chat adapters. Zero-cost validation includes controlled diagnostics to check templates and native/order diagnostic trajectories to check disclosure and state transitions.

Start from seed0! or seed9!. Parsed domain-valid responses become the next password even when wrong. Format/domain failures count as failed turns and preserve the previous password; raw responses remain in history. Transport failures are missing evidence and stop the episode. Full rewrites count as success; no minimum-edit requirement, semantic retry or oracle repair.

Interference depends on the actual incoming password. Recompute certificates from model states; never copy fixed offline labels onto trajectories. Already-invalid old states or repairs outside the proven search bound are unknown; no-ops are separate. A model can avoid a template's intended interference through its own choices. This is part of autonomous evaluation.

## Endpoints and inference

LLM H1: descriptive full-success comparisons across certified on-policy interference degrees, with denominators, family/load context and unknown/no-op rates. This replaces the original paired controlled H1 effect: autonomous states are not randomized/matched, so no causal interference claim is planned. Paired independent-minus-interfering contrasts remain offline diagnostic-only.

LLM H2: new-rule success with regression of previously satisfied old rules, unconditional and conditional on new-rule success. Record the number and IDs of newly violated old rules. Existing failures are not new regressions. Invalid outputs have unknown breakage counts while full/new/retention failures remain zero where eligible. Paired H2 contrasts remain diagnostic-only.

H3: original-minus-reverse final and whole-episode success differences, blocked by identical final set and initial string. Random orders are descriptive. Report 95% paired bootstrap intervals from 2,000 seeded resamples for offline contrasts and H3. No confirmatory p-values, equivalence conclusions or independent-turn inference. On-policy interference summaries receive no spurious paired confidence intervals.

Record exact prompts, responses, before/after checks, edit distances, dynamic certificates, infrastructure missingness, semantic/format failures, denominators, first failure, right-censoring and recovery. Freeze model IDs, verified prices, settings and spending ceiling after a development pilot and before held-out calls.

## Audit and limitations

Automated validation audits inputs, witnesses and every shortest new-only candidate with an independent checker. A human reviewer separately signs the 20-pair audit; automation never marks it complete. Pending review blocks paid held-out evaluation and permits development pilots and zero-cost diagnostics, following the accepted plan. Changing this requirement requires an explicit amendment before paid held-out evaluation.

Model access, model choices, spending ceiling and LLM evidence remain pending. The six families are templates, not proof of unseen-template generalization. Balanced brackets are implemented and tested but generated bracket cases remain deferred.
