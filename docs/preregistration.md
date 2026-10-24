# PassGame version 2: prespecified design

Current main study: the version-3 neutral-seed amendment dated 2026-10-24 below supersedes v2 focal-state initialization. Earlier design text and amendments remain as historical records, not a claim that later changes were preregistered before the pilots.

This amendment implements multiple-rule interference and sequential disclosure at the user's request, before any LLM evaluation. The original validation release is preserved on its completed experiment branch. Diagnostic results establish benchmark correctness, not LLM behavior.

## Dataset and matching

Seed: 20261008. Preserve the four original templates and their rules, parameters and incoming states. Append two numeric families with certified interference degrees two and three, using a separate random stream seeded 20261009. Degree k means every shortest new-only repair breaks at least k old rules, and at least one breaks exactly k. The failing rule IDs may differ across repairs.

Two-rule interference uses exact digit count, an upper digit-sum budget, exact multiplicity of a protected digit, and exact length. Three-rule interference also requires a digit adjacency pattern. The new rule fixes a digit at a specified position. Pairs match old/new constraints, input length and character multiplicities. Independent full distance is one; interfering full distance is two. The complete radius-one certificate includes substitutions, insertions and deletions and is independently audited. Distinct constraints produce the multiple-rule breakage.

Version 2 has 32 development pairs and 160 test pairs: 120 original test pairs and 40 multi-rule test pairs. Original loads are 3/5/8, degree-two loads 5/8, degree-three loads 6/8. Load includes old rules plus the new rule and is not a calibrated complexity measure. Cross-template degree comparisons are descriptive and may include family/load differences.

The native suite uses 30 test base sets, balanced across six families, with two initial strings per set. The order suite uses 20 test final sets with original, reverse and two seeded random orders. Development suites contain all six families. Final witnesses prove all prefixes satisfiable. A 20-pair human audit spans the six families and degrees one/two/three.

## LLM exposure and trajectories

No training, LLM judge, tools or provider JSON enforcement. One semantic attempt per turn. Reveal exactly one new rule per user message alongside the current password. In the original history-only exposure, earlier rules remained binding and appeared only in their original conversation turns, without cumulative reminders. The rule-reminder amendment below supersedes that exposure for the main pilot. Every assistant message comes from the evaluated model. All LLM tracks advance only when every active rule passes, carrying that successful password into the next turn. The evaluator retains certificates privately for scoring.

The original LLM protocol allowed native/order tracks. The corrected predefined-start protocol below also allows fixed_start. Scripted controlled prefixes and all-at-once fresh-solve prompts remain offline diagnostics only and rejected for chat adapters. Zero-cost validation includes controlled diagnostics to check templates and autonomous diagnostic trajectories to check disclosure and state transitions.

Native/order episodes start from seed0! or seed9!. A successful response becomes the next password. Any old-rule violation, new-rule failure, invalid format, or invalid domain terminates the episode immediately, with the failed raw response retained in evidence and no next-stage request. Transport failures are missing evidence and stop the episode. Full rewrites count as success; no minimum-edit requirement, semantic retry or oracle repair. Earlier historical runs that continued after failures are not retroactively assigned the new policy.

Interference depends on the actual incoming password. Recompute certificates from model states; never copy fixed offline labels onto trajectories. Already-invalid old states or repairs outside the proven search bound are unknown; no-ops are separate. A model can avoid a template's intended interference through its own choices. This is part of autonomous evaluation.

Certification implementation update (2026-10-22, after the development pilot): native/order two-edit witnesses are searched from the actual incoming string and currently active rules, without the episode's final witness. After exhaustive radius-one checking, search up to 100,000 distinct radius-two candidates, prioritizing new-valid one-edit intermediates and then considering the remaining intermediates. Record candidate counts and whether the search found a witness, reached its limit, or exhausted radius two. A verified two-edit witness plus the radius-one lower bound certifies full distance two; unsuccessful search remains unknown. Fixed offline data and label definitions are unchanged. Earlier pilot artifacts retain their original certificates; reclassification must be identified as analysis under the updated certifier.

## Predefined-start correction (2026-10-23, after the reset-protocol pilot)

The user requested shared predefined initial strings followed by the model's own outputs. The assistant's earlier per-turn reset implementation was a mistaken interpretation, not a requested protocol change. The completed 364-request reset pilot is historical evidence of a different protocol, not results for the requested autonomous experiment. Preserve its raw records and frozen source; label historical reanalysis legacy_reset and never merge it with corrected fixed_start trajectories.

For each existing pair member, initialize a fresh fixed_start conversation from its predefined string once. Introduce one rule per user turn. Retain exact model replies and carry successful passwords forward. Under the user's subsequent first-failure policy below, wrong or malformed answers end the conversation. No per-turn resets, oracle repairs, fabricated prefixes, or semantic retries. This correction originally used history-only prompts; the later reminder amendment changes the main prompt condition.

Score all attempted turns, including phases prefix and focal when reached. Record the scenario's initial_condition and intended_interference_degree descriptively; certify interference using actual incoming model states and active rules. Initial-case labels are not copied onto evolved trajectories and do not support a paired focal interference contrast. Include fixed-start conversations in final/whole-episode and survival summaries; exclude completed shorter episodes from later survival denominators. H3 remains specific to the order track.

There are 64 development conversations with at most 364 requests per model, and 320 held-out conversations with at most 1,820 requests. The initial strings and ordered rules are identical across models for a given case member. Subsequent successful strings may differ; certified interfering-turn coverage is measured rather than guaranteed. Human audit remains required for held-out evaluation. Use a fresh output directory and a new frozen snapshot for corrected runs. This correction follows pilot evidence and must not be presented as a pre-pilot registration.

## First-failure termination amendment (2026-10-23)

At the user's explicit request, all new native/order/fixed_start conversations terminate on the first response that fails any active rule or the format/domain contract. Record that failed attempt, its checks, termination reason, and null next_state, then stop before disclosing another rule. Continue with the next independent conversation; there is no retry, repair, reset, or later response in the failed episode. Successful responses alone advance the state.

Mark records with termination_policy first_failure. Treat early model failures as completed observed episodes with zero final/whole-episode success, not infrastructure missingness. Later stages are unattempted and receive no fabricated per-turn scores. Report first-failure stage, survival, at-risk denominators, and reached-stage counts. Partial histories caused by infrastructure or interruption remain incomplete. Survival counts retain early failures after their failure stage; episodes with shorter scheduled horizons leave later denominators.

Planned request counts are upper bounds. Completion accounts for skipped_after_failure and requires every planned episode to have reached its horizon or a recorded terminal model failure, with no infrastructure missingness or budget stop. Cached failure rows terminate again on resume without sending the next-stage request. Historical reset/continue runs retain their actual protocols and must not be relabelled as first-failure experiments.

## Eight-rule-only amendment (2026-10-23, after the mixed-length pilot)

At the user's request, the current pilot selects exactly eight scheduled rules per game. Set rule_count to 8 and filter cases by len(old_rules)+1 and episodes by len(rules), before computing request/episode plans. Exclude shorter games rather than adding padding rules or modifying the frozen dataset. Record the selection and selected pair count in metadata; reject empty selections. Keep the mixed-length pilot and its artifacts as a separate historical study.

The development subset contains 12 pairs (24 games), with two pairs per family across all six families. Intended interference degrees one/two/three contribute 8/2/2 pairs. Maximum requests are 24 times eight, or 192 per model. Held-out contains 60 pairs (120 games), with ten pairs per family, 40/10/10 pairs by intended degree, and at most 960 requests. Standardized initial strings, one-new-rule disclosure, actual model-generated state transitions, first-failure termination, adaptive certification, and the held-out audit gate remain part of the protocol. Eight is the scheduled horizon, not a guarantee every game will reach turn eight. Actual interference coverage remains observed rather than assigned to evolved states.

Use configs/dev-qwen2.5-7b-eight-rules.yaml and a new output directory and frozen snapshot. This selection amendment follows the mixed-length development evidence; it is not a pre-pilot registration. It standardizes the scheduled game length and does not itself establish a causal interference effect.

## Previous-rule reminder amendment (2026-10-23, after development evidence)

At the user's request, the main eight-rule pilot sets remind_previous_rules to true. Each user message contains the actual current password, every previously introduced rule under Previous rules (still binding), and exactly one new rule. Repeat the original rule IDs and deterministic descriptions without summarizing them. The first turn explicitly has no previous rules. Keep the full original conversation and exact model replies. Do not disclose future rules, witnesses, certificates, or checker feedback, and do not add a minimum-edit requirement.

Reminders are available to fixed_start/native/order trajectories. Omitted settings default to false to preserve the history-only comparison. The main configuration is configs/dev-qwen2.5-7b-eight-rules.yaml; configs/dev-qwen2.5-7b-eight-rules-no-reminders.yaml preserves the corresponding history-only condition. The main output is outputs/dev-qwen2.5-7b-eight-rules-reminders-stop-on-failure. Record the prompt setting/version in metadata, completion, and each trajectory row; use cumulative_rule_reminders_v1 versus history_only_v1 and distinct state-transition protocol versions. Keep their results separate and reject attempts to append changed prompts to existing evidence.

The eight-rule selection, cases, starting strings, rule order, model settings, scoring, actual-state certification, successful-output propagation, first-failure termination, and held-out audit gate remain unchanged. Reminders reduce dependence on locating earlier constraints in history; their effect on success or certified interference exposure must be measured. This is a retrospective design amendment, not a pre-pilot registration or a guarantee of reaching interference.

## Neutral-seed progressive amendment (2026-10-24, after development evidence)

The v2 fixed_start runner reused incoming focal-repair states as starts for whole conversations. These states were valid under the first seven rules. This was incorrect for the requested progressive game. Preserve data/ and completed snapshots/results; use the new versioned data/sequential-v3 dataset for new main evaluations. The current configuration selects seeded, eight rules, reminders, and development; its output is outputs/dev-qwen2.5-7b-progressive-eight-rules-v3.

V3 contains 24 distinct development episodes and 120 held-out episodes, balanced four/twenty per family. Seeds such as abc1 contain no case-specific prepared final solution and fail the first rule. Fixed eight-rule sequences are identical across models for each episode. Private reference paths require a repair at each step and independently verified valid outputs establish satisfiability of every cumulative prefix. On those reference paths, degree-one challenges occur by turn 3, degree-two by turn 4, and degree-three by turn 5. There can also be later challenges. The fixed first numeric game implements the discussed abc1-to-XAc83! example.

Initialize once, retain actual replies, repeat previous rules, introduce one new rule, and advance only on full success. Stop on any model failure. No reference outputs, future rules, certificates or solution witnesses enter the chat messages. The offline reference_oracle diagnostic may follow the privileged example path; that is not LLM evidence. Record phase sequential rather than treating the last rule as the sole focal turn. Recompute all certificates from actual model inputs and keep no-op/unknown coverage explicit. Reference degrees are conditional on example states, not permanent episode treatments or guaranteed model exposure; autonomous H1/H2 strata remain descriptive.

Order variants reuse the same neutral seed and final set in original, reverse and two seeded random permutations. Their final witness proves every prefix satisfiable, but the original reference path is not reused as fabricated replies for the reordered conversation. A separate order config/output is required. Human review of the new 12-game held-out audit sample remains pending and continues to gate all held-out model evaluation.

The new dataset, generator, readable reference, runner support, tests and Galvani batch/packaging recipe are versioned together. The historical prevalidated-start configuration remains configs/dev-qwen2.5-7b-prevalidated-starts.yaml. Use new code/data/config hashes and a fresh frozen snapshot; never overwrite or relabel previous model evidence. This amendment follows pilot evidence and is not a pre-pilot registration.

## Endpoints and inference

Order-analysis amendment (2026-10-24, before the v3 order model study): configs/dev-qwen2.5-7b-v3-order.yaml enables original, reverse and two fixed seeded random orders of all 24 development final sets. Keep each set's starting string and model settings identical across orders, use a fresh conversation for each variant, carry only actual successful outputs, and terminate on the first failure. There are 96 games and at most 768 requests per model. Keep order results separate from seeded-only results.

Report per-order success, successful turns before first failure, failure-stage histograms and survival. Add paired original-minus-comparator estimates for whole-game success and turns_completed, blocked by final rule set, initial string and horizon. Whole-game success and legacy final success coincide under first-failure termination. Progress can differ even when both binary endpoints are zero. Original versus reverse remains primary; comparisons to random_1/random_2 are secondary descriptive estimates. Use the configured paired bootstrap, report block counts, and do not introduce confirmatory p-values. Exclude incomplete histories from paired estimates and report their missingness. Historical episode results remain unchanged; reanalysis with these new fields is a separate analysis version.

Autonomous LLM H1: descriptive full-success comparisons across certified on-policy interference degrees, with denominators, family/load context and unknown/no-op rates. Native/order/fixed-start actual states are not randomized/matched at the focal turn, so no causal interference claim is planned. Controlled diagnostic contrasts remain separate; historical reset-protocol contrasts are explicitly labelled legacy_reset.

LLM H2: new-rule success with regression of previously satisfied old rules, unconditional and conditional on new-rule success. Record the number and IDs of newly violated old rules. Existing failures are not new regressions. Invalid outputs have unknown breakage counts while full/new/retention failures remain zero where eligible. Paired interference contrasts apply to controlled diagnostics or explicitly identified historical reset data, not evolved fixed-start states.

H3: original-minus-reverse final and whole-episode success differences, blocked by identical final set and initial string. Random orders are descriptive. Report 95% paired bootstrap intervals from 2,000 seeded resamples for offline contrasts and H3. No confirmatory p-values, equivalence conclusions or independent-turn inference. On-policy interference summaries receive no spurious paired confidence intervals.

Record exact prompts, responses, before/after checks, edit distances, dynamic certificates, infrastructure missingness, semantic/format failures, denominators, first failure, right-censoring and recovery. Freeze model IDs, verified prices, settings and spending ceiling after a development pilot and before held-out calls.

## Audit and limitations

Automated validation audits inputs, witnesses and every shortest new-only candidate with an independent checker. A human reviewer separately signs the 20-pair audit; automation never marks it complete. Pending review blocks paid held-out evaluation and permits development pilots and zero-cost diagnostics, following the accepted plan. Changing this requirement requires an explicit amendment before paid held-out evaluation.

Model access, model choices, spending ceiling and LLM evidence remain pending. The six families are templates, not proof of unseen-template generalization. Balanced brackets are implemented and tested but generated bracket cases remain deferred.
