---
name: email-voice-mgo
description: Use this skill when drafting a thank-you email from a major gift officer to a donor after a face-to-face visit. Provides voice exemplars anchored on meeting type and donor segment. Match the rhythm, opener pattern, and closing of the loaded references without copying their specifics.
license: Proprietary
---

# MGO Email Voice Anchoring

Reference exemplars of thank-you emails written by a specific major gift officer. Use them to anchor voice when drafting a new thank-you. The references live in `references/`.

## When to use this skill
Drafting a post-visit thank-you email. Not for solicitation letters, event invitations, or proposal cover notes.

## Inputs you need
- `meeting_type`: one of `discovery`, `cultivation`, `solicitation`, `stewardship`, `decline`
- `donor_segment`: one of `prospect`, `new_donor`, `mid_5k_10k`, `major_15k_50k`, `lead_100k_plus`

## How to pick references
1. Filter `references/` to files whose frontmatter `meeting_type` exactly matches the visit.
2. Within that pool, prefer files whose `donor_segment` exactly matches the donor. If fewer than 3 match, expand to adjacent segments:
   - `prospect` ↔ `new_donor`
   - `mid_5k_10k` ↔ `new_donor`
   - `major_15k_50k` ↔ `lead_100k_plus`
3. Load up to 3 references. If 1 or 2 match, load what exists. If zero match, proceed without exemplars and use the hard rules below.
4. When more than 3 candidates remain after filtering, prefer files whose `tags` overlap with the meeting's themes (e.g. `grateful_patient`, `board_intro`, `tour_followup`).

**Sensitivity-aware preference (v1.6).** When the caller indicates that the case involves flagged sensitivity content (i.e. the note's `sensitivity_flags` list is non-empty), references with `sensitivity_aware: true` in their frontmatter are returned first within the matching `meeting_type` group, ahead of standard references. This routes deferential, phone-pivot voice patterns to cases where the underlying topic must not be fully addressed in writing. Regular references for the same `meeting_type` are still included as supporting context, just not as the lead exemplar.

## How to use what you load
- Match sentence rhythm, opener pattern, and closing style.
- Do NOT import donor names, dollar amounts, or specifics from the references — they are voice anchors only.
- If references disagree with each other, prefer the one whose `donor_segment` most closely matches the current donor.

## Hard rules (apply to every email)
- No exclamation points unless a reference uses them.
- After a declined ask: warm and restrained, never "if circumstances change" or any soft re-ask.
- Never reference health, family hardship, or financial detail — the input bullets are pre-redacted; if you see `[redacted: ...]`, do not speculate about what was redacted.
- Close with a concrete next step that is in the bullets, not invented.

## References
Load by file path. The full list of available references is the contents of `references/*.md`. Each file's frontmatter describes when it applies.
