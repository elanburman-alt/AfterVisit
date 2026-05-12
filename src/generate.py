import json
from datetime import date

from anthropic import Anthropic
from jsonschema import Draft7Validator

from .config import (
    ANTHROPIC_API_KEY,
    MGO_NAME,
    MODEL_EMAIL,
    MODEL_NOTE,
    PROMPTS_DIR,
    SCHEMAS_DIR,
    SKILL_DIR,
)
from .redact import redact
from .skill_loader import EmailVoiceSkill

_client = Anthropic(api_key=ANTHROPIC_API_KEY)
_skill = EmailVoiceSkill(SKILL_DIR)
_NOTE_PROMPT  = (PROMPTS_DIR / "note_system.md").read_text(encoding="utf-8")
_EMAIL_PROMPT = (PROMPTS_DIR / "email_system.md").read_text(encoding="utf-8")
_SCHEMA       = json.loads((SCHEMAS_DIR / "activity_note.schema.json").read_text(encoding="utf-8"))
_VALIDATOR    = Draft7Validator(_SCHEMA)

BASELINE_B_FIXED_REF_IDS = ["ev_001", "ev_003", "ev_004"]

_token_usage = {"input": 0, "output": 0}


def reset_usage() -> None:
    _token_usage["input"] = 0
    _token_usage["output"] = 0


def get_usage() -> dict:
    return dict(_token_usage)


def _add_usage(resp) -> None:
    _token_usage["input"] += resp.usage.input_tokens
    _token_usage["output"] += resp.usage.output_tokens


def _call_note(bullets: list[str], donor_name: str, donor_context: str,
               meeting_type: str, retry_error: str | None = None) -> str:
    system = _NOTE_PROMPT.format(
        schema_json=json.dumps(_SCHEMA),
        today=date.today().isoformat(),
        donor_name=donor_name,
        mgo_name=MGO_NAME,
        donor_context=donor_context,
        meeting_type=meeting_type,
        bullets="\n".join(f"- {b}" for b in bullets),
    )
    if retry_error:
        system += f"\n\nPRIOR ATTEMPT FAILED SCHEMA VALIDATION:\n{retry_error}\nRetry. Return JSON only."
    resp = _client.messages.create(
        model=MODEL_NOTE,
        max_tokens=2048,
        temperature=0.2,
        system=system,
        messages=[{"role": "user", "content": "Generate the activity note."}],
    )
    _add_usage(resp)
    return resp.content[0].text.strip()


def _validate(raw: str) -> tuple[dict | None, str | None]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"
    errs = sorted(_VALIDATOR.iter_errors(obj), key=lambda e: list(e.path))
    if errs:
        return None, "\n".join(f"{list(e.path)}: {e.message}" for e in errs)
    return obj, None


def _call_email(redacted_bullets: list[str], donor_name: str, meeting_type: str,
                references) -> str:
    refs_text = "\n\n---\n\n".join(r.body for r in references) \
        if references else "(no exemplars matched — use voice rules only)"
    system = _EMAIL_PROMPT.format(
        voice_rules_from_skill_md=_skill.voice_rules(),
        loaded_reference_bodies=refs_text,
        donor_name=donor_name,
        mgo_name=MGO_NAME,
        meeting_type=meeting_type,
        redacted_bullets="\n".join(f"- {b}" for b in redacted_bullets),
    )
    resp = _client.messages.create(
        model=MODEL_EMAIL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": "Draft the thank-you email."}],
    )
    _add_usage(resp)
    return resp.content[0].text.strip()


def run(bullets: list[str], donor_name: str, donor_segment: str,
        meeting_type: str, donor_context: str = "") -> dict:
    redacted = redact(bullets)

    raw = _call_note(bullets, donor_name, donor_context, meeting_type)
    note, err = _validate(raw)
    if err:
        raw = _call_note(bullets, donor_name, donor_context, meeting_type, retry_error=err)
        note, err = _validate(raw)
        if err:
            raise ValueError(f"Note failed schema after retry:\n{err}\n\nRaw:\n{raw}")

    refs = _skill.select(meeting_type, donor_segment, k=3)
    email = _call_email(redacted, donor_name, meeting_type, refs)

    return {
        "note": note,
        "email": email,
        "references_used": [r.id for r in refs],
    }


def aftervisit(case: dict) -> dict:
    """Full skill-routed pipeline. Case-dict wrapper around run() for the eval harness."""
    return run(
        bullets=case["bullets"],
        donor_name=case["donor_name"],
        donor_segment=case["donor_segment"],
        meeting_type=case["meeting_type"],
    )


def baseline_a(case: dict) -> dict:
    """Simplest baseline: one model call producing both note and email. No schema,
    no skill, no redaction. The 'simpler-than-yours' comparison required by the
    assignment."""
    bullets = case["bullets"]
    donor = case["donor_name"]
    mt = case["meeting_type"]
    today = date.today().isoformat()

    system = (
        "You are an assistant for a major-gift fundraiser. From the meeting bullets below, produce both:\n"
        "1. A Salesforce activity note as a JSON object with these fields: subject, date (YYYY-MM-DD), "
        "type (discovery/cultivation/solicitation/stewardship/decline), attendees (array of strings), "
        "summary (string), commitments (array of strings), next_steps (array of strings), "
        "solicitation_amount (number or null), commitment_status "
        "(none/verbal_yes/verbal_no/written_pledge/received/deferred), "
        "sensitivity_flags (array, may be empty).\n"
        "2. A thank-you email body as plain text, signed by the MGO.\n\n"
        f"Donor: {donor}\n"
        f"Meeting type: {mt}\n"
        f"Today: {today}\n"
        f"MGO first name: {MGO_NAME}\n\n"
        "Bullets:\n"
        + "\n".join(f"- {b}" for b in bullets)
        + "\n\nReturn JSON only, no fences: {\"note\": {...}, \"email\": \"...\"}"
    )

    resp = _client.messages.create(
        model=MODEL_EMAIL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": "Generate."}],
    )
    _add_usage(resp)

    raw = resp.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(raw)
        return {
            "note": parsed.get("note", {}) if isinstance(parsed.get("note"), dict) else {},
            "email": parsed.get("email", "") if isinstance(parsed.get("email"), str) else "",
            "references_used": [],
        }
    except json.JSONDecodeError:
        return {"note": {}, "email": raw, "references_used": []}


def baseline_b(case: dict) -> dict:
    """Full two-call pipeline but with 3 fixed exemplars (one cultivation, one
    solicitation, one stewardship) instead of skill-routed references. Isolates
    the value of the skill's metadata routing."""
    bullets = case["bullets"]
    donor = case["donor_name"]
    mt = case["meeting_type"]

    redacted = redact(bullets)

    raw = _call_note(bullets, donor, "", mt)
    note, err = _validate(raw)
    if err:
        raw = _call_note(bullets, donor, "", mt, retry_error=err)
        note, err = _validate(raw)
        if err:
            raise ValueError(f"baseline_b note failed schema after retry:\n{err}\n\nRaw:\n{raw}")

    fixed_refs = [r for r in _skill.references if r.id in BASELINE_B_FIXED_REF_IDS]
    email = _call_email(redacted, donor, mt, fixed_refs)

    return {
        "note": note,
        "email": email,
        "references_used": [r.id for r in fixed_refs],
    }
