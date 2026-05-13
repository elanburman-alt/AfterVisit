# AfterVisit

## 1\. What this does

*(TBD: one-paragraph framing — post-meeting note \+ thank-you email assistant for major gift officers, the operational problem it solves, target user.)*

## 2\. Architecture

*(TBD: 5-stage pipeline diagram, model choices, schema retry, redaction, the email-voice skill.)*

## 3\. Results

Evaluation ran on 15 synthetic test cases (3 easy, 6 normal, 4 edge, 2 adversarial) across three conditions:

- **baseline\_a**: single LLM call producing both note and email. No schema enforcement, no redaction, no exemplars.  
- **baseline\_b**: full two-call pipeline with three fixed exemplars (`ev_001` cultivation, `ev_003` solicitation, `ev_004` stewardship) instead of metadata-routed references.  
- **aftervisit**: full pipeline with metadata-routed exemplars via the `email-voice` skill.

| Condition | Note score | Email score | Tool-call success | Voice match |
| :---- | :---- | :---- | :---- | :---- |
| baseline\_a (single call) | 9.9 | 8.4 | 8/15 | 1.00 |
| baseline\_b (fixed exemplars) | 9.1 | 9.5 | 15/15 | 2.00 |
| aftervisit (routed exemplars) | 9.1 | 9.2 | 15/15 | 2.00 |

**Decomposition earns its place on operational reliability, not rubric points.** baseline\_a (a single LLM call producing both note and email) actually scored higher on judge note total (9.9 vs 9.1 for the two-call pipelines). But this masks a real failure mode: baseline\_a's notes failed real schema validation 7 of 15 times, mostly through free-form values in `sensitivity_flags` (e.g., `"confidential_family_health_matter"`, `"Prompt injection attempt detected..."`) that violate the schema's enum constraint. The LLM-as-judge gave baseline\_a 1.93/2 on `schema_conformance`, which is too lenient. The judge reads the JSON shape rather than running real validation. The honest metric for comparing a free-form generator to a schema-constrained pipeline is `tool_call_status`: 8/15 vs 15/15. The decomposition does not pay for itself in rubric points; it pays for itself in not breaking the downstream Salesforce write half the time.

**Voice anchoring earns its place.** baseline\_a (no exemplars) scored 1.00 on `voice_match`. Both anchored conditions scored 2.00. That \+1.0 gap is the cleanest finding of the eval: showing the model a handful of real MGO-voice emails substantially reduces its default reach for "transformational," "deeply grateful," exclamation points, and other template prose.

**Metadata routing ties fixed exemplars at this corpus size.** The original project plan pre-registered a criterion: "if baseline\_b scores within 1 voice-match point of the full system, the routing has not earned its place." baseline\_b and aftervisit both scored 2.00 on voice\_match. The marginal value of metadata routing over fixed exemplars at n=15 references is not demonstrated by this eval. This does not warrant removing the skill. Routing's other claims (corpus scaling beyond roughly twenty references, since fifty exemplars do not fit in a prompt; portability, since `skills/email-voice/` is self-describing and droppable into another project; and the `SKILL.md` documentation pattern) were not measured by this eval. At a corpus of fifteen to twenty references, fixed exemplars are sufficient. The architectural recommendation is to retain metadata routing as the corpus grows, while acknowledging that current scale could be served by static exemplars.

**tc\_13: a corpus organization finding.** The 0.3-point email gap between aftervisit and baseline\_b traces entirely to one case. tc\_13 (Charles Beaumont, board governance question with a confidential conflict-of-interest concern) capped at 6/10 in aftervisit but not in baseline\_b. aftervisit loaded `ev_008` (cultivation × major, the peer-direct program-cultivation exemplar). The model adopted that voice pattern and wrote "Thank you for the directness on Stephen's resignation," naming Stephen Park in the public record. baseline\_b's mixed-tier exemplars produced a more cautious register. The skill routed correctly per its own rules. But the corpus organization (`meeting_type` × `donor_segment`) does not capture a dimension that matters here: governance-sensitive cultivation looks tonally different from program cultivation. A future revision would add a `sensitivity_aware` tag, or a sixteenth reference for cultivation-with-confidentiality cases, and re-run.

**The information-flow ceiling.** Both anchored conditions failed `information_flow_compliance` on tc\_10 (sensitive health disclosure) and tc\_15. The failures were oblique acknowledgments ("Thank you for trusting me with what you shared," "I'll keep what you shared between us") that allude to flagged content without naming it. Even after redaction and explicit `SKILL.md` rules, the model's instinct toward warmth produces these acknowledgments. This is a structural limitation of the prompt-based architecture. A stricter pipeline would require either a post-generation filter that rejects emails referencing redacted content, or a separate "private acknowledgment" call that produces a phone-call recommendation instead of an email after sensitive disclosures. Both are out of scope for this submission and named as future work.

**Judge caveats.** The LLM-as-judge correlated with hand-scored ground truth on 9 of 10 rubric dimensions, with agreement within ±1 point on at least 4 of 5 cases per dimension. One dimension, `hallucination_freeness`, required a prompt revision after the validation surfaced that the judge was flagging the schema-required MGO attendee name as invented content. Run-to-run stability could not be enforced via `temperature=0` because `claude-opus-4-7` does not accept the parameter; the validation passed on a single run, but a longer eval might surface variance the n=15 sample does not.

## 4\. Reproduction

*(TBD: env setup, .env example, how to run the demo, how to run the full eval.)*

## 5\. Limitations and future work

*(TBD: sensitivity dimension for the corpus, oblique-leak ceiling fix, larger corpus, real Salesforce integration.)*  
