# AfterVisit — Build Plan for Claude Code (v3)

> **v3 update.** This revision incorporates Prof. Ju's feedback: *"Email voice anchoring may be better done with a skill where you have examples of email voices in `references/`."* The runtime retrieval layer (sentence-transformers + cosine ranking + dual-key filter) is replaced by a proper Anthropic-style skill — `skills/email-voice/SKILL.md` plus a `references/` folder. Routing logic lives in the skill instructions; the Python loader is a thin metadata filter. The result is simpler, more portable, and directly answers the assignment's "skill or tool" deliverable option.

Post-meeting assistant for major gift officers. Two LLM calls (note + email), a voice-anchoring **skill** with exemplar emails in `references/`, mock Salesforce tool call with human approval gate, Streamlit UI, evaluation harness with two baselines.

**Build philosophy: end-to-end happy path first, then robustness, then evaluation, then submission deliverables.** Resist the urge to build the eval harness before you have a working pipeline. The MVP is small enough that you can stand it up in one sitting.

---

## How this maps to the assignment

| Assignment requirement                          | Where it lives in this build                                              |
|-------------------------------------------------|---------------------------------------------------------------------------|
| One specific user, one specific workflow        | Major gift officer at a mid-size health-system foundation; post-visit close-out (note + thank-you) |
| Usable app/skill/tool a grader can run          | Streamlit app + `src/demo.py` CLI + a portable voice-anchoring **skill** at `skills/email-voice/` |
| "Skill" as an acceptable artifact form          | `skills/email-voice/` is a self-contained Anthropic-format skill, usable by Claude Code / Agent SDK or by our own loader |
| Why GenAI fits                                  | README §2 — bullets-to-prose in a person's voice is not a template problem |
| Comparison against a simpler baseline           | Baseline A (single prompt-only LLM call) is the assignment's required baseline; Baseline B (decomposed with static exemplars) is the optional second one that tests the skill's routing logic |
| Realistic example set, not one screenshot       | 15 hand-built synthetic test cases × 3 conditions, scored on two rubrics  |
| What worked, what failed, where humans stay     | README §3, populated from `eval_summary.md` after the run                 |
| No secrets / PII / private donor data           | All data synthetic; `.env.example` checked in; `.env` gitignored          |
| README with the four required sections          | Phase 5.1 — scaffold provided verbatim                                    |
| Setup so a grader can install and run           | Phase 5.2 — one `pip install -r`, one `streamlit run`, one `python -m src.demo` |
| Lightning presentation (2-3 min, slides)        | Phase 5.4 — five-slide outline                                            |
| Snapshot artifact (screenshots / sample output) | Phase 5.3 — `docs/screenshots/` + `data/sample_outputs/` committed to repo |

---

## Defending complexity against the assignment's simplicity guard

The assignment is explicit: *"Do not use RAG, agents, or multiple models unless they actually help the workflow."* AfterVisit uses skill-based exemplar routing, mixes two model tiers, and decomposes into two calls. Each choice is **measured, not assumed**:

- **Two calls (note vs email).** Baseline A is a single prompt-only call producing both. If A scores within 1 rubric point of the full system, the decomposition has not earned its place and the README will say so.
- **Voice-anchoring skill with metadata routing.** Baseline B is the full decomposed pipeline with 3 *static* exemplars instead of skill-routed ones. If B scores within 1 voice-match point of the full system, the routing has not earned its place and the README will recommend dropping it.
- **Two model tiers (Haiku for note, Sonnet/Opus for email).** A 5-case Haiku-vs-Sonnet comparison on the note runs in Phase 4. If Haiku clears schema conformance and completeness, the note stays on Haiku. The "two models" is per-task selection, not parallel ensembles.

Note that v3 explicitly removes embedding-based retrieval. For 15-20 exemplars with structured metadata, exact-match filtering with adjacency fallback is sufficient — cosine similarity over a small corpus adds a dependency without changing the answer. This is the simplicity rule actually applied, not just talked about.

---

## Phase 0 — Setup

### 0.1 Project structure

```
aftervisit/
├── .env                                # ANTHROPIC_API_KEY=... — gitignored
├── .env.example                        # Documented placeholder for graders
├── .gitignore                          # .env, __pycache__/, .venv/, data/activity_log.json
├── LICENSE                             # MIT, optional
├── requirements.txt
├── README.md                           # The graded artifact (Phase 5.1)
├── app.py                              # Streamlit entry point
├── skills/
│   └── email-voice/                    # PORTABLE VOICE-ANCHORING SKILL
│       ├── SKILL.md                    # Instructions: when to use, how to route, hard rules
│       ├── README.md                   # How to use the skill outside AfterVisit (Claude Code, Agent SDK)
│       └── references/                 # One .md per exemplar email
│           ├── 01_cultivation_mid_heart.md
│           ├── 02_discovery_prospect_boardintro.md
│           └── ...
├── data/
│   ├── test_cases.json                 # 15 synthetic meetings for evaluation
│   ├── activity_log.json               # Mock Salesforce write target — gitignored
│   └── sample_outputs/                 # Committed: pre-run outputs from all 15 cases
│       ├── tc_01_aftervisit.json
│       ├── tc_01_baseline_a.json
│       └── ...
├── docs/
│   └── screenshots/                    # 3-4 PNGs of the Streamlit UI for the README
├── prompts/
│   ├── note_system.md
│   ├── email_system.md
│   ├── judge_note.md
│   └── judge_email.md
├── schemas/
│   └── activity_note.schema.json       # JSON Schema 7
├── src/
│   ├── __init__.py
│   ├── config.py                       # Loads .env, model names, paths
│   ├── skill_loader.py                 # Loads SKILL.md + filters references by metadata
│   ├── redact.py                       # Deterministic sensitivity redaction
│   ├── generate.py                     # Two-call pipeline + Baseline A + Baseline B
│   ├── mock_salesforce.py              # post_activity(note) -> {id, status, errors}
│   ├── evaluate.py                     # Judge + scoring harness
│   └── demo.py                         # One-shot canned run for graders
├── presentation/
│   └── AfterVisit.pptx                 # 5 slides, 2-3 min talk
├── eval_results.csv                    # Generated by `python -m src.evaluate`
├── eval_summary.md                     # Generated by `python -m src.evaluate`
└── tests/
    └── test_skill_loader.py            # Metadata routing unit tests
```

### 0.2 Dependencies (`requirements.txt`)

```
anthropic>=0.40.0
streamlit>=1.40
python-dotenv>=1.0
python-frontmatter>=1.1
jsonschema>=4.23
pyyaml>=6.0
pandas>=2.2                     # eval CSV / summary
```

**No embedding library, no vector math.** The skill routes by metadata, not similarity. For 15-20 exemplars this is the right choice; cosine similarity over a corpus this small doesn't earn its dependency.

### 0.3 Models

In `src/config.py`:

```python
MODEL_NOTE  = "claude-haiku-4-5-20251001"   # structured extraction; cheap, fast
MODEL_EMAIL = "claude-opus-4-7"             # voice nuance; or claude-sonnet-4-6 if cost-tight
MODEL_JUDGE = "claude-opus-4-7"             # evaluator
```

Start the note on Haiku; bump to Sonnet only if Phase 4's comparison shows it can't clear the conformance bar. The email is voice-sensitive — keep it on the stronger tier.

### 0.4 Repo hygiene (do this in the first commit)

- `.env.example` checked in with `ANTHROPIC_API_KEY=sk-ant-...` as a placeholder. Real `.env` gitignored.
- `.gitignore` covers `.env`, `__pycache__/`, `.venv/`, `*.pyc`, `data/activity_log.json` (the mock write target — starts empty and grows during demo).
- No real donor data anywhere in the repo. Synthetic only. State this in the README.
- The committed `data/sample_outputs/` directory lets a grader read results even without an API key.

---

## Phase 1 — The voice-anchoring skill (do this FIRST)

This is the mechanism Prof. Ju flagged. The skill follows Anthropic's skill convention: a `SKILL.md` with frontmatter and operating instructions, plus a `references/` folder of files the skill loads on demand. The "retrieval" logic is written as instructions in `SKILL.md` rather than as Python code — the routing rules are agent-readable, human-readable, and portable.

### 1.1 `skills/email-voice/SKILL.md`

```markdown
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
```

The `description` field in the frontmatter is what makes the skill discoverable to an agent — write it in the "Use this skill when X" form Anthropic recommends.

### 1.2 Sample reference file format

`skills/email-voice/references/01_cultivation_mid_heart.md`:

```markdown
---
id: ev_001
meeting_type: cultivation
donor_segment: mid_5k_10k
program: heart_institute
tone: warm_direct
tags: [grateful_patient, family_connection, tour_followup]
notes: |
  Voice anchors: no exclamation points; names specific things the donor said;
  closes with a concrete next step, not a vague "let's stay in touch."
---
Dear Margaret,

Thank you for making time on Tuesday — and more than that, thank you for telling me what your mother's care at the Heart Institute meant to your family. The way you described Dr. Chen's bedside manner is exactly the kind of perspective we don't get in a foundation report, and I'll be carrying it with me into next month's program review.

I heard your question about cardiologist recruitment loud and clear. Let me come back to you in the next two weeks with a clearer picture of where we are on the search and what philanthropic support is actually unlocking versus what the operating budget covers. I'd rather give you the real answer than a clean one.

For the tour in May — I'll have Sarah reach out tomorrow with three Wednesday options. We can do the full Heart Institute walk-through in about ninety minutes, including time with one of the interventional fellows if you'd like.

Congratulations again to Annie on starting med school. Tell her if she ever wants to shadow on the cardiac side, the door is open.

Warmly,
Elan
```

### 1.3 Seed corpus

Ship **6 well-crafted reference emails** covering the meeting-type × donor-segment cells you actually care about. Grow to 15-20 as you iterate. Cells worth covering early:

| Meeting type   | Donor segment       | Why |
|----------------|---------------------|-----|
| cultivation    | mid_5k_10k          | most common case |
| discovery      | prospect            | board-intro pattern |
| solicitation   | major_15k_50k       | ask language + spouse-conversation pattern |
| stewardship    | major_15k_50k       | post-event, includes sensitive-disclosure restraint |
| decline        | major_15k_50k       | warm-restrained, no "if circumstances change" |
| stewardship    | lead_100k_plus      | quarterly-cadence pattern |

Write these in **your actual voice.** That's the whole point — the system anchors on you, not on a generic MGO. If the voice in the references is bland, the output will be bland.

### 1.4 Skill loader (`src/skill_loader.py`)

Thin Python that does the metadata routing the SKILL.md describes. Reads SKILL.md once, filters references/, returns selected files. ~40 lines.

```python
class Reference:
    id: str
    meeting_type: str
    donor_segment: str
    program: str | None
    tags: list[str]
    body: str
    path: Path

class EmailVoiceSkill:
    def __init__(self, skill_dir: Path):
        self.skill_md = (skill_dir / "SKILL.md").read_text()
        self.references = self._load_refs(skill_dir / "references")

    def select(self, meeting_type: str, donor_segment: str, k: int = 3) -> list[Reference]:
        """
        Implements the routing rules from SKILL.md:
        1. Hard filter on meeting_type (exact match).
        2. Prefer exact donor_segment; expand to adjacent segments if pool < k.
        3. Return up to k. Empty list is acceptable — the email prompt degrades gracefully.
        """

    def voice_rules(self) -> str:
        """Returns the 'How to use what you load' + 'Hard rules' sections of SKILL.md
        for inclusion in the email system prompt."""
```

**Build behavior:**
- Adjacency map is defined once in the loader, mirroring SKILL.md exactly. The two must stay in sync; add a unit test that asserts the adjacency rules in SKILL.md and in `skill_loader.py` agree.
- No caching needed. 20 references × ~500 words is trivial to read on every request.
- The skill is also usable directly from Claude Code or the Agent SDK — point those tools at `skills/email-voice/` and they read SKILL.md natively. The Python loader is just AfterVisit's runtime way of using it.

### 1.5 Tests (`tests/test_skill_loader.py`)

Verify at minimum:
- Hard filter excludes mismatched meeting types.
- Adjacency fallback fires when the strict donor_segment pool is empty.
- Empty result returns `[]` rather than throwing.
- Same query → same ordering (deterministic).
- The adjacency map in code matches what SKILL.md documents (string-search the SKILL.md text for the documented adjacencies).

### 1.6 Skill `README.md` (`skills/email-voice/README.md`)

A short README **inside the skill folder** so the skill is portable and self-describing when used outside AfterVisit. Cover: what the skill does, how to add a new reference, how to invoke it from Claude Code (drop the folder into your project's skills directory), how to invoke it from the Agent SDK. Three or four paragraphs is enough.

---

## Phase 2 — Schema, prompts, two-call pipeline

### 2.1 Schema (`schemas/activity_note.schema.json`)

JSON Schema 7. Required fields from the project plan:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["subject", "date", "type", "attendees", "summary", "commitments", "next_steps", "sensitivity_flags"],
  "properties": {
    "subject":            { "type": "string", "maxLength": 120 },
    "date":               { "type": "string", "format": "date" },
    "type":               { "enum": ["discovery", "cultivation", "solicitation", "stewardship", "decline"] },
    "attendees":          { "type": "array", "items": { "type": "string" }, "minItems": 1 },
    "summary":            { "type": "string", "minLength": 40 },
    "commitments":        { "type": "array", "items": { "type": "string" } },
    "next_steps":         { "type": "array", "items": { "type": "string" }, "minItems": 1 },
    "solicitation_amount":{ "type": ["number", "null"] },
    "commitment_status":  { "enum": ["none", "verbal_yes", "verbal_no", "written_pledge", "received", "deferred", null] },
    "sensitivity_flags":  { "type": "array", "items": { "enum": ["health", "family", "financial", "board_dynamics", "donor_relationship", "other"] } }
  },
  "additionalProperties": false
}
```

### 2.2 Note prompt (`prompts/note_system.md`)

```
You are a development-operations assistant generating a Salesforce activity note from a major gift officer's post-meeting bullets.

OUTPUT CONTRACT
Return a single JSON object matching the schema below. No prose, no markdown fences, no preamble.

<schema>
{schema_json}
</schema>

RULES
- Capture every bullet. If a fact is not in the bullets, do not invent it.
- sensitivity_flags MUST be set whenever the bullets mention health, family hardship, financial detail, or board dynamics — even if the MGO did not flag it.
- commitment_status reflects the donor's stated position. "verbal_no" only when explicit; default "none".
- next_steps must be concrete enough to assign and date.

INPUT
<donor_context>{donor_context}</donor_context>
<meeting_type>{meeting_type}</meeting_type>
<bullets>
{bullets}
</bullets>
```

The XML-tagged input is your injection defense — the system prompt tells the model to treat tagged content as data.

### 2.3 Email prompt (`prompts/email_system.md`)

The email prompt is composed at runtime from two parts: (a) the voice rules from `SKILL.md`, and (b) the selected reference bodies. Template:

```
You are drafting a thank-you email in the voice of a specific major gift officer.

{voice_rules_from_skill_md}

VOICE EXEMPLARS (do not quote from these)
<exemplars>
{loaded_reference_bodies}
</exemplars>

INPUT
<donor>{donor_name}</donor>
<meeting_type>{meeting_type}</meeting_type>
<bullets>
{redacted_bullets}
</bullets>

Return the email body only. No subject line. No signature block beyond the MGO's first name.
```

This way the SKILL.md is the **single source of truth** for the voice rules. Edit SKILL.md, the email prompt updates next call.

### 2.4 Redaction (`src/redact.py`)

Pre-call deterministic pass — not an LLM call. Regex + keyword list for: health terms ("cancer", "stroke", "diagnosis", "treatment", "ICU", "hospice"...), family hardship ("divorce", "death", "passed", "lost"), financial detail ("bankruptcy", "layoff", "lost job"). Replace matched spans with `[redacted: health]`, `[redacted: family]`, etc. Keep a copy of the unredacted bullets for the note call.

Regex is crude on purpose — it's a hard floor, and the email prompt's information-flow rules (loaded from SKILL.md) are the second layer.

### 2.5 Pipeline (`src/generate.py`)

```python
def run(bullets: list[str], donor_name: str, donor_segment: str,
        meeting_type: str) -> dict:
    redacted   = redact(bullets)
    note       = generate_note(bullets, donor_name, meeting_type)        # full bullets
    references = skill.select(meeting_type, donor_segment, k=3)
    email      = generate_email(redacted, donor_name, meeting_type,
                                voice_rules=skill.voice_rules(),
                                references=references)
    return {"note": note, "email": email,
            "references_used": [r.id for r in references]}
```

Schema validation on the note: validate, and on failure issue **one** retry with the validation error appended to the system prompt. After that, surface the error. Do not silently invent fields.

### 2.6 Mock Salesforce (`src/mock_salesforce.py`)

```python
def post_activity(note: dict) -> dict:
    # validate against schema
    # if valid: append {id: uuid, posted_at: now, note: note} to data/activity_log.json, return {"id": ..., "status": "ok"}
    # if invalid: return {"status": "error", "errors": [...jsonschema errors...]}
```

A real Salesforce REST integration is gated behind an env flag (`USE_REAL_SALESFORCE=true`) and is **explicitly out of scope** for the submission. Say so in the README.

---

## Phase 3 — Streamlit UI (`app.py`)

Layout:

```
┌─────────────────────────────────────────────────────────────┐
│  AfterVisit                                                 │
├─────────────────────────────────────────────────────────────┤
│  Donor name:   [_______________]                            │
│  Donor segment:[v]   Meeting type: [v]                      │
│  Bullets (one per line):                                    │
│  [                                                  ]       │
│  [ ] I disclosed sensitive content                          │
│                                  [Generate]                 │
├──────────────────────────┬──────────────────────────────────┤
│  Salesforce Note         │  Thank-you Email                 │
│  (JSON, pretty-printed)  │  (markdown)                      │
│                          │                                  │
│  [Edit] [Reject]         │  Refs used: ev_001, ev_003       │
│  [ ] I've read the note  │  [Edit]                          │
│  [Approve and File] ←    │  [Copy]                          │
│  (disabled until checked)│                                  │
├──────────────────────────┴──────────────────────────────────┤
│  Recent activity log (last 5 filed)                         │
└─────────────────────────────────────────────────────────────┘
```

**Approval-fatigue control.** Simplest implementation: a "I've read the note" checkbox at the bottom of the note panel. The Approve button is disabled until that's checked. Two lines of code, satisfies the constraint.

**Sensitivity flags surfaced as colored chips** at the top of the note panel. If `sensitivity_flags` is non-empty AND the email body contains a flagged keyword, show a warning banner above the email: "This email may reference flagged content — review before copying."

**Show which references were used** under the email panel — a small line with the reference IDs. Makes the skill visible to the MGO and to the grader.

---

## Phase 4 — Test cases, baselines, evaluation

### 4.1 Test cases (`data/test_cases.json`)

15 cases per project plan §5: 3 easy, 6 normal, 4 edge, 2 adversarial. Each case:

```json
{
  "id": "tc_07",
  "tier": "edge",
  "donor_name": "...",
  "donor_segment": "...",
  "meeting_type": "stewardship",
  "bullets": ["...", "...", "..."],
  "expected_sensitivity_flags": ["health", "family"],
  "expected_commitments": [],
  "notes_for_human_grader": "Email must not reference the spouse's diagnosis."
}
```

### 4.2 Baselines (`src/generate.py`)

- `baseline_a(case)` — one call, one prompt, "produce a note and an email from these bullets." No schema, no skill, no redaction. **This is the assignment's required baseline — the simpler-than-yours comparison.**
- `baseline_b(case)` — full two-call pipeline but with **3 fixed exemplars** in the email prompt instead of skill-routed ones. The 3 fixed exemplars span meeting types (e.g. one cultivation, one solicitation, one stewardship). Isolates the value of the skill's metadata routing.
- `aftervisit(case)` — the full pipeline with skill-routed references.

### 4.3 Judge (`prompts/judge_note.md`, `prompts/judge_email.md`)

Two rubrics from the project plan, scoring 0–2 per dimension, totals out of 10. The hallucination-freeness and information-flow dimensions are binary cap rules (any failure caps total at 6) — implement that as post-processing on the judge output, not as a judge instruction.

Validate the judge on 5 cases against your hand scores before running it on all 15. Document the agreement check in `eval_summary.md`.

### 4.4 Eval harness (`src/evaluate.py`)

```
python -m src.evaluate --conditions a,b,aftervisit --cases data/test_cases.json --out eval_results.csv
```

Writes `eval_results.csv` (raw scores) and `eval_summary.md` (mean by condition, per-dimension breakdowns, per-case deltas, **skill routing coverage** — how many of the 15 cases had ≥1 reference loaded — and model-tier comparison). The summary feeds into the README §3 results section.

Note: with metadata routing replacing embedding similarity, "retrieval precision" is no longer the right metric. Coverage (did the skill find any references at all) plus the voice-match rubric dimension (does the email read like the MGO) together cover what precision@3 used to measure.

---

## Phase 5 — Submission deliverables

This phase exists for the grader, not for you. Allocate real time for it.

### 5.1 README scaffold (`README.md`)

Use these exact section headers. Each maps to one of the four pieces the assignment requires.

```markdown
# AfterVisit
*Post-meeting assistant for major gift officers — turns 5 bullets into an approved Salesforce activity note and a personalized thank-you email. Ships with a portable voice-anchoring skill.*

![demo](docs/screenshots/01_form.png)

## 1. Context, user, and problem
- **User.** Major gift officer (MGO) at a mid-sized nonprofit health-system foundation. Carries 10-15 donor visits per month across a portfolio of 100-150 donors.
- **Workflow.** Every donor visit is supposed to produce two artifacts within 24-48 hours: a Salesforce activity note and a thank-you email. Today this takes 20-30 minutes per visit if it happens at all — and it often doesn't. Contact-report compliance is a chronic weak point in development operations.
- **Why it matters.** For a 12-person MGO team at 12 visits/month, moving from 75% to 95% on-time completion adds ~30 usable records monthly, with compounding effects on CRM data quality, donor handoffs, and director-level coaching visibility. Personalized thank-yous within 48 hours correlate with donor retention; generic or late emails quietly erode trust.

## 2. Solution and design
- **What it is.** A Streamlit app, plus a portable voice-anchoring **skill** (`skills/email-voice/`) usable independently by Claude Code or the Agent SDK. The MGO enters 3-5 bullets, donor name and segment, and meeting type. The app returns a draft Salesforce note (JSON, schema-validated) and a draft thank-you email anchored on the MGO's past email voice via the skill. The MGO reviews, approves the note, and files it to a mock Salesforce endpoint with one click. The email is copied to the clipboard.
- **Why GenAI.** Bullets-to-prose in a specific MGO's voice is a language-generation problem. Templates produce template-shaped emails. A donor reading "Your story about why your mother's cardiac care shaped your commitment to the Heart Institute" can tell the difference.
- **Architecture.**
  1. Deterministic redaction strips health / family / financial mentions from a copy of the bullets.
  2. Note call (Claude Haiku 4.5, temp 0.2) produces JSON conforming to the activity-note schema.
  3. The voice-anchoring skill (`skills/email-voice/`) routes by metadata — meeting_type and donor_segment, with an adjacency fallback documented in its `SKILL.md` — and loads up to 3 reference emails.
  4. Email call (Claude Opus 4.7, temp 0.5) drafts the thank-you using the redacted bullets, the loaded references, and the voice rules pulled directly from `SKILL.md`.
  5. Approval gate: the MGO must check "I've read the note" before the file-to-Salesforce button activates. The mock endpoint writes to `data/activity_log.json` and returns an activity ID.
- **Key design choices** (each tested in evaluation, not assumed):
  - **Two calls instead of one.** Note is structured extraction at low temperature; email is voice at higher temperature. Same prompt for both produces mush. Baseline A tests this.
  - **Voice anchoring as a skill, not a vector DB.** The skill follows Anthropic's `SKILL.md` + `references/` convention. Routing is metadata-driven (meeting_type + donor_segment, adjacency fallback) and lives in `SKILL.md` as agent-readable instructions. No embeddings, no cosine math. Baseline B tests whether routing earns its place against a static-exemplar control.
  - **Two model tiers.** Haiku for the structured note, Opus for the voice email. Phase 4 compares Haiku vs Sonnet 4.6 on the note specifically.
  - **Hard separation of note and email.** The email generator never sees unredacted sensitive content. This is the information-flow boundary that matters most in health-system philanthropy.
  - **Approval gate is a hard boundary.** No autonomous tool calls. No auto-send on emails. Copy-to-clipboard by design.

## 3. Evaluation and results
- **Test set.** 15 synthetic donor meetings — 3 easy, 6 normal, 4 edge (sensitive disclosure, declined ask, on-the-spot commitment, board complication), 2 adversarial (prompt-injection in bullets).
- **Baselines.**
  - **Baseline A** — single prompt-only LLM call producing both artifacts. The simplest plausible system. *(This is the assignment's required baseline.)*
  - **Baseline B** — full two-call pipeline with 3 fixed exemplars instead of skill-routed ones. Tests whether the skill's metadata routing earns its complexity.
- **Rubrics.** Two 10-point rubrics (note, email) scored by Claude Opus 4.7 as judge, validated against my hand scores on 5 cases (agreement within ±1 point per dimension on N of 5 — see `eval_summary.md`). Hallucination-freeness on the note and information-flow compliance on the email are binary cap rules: any failure caps the total at 6/10.
- **Headline results.** *(filled in after the eval run)*

  | Condition       | Note (mean / 10) | Email (mean / 10) | Sensitivity leakage | Tool-call success |
  |-----------------|------------------|-------------------|---------------------|-------------------|
  | Baseline A      | x.x              | x.x               | x / 4 edge cases    | n/a               |
  | Baseline B      | x.x              | x.x               | x / 4 edge cases    | x / 15            |
  | AfterVisit      | x.x              | x.x               | x / 4 edge cases    | x / 15            |

- **What worked.** *(filled in)*
- **What failed.** *(filled in — at minimum reproduce one anticipated failure from the project plan; e.g., post-decline tone or unflagged sensitive content)*
- **Where a human stays involved.** The approval gate is non-optional. Every note is reviewed before filing; every email is reviewed before sending. AfterVisit is a draft-and-approve assistant, never an autonomous one.

## 4. Artifact snapshot
![note + email side by side](docs/screenshots/02_outputs.png)
![approval + activity log](docs/screenshots/03_filed.png)

Pre-run outputs for all 15 test cases are committed under `data/sample_outputs/` so you can read the results without running the system or spending API tokens.

## Setup and usage
**Prereqs.** Python 3.11+. An Anthropic API key.

```bash
git clone <repo>
cd aftervisit
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                    # then paste your ANTHROPIC_API_KEY into .env
```

**Run the interactive app:**
```bash
streamlit run app.py
```

**Run one canned example end-to-end (no UI):**
```bash
python -m src.demo --case tc_01
# Prints the note JSON, the email body, the references loaded, and a mock Salesforce activity ID.
```

**Reproduce the evaluation:**
```bash
python -m src.evaluate --conditions a,b,aftervisit --cases data/test_cases.json
# Writes eval_results.csv and eval_summary.md.
```

**Use the voice-anchoring skill on its own (outside AfterVisit).**
The skill at `skills/email-voice/` is self-contained. Drop it into a Claude Code project's `skills/` directory or load it via the Agent SDK; see `skills/email-voice/README.md`.

## Repository layout
*(brief tree)*

## Limitations and out-of-scope
- All data is synthetic. No real donor content from anywhere.
- Salesforce write is mocked. Real REST integration is gated behind `USE_REAL_SALESFORCE=true` and out of scope.
- 15-20 voice references is enough for a prototype but probably not for production. Routing quality should be re-measured if the reference corpus grows past ~50.
- The redaction module is regex/keyword based. It catches common cases by design; it is not a substitute for HIPAA-level controls.

## Acknowledgments
Built for BU.330.760 Generative AI for Business, Spring 2026, Prof. Harang Ju.
Voice-anchoring approach incorporates feedback from Prof. Ju on project plan v1.
```

### 5.2 Grader-friendly demo path

The grader gets exactly one command to confirm the system works:

```bash
python -m src.demo --case tc_01
```

What `src/demo.py` does:
- Loads `data/test_cases.json`, picks the named case (default `tc_01`).
- Runs the full pipeline.
- Prints, to stdout: the bullets, the note JSON (pretty), the email body, the reference IDs the skill loaded, and the mock Salesforce activity ID.
- Exits 0 on success, non-zero on validation failure.

If the grader doesn't want to provide an API key, the committed `data/sample_outputs/tc_*_aftervisit.json` files contain the same fields as a prior run, so the artifact is inspectable without execution.

### 5.3 Snapshot artifacts to commit

In `docs/screenshots/`:
1. `01_form.png` — the input form with example bullets entered.
2. `02_outputs.png` — note (left) + email (right) side-by-side after Generate, with the "Refs used" line visible.
3. `03_filed.png` — approval flow with the activity log showing a new filed record at the bottom.
4. `04_eval.png` (optional) — a sample row from `eval_results.csv` or a small chart from `eval_summary.md`.

Take these at `1280×800` or larger. Markdown-embed them in README sections 2 and 4.

In `data/sample_outputs/`:
- One JSON file per (test case × condition) pair, format:
  ```json
  {
    "case_id": "tc_01",
    "condition": "aftervisit",
    "bullets": ["..."],
    "note": { /* full schema-valid note */ },
    "email": "...",
    "references_used": ["ev_001", "ev_003", "ev_005"],
    "scored": { "note": 9, "email": 8 }
  }
  ```
- Generated once and committed. The grader reads these to evaluate results without re-running.

### 5.4 Lightning presentation (`presentation/AfterVisit.pptx`)

Five slides, 30-40 seconds each. **You're being graded on whether the business workflow is clear, not on technical detail.**

**Slide 1 — Title & hook (20s).**
- Title: "AfterVisit — turning 5 bullets into a filed donor note and a sent thank-you in 3 minutes."
- One line: "Major gift officers lose 4-6 hours a month to post-visit paperwork, and many of those visits never get documented at all."

**Slide 2 — User & workflow (30s).**
- Who: MGO at a mid-size nonprofit health-system foundation.
- Workflow today: visit → 20-30 minutes per visit on note + email, often skipped, ~75% on-time completion.
- Why it matters: missed records degrade CRM data, donor handoffs, and retention.

**Slide 3 — What I built (40s).**
- Streamlit app screenshot.
- Architecture in one diagram: bullets → [redact → note call] + [voice-anchoring skill → email call] → human approval → mock Salesforce.
- Three design choices, one line each: decompose into two calls; anchor voice through a portable skill (`SKILL.md` + `references/`); hard approval gate before anything touches the CRM.
- One line: "The skill works on its own outside the app — Claude Code can use it directly."

**Slide 4 — Evaluation (40s).**
- Baseline A: single prompt-only call. The required simpler comparison.
- Baseline B: full pipeline with static exemplars instead of skill routing. Tests whether the skill earns its place.
- 15 synthetic test cases × 2 rubrics × 3 conditions.
- Headline result table with three numbers per condition.

**Slide 5 — Where it works, where it fails, where humans stay (30s).**
- One thing that worked.
- One thing that failed (e.g., the post-decline tone problem — model wants to soft re-ask; SKILL.md explicitly forbids it).
- Where humans stay: every note is approved before filing; every email is reviewed before sending. AfterVisit is a draft-and-approve assistant, never autonomous.

Build the deck after the evaluation runs so slide 4 has real numbers. Don't open PowerPoint until then.

---

## Build order (revised for v3)

**Session 1 (MVP end-to-end, ~3-4 hours):**
1. Project structure, `.env.example`, `.gitignore`, `requirements.txt`.
2. `skills/email-voice/SKILL.md` + 6 reference emails in your voice.
3. `skill_loader.py` + metadata routing. Sanity-check filtering manually with one or two queries from a Python REPL.
4. Schema, both prompts, redact module.
5. `generate.py` happy path. Verify on one test case.
6. `mock_salesforce.py`.
7. Streamlit UI. End-to-end: bullets → note + email → approve → activity log shows the new row. "Refs used" line visible.
8. `src/demo.py` — the grader's one-command path.

**Session 2 (robustness, ~2-3 hours):**
9. Write 9 more references (target 15 total). Cover the adjacency edges deliberately.
10. Write all 15 test cases.
11. Sensitivity-flag UI banner, approval-fatigue checkbox.
12. Injection test: feed an adversarial case through the UI and verify the tagged-data defense holds.
13. Write `skills/email-voice/README.md` so the skill is portable.
14. Take screenshots 01/02/03 → `docs/screenshots/`.

**Session 3 (evaluation, ~3-4 hours):**
15. Judge prompts + judge validation on 5 hand-scored cases.
16. Baselines A and B implemented.
17. Eval harness, run all 15 cases × 3 conditions. Generate `eval_results.csv` + `eval_summary.md`.
18. Generate and commit `data/sample_outputs/` from the run.
19. Haiku-vs-Sonnet comparison on the note for 5 cases.

**Session 4 (submission deliverables, ~2-3 hours):**
20. Fill in the README scaffold with real numbers from the eval.
21. Build the 5-slide deck.
22. Final repo cleanup: no `.env`, no API keys, no real donor data anywhere.
23. Push, tag, submit GitHub link via Canvas.

---

## Things to deliberately skip

- **Embedding-based retrieval.** v3 dropped this on the professor's advice. Metadata routing with adjacency fallback handles 15-20 exemplars cleanly; cosine similarity over a corpus this small adds a dependency without changing the answer.
- A real vector database. Same reason.
- A separate API service. Streamlit calls Python functions directly. There is no API layer.
- Real Salesforce integration. The mock writes to a JSON file. That's enough for the demo and the submission.
- LangChain / LlamaIndex. The skill loader is ~40 lines of Python. Frameworks add concept overhead, not capability.
- Self-critique passes on the email. Project plan flags this as an open question. Measure first; don't pre-commit.
- A live demo at the presentation. The assignment explicitly says you don't need one. The screenshots in `docs/screenshots/` are the demo.

---

## One thing to watch

The references are the soul of the skill. If they all sound the same — same opener, same rhythm, same closer — the model will pattern-match to "AfterVisit voice" instead of your voice. Vary the openers across references. Some start with "Thank you for...", some with "Tuesday's conversation has been on my mind...", some with the donor's question. The model copies what it sees. The skill's routing can pick the right references, but only if there are differentiated references to pick from.
