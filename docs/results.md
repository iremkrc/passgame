# Results

## Overall Performance

We analysed 19 completed evaluation runs across the 11 model variants. Each run included 96 conversations, for a total of 1,824 conversations and 10,919 attempted responses. Every game either passed all eight turns or ended after a model failure.

**Table 1. Whole-game success and mean successful turns without thinking, across all four rule orders. A game passed only if all eight turns succeeded.**

| Model | Games passed | Mean successful turns |
| --- | ---: | ---: |
| Qwen2.5-7B | 0/96 | 2.00 |
| Qwen2.5-14B | 1/96 | 2.96 |
| Qwen2.5-32B | 5/96 | 3.82 |
| Qwen3.5-9B | 10/96 | 3.49 |
| Qwen3.5-27B | 23/96 | 5.28 |
| Qwen3.6-27B | 23/96 | 5.31 |
| Qwen3.6-35B-A3B | 27/96 | 4.81 |
| Gemma 4-12B | 22/96 | 4.49 |
| Gemma 4-26B-A4B | 27/96 | 5.11 |
| Gemma 4-31B | 31/96 | 5.52 |
| DeepSeek-V4.1-Flash | 24/96 | 4.96 |

**Table 2. Whole-game success and mean successful turns with thinking at a 4,096-token limit, across all four rule orders.** 

| Model | Token limit | Games passed | Mean successful turns |
| --- | ---: | ---: | ---: |
| Qwen3.6-27B | 4,096 | 70/96 | 5.97 |
| Qwen3.6-35B-A3B | 4,096 | 74/96 | 6.91 |
| Gemma 4-12B | 4,096 | 53/96 | 5.99 |
| Gemma 4-31B | 4,096 | 91/96 | 7.84 |
| DeepSeek-V4.1-Flash | 4,096 | 96/96 | 8.00 |

The token limit in Table 2 counts all completion tokens, including reasoning.

DeepSeek-V4.1-Flash with thinking passed all 96 games. Gemma 31B with thinking and a 4,096-token limit passed 91. Qwen2.5-7B passed no complete games; the 14B and 32B models passed one and five, respectively. They completed an average of 2.00, 2.96, and 3.82 successful turns.

Qwen2.5-7B met the new rule in 225 of its 288 responses. Of those 225 responses, 192 satisfied all active rules. The remaining 33 met the new rule but broke at least one earlier rule. Examples of a failed and a successful game are shown in [the protocol example](protocol.md#example).

## Effect of Increasing the Token Limit

Some thinking responses reached the token limit before returning a valid final answer. At 4,096 tokens, this accounted for all 26 failures in Qwen3.6-27B, 41 of 43 failures in Gemma 12B, and 12 of 22 failures in Qwen3.6-35B-A3B. We therefore increased the limit to 16,384 tokens and reran these models on the same 96 game-and-order combinations. This limit was shared between reasoning and the final answer.

**Table 3. Thinking runs before and after increasing the token limit.** Each run covered 96 games. Token-limit failures ended at the completion limit without a valid final answer; other failures were rule or domain violations.

| Model | Token limit | Games passed | Mean successful turns | Token-limit failures | Other failures |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.6-27B | 4,096 | 70/96 | 5.97 | 26 | 0 |
| Qwen3.6-27B | 16,384 | 77/96 | 6.67 | 19 | 0 |
| Qwen3.6-35B-A3B | 4,096 | 74/96 | 6.91 | 12 | 10 |
| Qwen3.6-35B-A3B | 16,384 | 78/96 | 7.12 | 10 | 8 |
| Gemma 4-12B | 4,096 | 53/96 | 5.99 | 41 | 2 |
| Gemma 4-12B | 16,384 | 75/96 | 6.89 | 20 | 1 |

All three models evaluated at both limits passed more games at the larger limit. Gemma 12B showed the largest increase, from 53 to 75 games. Qwen3.6-27B improved from 70 to 77 games, and Qwen3.6-35B-A3B improved from 74 to 78.

Some games still ended at the 16,384-token limit without a valid final answer. For Qwen3.6-27B, 25 of the 26 initial failures and all 19 failures at the larger limit had empty final answers. For Qwen3.6-35B-A3B, token-limit failures decreased from 12 to 10, all with empty final answers. Another eight games at the larger limit failed because of rule or domain violations. Token-limit failures counted as game failures under the response protocol.



## Rule-Order Effects

We compared all four rule orders in the 11 runs without thinking. Each order used the same 24 base games. The two random orders were fixed for each base game and shared across models.

**Table 4. Mean successful turns per game in each rule order, without thinking.** Means include all 24 games in each order; the maximum is eight turns.

| Model | Original | Reverse | Random 1 | Random 2 |
| --- | ---: | ---: | ---: | ---: |
| Qwen2.5-7B | 1.92 | 2.42 | 1.71 | 1.96 |
| Qwen2.5-14B | 2.58 | 3.29 | 3.08 | 2.88 |
| Qwen2.5-32B | 3.83 | 3.75 | 3.58 | 4.12 |
| Qwen3.5-9B | 2.12 | 4.58 | 3.46 | 3.79 |
| Qwen3.5-27B | 4.58 | 6.54 | 4.92 | 5.08 |
| Qwen3.6-27B | 5.42 | 6.17 | 4.46 | 5.21 |
| Qwen3.6-35B-A3B | 4.96 | 5.29 | 4.62 | 4.38 |
| Gemma 4-12B | 4.17 | 4.00 | 4.75 | 5.04 |
| Gemma 4-26B-A4B | 5.00 | 4.67 | 5.62 | 5.17 |
| Gemma 4-31B | 5.29 | 5.88 | 5.62 | 5.29 |
| DeepSeek-V4.1-Flash | 4.12 | 5.79 | 4.83 | 5.08 |

Reverse order gave the highest observed mean number of successful turns for eight of the 11 models. Qwen2.5-32B and Gemma 12B had their highest means in Random 2, while Gemma 26B-A4B had its highest mean in Random 1.

In the paired comparison with original order, Qwen3.5-9B completed 2.46 more successful turns per game in reverse order. The gains were 1.96 turns for Qwen3.5-27B and 1.67 for DeepSeek. For the other eight models, the comparison did not clearly favour either original or reverse order.
