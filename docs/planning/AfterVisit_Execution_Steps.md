# Execute AfterVisit — Step-by-Step

How to actually build it. The build plan is the reference; this is the do-list. Total time budget: ~12 hours across 4 sessions.

**Division of labor.** Three players:
- **You** — review, edit, decide, take screenshots, submit.
- **Claude (in chat, this thread)** — draft reference emails, draft test cases, write the slide deck content. Has memory of your voice and project context.
- **Claude Code (in terminal)** — write Python, scaffold files, run evals, fix bugs. Reads the build plan, executes against it.

Wherever a step says "ask Claude," do it here in this chat. Wherever a step says "tell Claude Code," paste the prompt into a Claude Code session.

---

## Before you start (one-time, 30 min)

1. **Anthropic API key.** Get one at console.anthropic.com if you don't already have one. Stash it somewhere safe — you'll paste it into `.env` later.
2. **Python 3.11+.** Verify: `python3 --version`. If older, install via brew/pyenv.
3. **Claude Code.** Install: `npm install -g @anthropic-ai/claude-code`. Verify: `claude --version`.
4. **GitHub repo.** Create a new empty repo named `aftervisit`. Clone it locally. `cd aftervisit`.
5. **Drop the build plan in.** Copy `AfterVisit_Build_Plan.md` into the repo root. This is what Claude Code will read.

---

## Session 1 — MVP end-to-end (3-4 hours)

Goal: app runs, you can enter bullets and get a note + email + filed activity.

### 1.1 Scaffold the project (Claude Code, 10 min)
Open Claude Code in the repo. Paste:

```
Read AfterVisit_Build_Plan.md. Create the project structure described in Phase 0.1 — all directories and the files .gitignore, .env.example, requirements.txt, LICENSE (MIT), and an empty README.md. Do not create source code yet, just the scaffolding. Show me the resulting tree.
```

**Check:** the tree matches Phase 0.1 of the build plan. Commit: `git add -A && git commit -m "scaffold"`.

### 1.2 Draft 6 reference emails (Claude here in chat, 30-45 min)
Come back to this thread and ask:

> Draft 6 reference emails for `skills/email-voice/references/` covering the 6 cells in Phase 1.3 of the build plan. Use my actual voice — refer to past emails and dvar Torah work you've helped me with. Use synthetic donor names, synthetic dollar amounts, synthetic Adventist-adjacent programs. Include the YAML frontmatter. Vary the openers across the 6 emails so they don't all sound the same.

Review each one. Edit ruthlessly — anything that sounds like a template, rewrite. **This is the single highest-leverage manual step in the project.** If the references are bland, every output is bland.

Save them as `skills/email-voice/references/01_*.md` through `06_*.md`.

### 1.3 Build the skill + core code (Claude Code, 60-90 min)
Paste:

```
Read AfterVisit_Build_Plan.md sections Phase 1 (subsections 1.1, 1.4, 1.5), Phase 2 (all), and Phase 3.

Implement:
- skills/email-voice/SKILL.md per the template in 1.1 (do not modify the references/ I've already written)
- src/skill_loader.py per the contract in 1.4 — keep it under 60 lines
- src/config.py, src/redact.py, src/mock_salesforce.py
- schemas/activity_note.schema.json
- prompts/note_system.md and prompts/email_system.md
- src/generate.py (the `run` function only — no baselines yet)
- app.py (Streamlit UI per Phase 3, no eval features yet)
- src/demo.py per Phase 5.2
- tests/test_skill_loader.py

Constraints:
- No sentence-transformers, no embeddings, no vector DBs
- No LangChain, LlamaIndex, or other frameworks
- Ask me before adding any dependency not already in requirements.txt
- Use exact model names from Phase 0.3
```

When it finishes, ask it to run the unit tests: `pytest tests/`.

### 1.4 First end-to-end test (you, 20 min)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Paste ANTHROPIC_API_KEY=sk-ant-... into .env
python -m src.demo --case tc_01
```

Won't work yet — no test cases. Create a minimal one by hand to verify the demo path:

```bash
echo '[{"id":"tc_01","tier":"easy","donor_name":"Margaret Chen","donor_segment":"mid_5k_10k","meeting_type":"cultivation","bullets":["Heart Institute expansion","cardiologist recruitment question","tour requested","daughter starting med school","next step: schedule tour in May"]}]' > data/test_cases.json
python -m src.demo --case tc_01
```

**Check:** you see a JSON note and an email printed to stdout. The email should sound like one of your references (warm, specific, no exclamation points).

### 1.5 Streamlit smoke test (you, 10 min)
```bash
streamlit run app.py
```

Open the URL. Enter the same bullets. Click Generate. **Check:** note on the left, email on the right, "Refs used" line shows real reference IDs, Approve button is disabled until you check "I've read the note," clicking Approve writes to `data/activity_log.json`.

### 1.6 Commit and rest
```bash
git add -A && git commit -m "Session 1: MVP end-to-end works"
```

---

## Session 2 — Robustness (2-3 hours)

Goal: 15 references, 15 test cases, sensitivity controls, injection defense, screenshots.

### 2.1 Draft 9 more reference emails (Claude here in chat, 45-60 min)
Ask:

> Draft 9 more reference emails for `skills/email-voice/references/`. Cover meeting_type × donor_segment combinations not yet covered by my first 6, and deliberately exercise the adjacency edges (one new_donor↔mid_5k_10k, one major_15k_50k↔lead_100k_plus). Keep my voice. Vary the openers.

Review, edit, save as `07_*.md` through `15_*.md`.

### 2.2 Draft the 15 test cases (Claude here in chat, 30-45 min)
Ask:

> Generate 15 test cases for data/test_cases.json per Phase 4.1: 3 easy, 6 normal, 4 edge (sensitive disclosure, declined ask, on-the-spot commitment, board complication), 2 adversarial (prompt-injection in bullets, unflagged sensitive content). Use synthetic donor names. Include expected_sensitivity_flags, expected_commitments, and notes_for_human_grader on the edge and adversarial cases.

Review. Save to `data/test_cases.json`.

### 2.3 Add UI hardening (Claude Code, 30-45 min)
Paste:

```
Update app.py to add:
1. Sensitivity-flag colored chips at the top of the note panel
2. Warning banner above the email if sensitivity_flags is non-empty AND the email body contains a flagged keyword
3. "Refs used: ev_xxx, ev_yyy" line under the email panel showing which references the skill loaded

Also: verify the XML-tagged-data injection defense in prompts/note_system.md and prompts/email_system.md is solid. Run our adversarial test case tc_14 (prompt-injection) through src/demo.py and show me the output.
```

**Check:** the injection case does not produce an email that follows the injected instruction.

### 2.4 Write the skill's own README (Claude Code, 10 min)
Paste:

```
Write skills/email-voice/README.md per Phase 1.6 of the build plan — 3-4 paragraphs covering what the skill does, how to add a new reference, how to use it from Claude Code, how to use it from the Agent SDK.
```

### 2.5 Take screenshots (you, 15 min)
With the app running, capture:
- `docs/screenshots/01_form.png` — input form with example bullets entered
- `docs/screenshots/02_outputs.png` — note + email side-by-side with "Refs used" visible
- `docs/screenshots/03_filed.png` — after clicking Approve, showing the activity log row at the bottom

Use Cmd+Shift+4 on Mac, save 1280×800 or larger.

### 2.6 Commit
```bash
git add -A && git commit -m "Session 2: 15 references, 15 cases, UI hardening, screenshots"
```

---

## Session 3 — Evaluation (3-4 hours)

Goal: judges, baselines, eval run, sample outputs.

### 3.1 Build judges + baselines + eval harness (Claude Code, 60-90 min)
Paste:

```
Read Phase 4 of AfterVisit_Build_Plan.md. Implement:
- prompts/judge_note.md and prompts/judge_email.md per Phase 4.3 (binary cap rules go in post-processing in src/evaluate.py, NOT in the judge prompts)
- baseline_a and baseline_b functions in src/generate.py per Phase 4.2
- src/evaluate.py per Phase 4.4 — outputs eval_results.csv and eval_summary.md

The eval CLI should be:
python -m src.evaluate --conditions a,b,aftervisit --cases data/test_cases.json
```

### 3.2 Hand-score 5 cases (you, 30-45 min)
This is judge validation. Run the full pipeline on 5 cases (mix of easy/normal/edge):

```bash
for tc in tc_01 tc_04 tc_07 tc_10 tc_13; do
  python -m src.demo --case $tc > /tmp/$tc.txt
done
```

Open each file. Score the note (out of 10) and email (out of 10) using the rubric dimensions from Phase 4.3. Write your scores into a scratch file.

### 3.3 Validate the judge (Claude Code, 20 min)
Paste:

```
Run the judge on these 5 cases: tc_01, tc_04, tc_07, tc_10, tc_13. Compare its scores to mine [paste your hand scores]. Report per-dimension agreement. If any dimension differs by more than 1 point on more than 1 case, propose a judge prompt revision.
```

Iterate until agreement is acceptable. Then proceed.

### 3.4 Run the full eval (Claude Code or you, 30-45 min)
```bash
python -m src.evaluate --conditions a,b,aftervisit --cases data/test_cases.json
```

This makes real API calls — budget ~$5-10 in tokens. Tail the run; if costs balloon, kill it and ask Claude Code to investigate.

**Check:** `eval_results.csv` and `eval_summary.md` exist and look sensible.

### 3.5 Generate committed sample outputs (Claude Code, 20 min)
Paste:

```
For each test case × condition, write a JSON file to data/sample_outputs/tc_XX_<condition>.json in the format from Phase 5.3 of the build plan (case_id, condition, bullets, note, email, references_used, scored). Use the outputs from the eval run we just did. Commit these files.
```

### 3.6 Haiku vs Sonnet on the note (Claude Code, 20 min)
Paste:

```
Run a 5-case comparison of claude-haiku-4-5-20251001 vs claude-sonnet-4-6 on the note generation only. Report mean note score, cost per call, latency, and a recommendation. Append the table to eval_summary.md.
```

### 3.7 Commit
```bash
git add -A && git commit -m "Session 3: evaluation run, sample outputs, model comparison"
```

---

## Session 4 — Submission deliverables (2-3 hours)

Goal: README filled in with real numbers, slide deck, clean repo, submitted.

### 4.1 Fill in the README (Claude Code, 30 min)
Paste:

```
Open README.md. The Phase 5.1 scaffold in AfterVisit_Build_Plan.md is the template. Fill in:
- Section 3 headline results table — pull real numbers from eval_results.csv
- Section 3 "What worked" — propose 3 bullets based on eval_summary.md, then ask me to confirm
- Section 3 "What failed" — propose 2-3 bullets including at least one anticipated failure from the project plan §6 that the eval actually reproduced
- Repository layout — generate from `tree -L 2`

Embed the three screenshots in sections 2 and 4.
```

Review the proposed "what worked / what failed" bullets carefully. Edit so they sound like you talking, not Claude Code talking.

### 4.2 Build the slide deck (Claude here in chat, 30-45 min)
Ask:

> Draft the 5-slide deck content per Phase 5.4 of the build plan, using the actual results from my eval_summary.md [paste it]. Output as a markdown outline with speaker notes for each slide.

Then either:
- **Easy path:** ask me here to generate the .pptx using the pptx skill, or
- **Manual path:** open Keynote/PowerPoint and build it yourself from the outline

Save as `presentation/AfterVisit.pptx`. Time yourself reading it through — must fit 2-3 minutes.

### 4.3 Repo cleanup (you, 15 min)
```bash
# Confirm no secrets
git ls-files | xargs grep -l "sk-ant-" || echo "clean"

# Confirm .env is not tracked
git ls-files | grep "^\.env$" && echo "PROBLEM" || echo "clean"

# Confirm activity_log.json is not tracked
git ls-files | grep "activity_log.json$" && echo "PROBLEM" || echo "clean"

# Confirm no real donor names anywhere
git ls-files | xargs grep -l "Adventist HealthCare" || echo "clean"
```

Fix anything that flags. Then:

```bash
git add -A && git commit -m "Session 4: README, slides, submission ready"
git push origin main
```

### 4.4 Final smoke test (you, 10 min)
Simulate the grader experience. In a clean directory:

```bash
git clone <your-repo-url> aftervisit-grader-test
cd aftervisit-grader-test
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Paste your key
python -m src.demo --case tc_01
```

**Check:** it works end-to-end with zero hand-holding. If it doesn't, fix it now.

### 4.5 Submit
- Tag the release: `git tag v1.0 && git push --tags`
- Submit the GitHub URL via Canvas

---

## If things go wrong

| Symptom                                        | Fix                                                                 |
|------------------------------------------------|---------------------------------------------------------------------|
| Claude Code adds embeddings or a vector DB     | "Stop. Re-read the simplicity defense in the build plan. Revert."   |
| `skill_loader.py` is over 60 lines             | "Compress. Metadata filter + adjacency map. Nothing else."          |
| Email reads like a template, not like you      | The references are bland. Rewrite 2-3 of them with sharper voice.   |
| Judge disagrees with you by 2+ points          | Revise the judge prompt; add more rubric examples. Re-validate.     |
| Eval costs spiraling                           | Drop email model from Opus to Sonnet 4.6. Cache the system prompt.  |
| Streamlit "Refs used" line is empty            | Skill found no exact-match references. Check adjacency map in code matches SKILL.md. |
| Injection test produces compromised email      | Re-tag inputs in prompts/email_system.md with `<bullets>`; explicit instruction-vs-data separation. |
| `data/activity_log.json` showing up in git     | Add to `.gitignore`, then `git rm --cached data/activity_log.json`. |

---

## What to do today

If you have 30 minutes right now: do the "Before you start" section, then return to this chat and ask me to draft the first 6 reference emails. By the time you sit down for Session 1 proper, you'll have the highest-leverage manual piece already in hand.
