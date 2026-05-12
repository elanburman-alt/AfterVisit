"""Evaluation harness. Runs each (condition × case), scores with judges, applies
binary cap rules, writes eval_results.csv + eval_summary.md."""

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from anthropic import Anthropic
from jsonschema import Draft7Validator

from .config import (
    ANTHROPIC_API_KEY,
    MODEL_JUDGE,
    PROMPTS_DIR,
    ROOT,
    SCHEMAS_DIR,
    TEST_CASES,
)
from .generate import aftervisit, baseline_a, baseline_b, get_usage, reset_usage
from .redact import detect_categories

_client = Anthropic(api_key=ANTHROPIC_API_KEY)
_JUDGE_NOTE  = (PROMPTS_DIR / "judge_note.md").read_text(encoding="utf-8")
_JUDGE_EMAIL = (PROMPTS_DIR / "judge_email.md").read_text(encoding="utf-8")
_SCHEMA      = json.loads((SCHEMAS_DIR / "activity_note.schema.json").read_text(encoding="utf-8"))
_VALIDATOR   = Draft7Validator(_SCHEMA)

CONDITIONS = {
    "a": baseline_a,
    "b": baseline_b,
    "aftervisit": aftervisit,
}

NOTE_DIMS  = ["completeness", "commitment_accuracy", "schema_conformance",
              "sensitivity_flagging", "hallucination_freeness"]
EMAIL_DIMS = ["personalization", "voice_match", "tone_appropriateness",
              "next_step_calibration", "information_flow_compliance"]

CAP_THRESHOLD = 6
NOTE_CAP_DIM  = "hallucination_freeness"
EMAIL_CAP_DIM = "information_flow_compliance"


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return raw


def _judge(template: str, **fields) -> dict:
    # The judge prompts contain literal { } in the output-contract example
    # (showing the expected JSON shape), so .format() collides with those.
    # Use direct substitution instead.
    system = template
    for key, value in fields.items():
        system = system.replace("{" + key + "}", str(value))
    resp = _client.messages.create(
        model=MODEL_JUDGE,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": "Score it."}],
    )
    return json.loads(_strip_fences(resp.content[0].text))


def judge_note(case: dict, note: dict) -> dict:
    return _judge(
        _JUDGE_NOTE,
        case_id=case["id"],
        tier=case.get("tier", ""),
        donor_name=case["donor_name"],
        meeting_type=case["meeting_type"],
        bullets="\n".join(f"- {b}" for b in case["bullets"]),
        expected_sensitivity_flags=json.dumps(case.get("expected_sensitivity_flags", [])),
        expected_commitments=json.dumps(case.get("expected_commitments", [])),
        note_json=json.dumps(note, indent=2),
    )


def judge_email(case: dict, email: str, references_used: list, sensitivity_flags: list) -> dict:
    return _judge(
        _JUDGE_EMAIL,
        case_id=case["id"],
        tier=case.get("tier", ""),
        donor_name=case["donor_name"],
        meeting_type=case["meeting_type"],
        bullets="\n".join(f"- {b}" for b in case["bullets"]),
        sensitivity_flags=json.dumps(sensitivity_flags),
        references_used=json.dumps(references_used),
        grader_notes=case.get("notes_for_human_grader", ""),
        email_body=email,
    )


def _apply_cap(scores: dict, dims: list, cap_dim: str) -> tuple[int, bool]:
    """Sum the per-dimension scores; cap total at CAP_THRESHOLD if cap_dim scored 0."""
    total = sum(scores["dimensions"][d]["score"] for d in dims)
    capped = scores["dimensions"][cap_dim]["score"] == 0
    if capped:
        total = min(total, CAP_THRESHOLD)
    return total, capped


def _tool_call_status(note: dict) -> str:
    """Validate the note against the schema without writing to activity_log."""
    errors = sorted(_VALIDATOR.iter_errors(note), key=lambda e: list(e.path))
    if not errors:
        return "ok"
    first = errors[0]
    return f"schema_invalid: {list(first.path)}: {first.message}"


def _empty_scores(dims: list, msg: str) -> dict:
    return {"dimensions": {d: {"score": 0, "rationale": msg} for d in dims}}


def evaluate_case(case: dict, condition: str) -> dict:
    fn = CONDITIONS[condition]
    reset_usage()
    started = time.time()

    try:
        result = fn(case)
    except Exception as e:
        return {
            "case_id": case["id"],
            "tier": case.get("tier", ""),
            "condition": condition,
            "note_score": 0,
            "email_score": 0,
            "note_dimensions": {},
            "email_dimensions": {},
            "sensitivity_leakage": "",
            "tool_call_status": f"generation_error: {e}",
            "latency_s": round(time.time() - started, 2),
            "input_tokens": get_usage()["input"],
            "output_tokens": get_usage()["output"],
            "_references_used": [],
        }

    latency = round(time.time() - started, 2)
    usage = get_usage()
    note = result.get("note", {})
    email = result.get("email", "")
    refs_used = result.get("references_used", [])

    try:
        note_scores = judge_note(case, note)
    except Exception as e:
        note_scores = _empty_scores(NOTE_DIMS, f"judge error: {e}")
    try:
        flags = note.get("sensitivity_flags", []) or []
        email_scores = judge_email(case, email, refs_used, flags)
    except Exception as e:
        email_scores = _empty_scores(EMAIL_DIMS, f"judge error: {e}")

    note_total, _ = _apply_cap(note_scores, NOTE_DIMS, NOTE_CAP_DIM)
    email_total, _ = _apply_cap(email_scores, EMAIL_DIMS, EMAIL_CAP_DIM)

    flags = note.get("sensitivity_flags", []) or []
    leaked = sorted(set(flags) & set(detect_categories(email)))

    return {
        "case_id": case["id"],
        "tier": case.get("tier", ""),
        "condition": condition,
        "note_score": note_total,
        "email_score": email_total,
        "note_dimensions": note_scores["dimensions"],
        "email_dimensions": email_scores["dimensions"],
        "sensitivity_leakage": ",".join(leaked),
        "tool_call_status": _tool_call_status(note),
        "latency_s": latency,
        "input_tokens": usage["input"],
        "output_tokens": usage["output"],
        "_references_used": refs_used,
    }


def write_csv(rows: list, path: Path) -> None:
    fieldnames = [
        "case_id", "tier", "condition",
        "note_score", "email_score",
        "note_dimensions", "email_dimensions",
        "sensitivity_leakage", "tool_call_status",
        "latency_s", "input_tokens", "output_tokens",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            row = dict(r)
            row["note_dimensions"] = json.dumps(r["note_dimensions"])
            row["email_dimensions"] = json.dumps(r["email_dimensions"])
            w.writerow(row)


def _mean_or_dash(values: list) -> str:
    return f"{mean(values):.2f}" if values else "-"


def write_summary(rows: list, path: Path) -> None:
    conditions = sorted({r["condition"] for r in rows})
    case_ids = sorted({r["case_id"] for r in rows})

    lines: list[str] = []
    lines.append("# AfterVisit Evaluation Summary")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Conditions: {', '.join(conditions)}")
    lines.append(f"Cases: {len(case_ids)}")
    lines.append("")

    lines.append("## Headline scores")
    lines.append("")
    lines.append("| Condition | Note (mean/10) | Email (mean/10) | Sensitivity leakage | Tool-call success |")
    lines.append("|---|---|---|---|---|")
    for c in conditions:
        rs = [r for r in rows if r["condition"] == c]
        ok = [r for r in rs if r["tool_call_status"] == "ok"]
        note_mean = mean(r["note_score"] for r in ok) if ok else 0.0
        email_mean = mean(r["email_score"] for r in ok) if ok else 0.0
        leak = sum(1 for r in rs if r["sensitivity_leakage"])
        lines.append(f"| {c} | {note_mean:.1f} | {email_mean:.1f} | {leak}/{len(rs)} | {len(ok)}/{len(rs)} |")
    lines.append("")

    lines.append("## Note dimensions (mean per condition)")
    lines.append("")
    lines.append("| Condition | " + " | ".join(NOTE_DIMS) + " |")
    lines.append("|" + "---|" * (len(NOTE_DIMS) + 1))
    for c in conditions:
        rs = [r for r in rows if r["condition"] == c and r["note_dimensions"]]
        row = f"| {c} |"
        for d in NOTE_DIMS:
            vals = [r["note_dimensions"][d]["score"] for r in rs if d in r["note_dimensions"]]
            row += f" {_mean_or_dash(vals)} |"
        lines.append(row)
    lines.append("")

    lines.append("## Email dimensions (mean per condition)")
    lines.append("")
    lines.append("| Condition | " + " | ".join(EMAIL_DIMS) + " |")
    lines.append("|" + "---|" * (len(EMAIL_DIMS) + 1))
    for c in conditions:
        rs = [r for r in rows if r["condition"] == c and r["email_dimensions"]]
        row = f"| {c} |"
        for d in EMAIL_DIMS:
            vals = [r["email_dimensions"][d]["score"] for r in rs if d in r["email_dimensions"]]
            row += f" {_mean_or_dash(vals)} |"
        lines.append(row)
    lines.append("")

    av_rows = [r for r in rows if r["condition"] == "aftervisit" and r["tool_call_status"] == "ok"]
    if av_rows:
        with_refs = sum(1 for r in av_rows if r["_references_used"])
        lines.append("## Skill routing coverage (aftervisit)")
        lines.append("")
        lines.append(f"{with_refs}/{len(av_rows)} cases loaded at least one reference.")
        lines.append("")

    lines.append("## Per-case scores (note / email)")
    lines.append("")
    lines.append("| Case | Tier | " + " | ".join(conditions) + " |")
    lines.append("|" + "---|" * (len(conditions) + 2))
    for cid in case_ids:
        rs = {r["condition"]: r for r in rows if r["case_id"] == cid}
        tier = next((r["tier"] for r in rs.values()), "")
        row = f"| {cid} | {tier} |"
        for c in conditions:
            r = rs.get(c)
            if r and r["tool_call_status"] == "ok":
                row += f" {r['note_score']}/{r['email_score']} |"
            else:
                row += " — |"
        lines.append(row)
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run AfterVisit evaluation.")
    ap.add_argument("--conditions", default="a,b,aftervisit",
                    help="Comma-separated condition names (any of: a, b, aftervisit)")
    ap.add_argument("--cases", default=str(TEST_CASES),
                    help="Path to test_cases.json")
    ap.add_argument("--case-ids", default=None,
                    help="Optional comma-separated subset of case IDs")
    ap.add_argument("--out", default=str(ROOT / "eval_results.csv"),
                    help="Output CSV path")
    ap.add_argument("--summary", default=str(ROOT / "eval_summary.md"),
                    help="Output summary markdown path")
    args = ap.parse_args()

    conditions = args.conditions.split(",")
    for c in conditions:
        if c not in CONDITIONS:
            raise SystemExit(f"Unknown condition: {c}. Valid: {list(CONDITIONS)}")

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.case_ids:
        wanted = set(args.case_ids.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    if not cases:
        raise SystemExit("No cases to run.")

    rows = []
    for case in cases:
        for cond in conditions:
            print(f"running {case['id']} × {cond}...", flush=True)
            row = evaluate_case(case, cond)
            rows.append(row)
            print(f"  -> note {row['note_score']}/10, email {row['email_score']}/10, "
                  f"{row['tool_call_status']}, {row['latency_s']}s")

    write_csv(rows, Path(args.out))
    write_summary(rows, Path(args.summary))
    print(f"\nWrote {args.out} and {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
