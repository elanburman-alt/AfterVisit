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
