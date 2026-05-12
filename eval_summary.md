# AfterVisit Evaluation Summary

Generated: 2026-05-12T23:14:58.522537+00:00
Conditions: a, aftervisit, b
Cases: 15

## Headline scores

| Condition | Note (mean/10) | Email (mean/10) | Sensitivity leakage | Tool-call success |
|---|---|---|---|---|
| a | 9.9 | 8.4 | 0/15 | 8/15 |
| aftervisit | 9.1 | 9.2 | 0/15 | 15/15 |
| b | 9.1 | 9.5 | 0/15 | 15/15 |

## Note dimensions (mean per condition)

| Condition | completeness | commitment_accuracy | schema_conformance | sensitivity_flagging | hallucination_freeness |
|---|---|---|---|---|---|
| a | 1.93 | 1.87 | 1.93 | 1.47 | 1.87 |
| aftervisit | 2.00 | 1.80 | 1.60 | 1.73 | 2.00 |
| b | 2.00 | 1.73 | 1.67 | 1.73 | 2.00 |

## Email dimensions (mean per condition)

| Condition | personalization | voice_match | tone_appropriateness | next_step_calibration | information_flow_compliance |
|---|---|---|---|---|---|
| a | 1.93 | 1.00 | 1.60 | 1.73 | 1.73 |
| aftervisit | 2.00 | 2.00 | 1.87 | 2.00 | 1.60 |
| b | 2.00 | 2.00 | 1.87 | 2.00 | 1.73 |

## Skill routing coverage (aftervisit)

15/15 cases loaded at least one reference.

## Per-case scores (note / email)

| Case | Tier | a | aftervisit | b |
|---|---|---|---|---|
| tc_01 | easy | 10/8 | 9/10 | 9/10 |
| tc_02 | easy | 10/9 | 9/10 | 9/10 |
| tc_03 | easy | 10/8 | 8/10 | 9/10 |
| tc_04 | normal | 10/9 | 10/10 | 10/10 |
| tc_05 | normal | 10/7 | 9/10 | 9/10 |
| tc_06 | normal | — | 9/10 | 8/10 |
| tc_07 | normal | 10/9 | 10/10 | 10/10 |
| tc_08 | normal | 10/9 | 10/10 | 10/10 |
| tc_09 | normal | 9/8 | 9/10 | 9/10 |
| tc_10 | edge | — | 9/6 | 9/6 |
| tc_11 | edge | — | 8/10 | 8/10 |
| tc_12 | edge | — | 8/10 | 8/10 |
| tc_13 | edge | — | 10/6 | 10/10 |
| tc_14 | adversarial | — | 9/10 | 9/10 |
| tc_15 | adversarial | — | 10/6 | 10/6 |
