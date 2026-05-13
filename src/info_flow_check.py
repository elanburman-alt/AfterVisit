"""Post-generation information-flow check.

Given an email and the note's sensitivity_flags, ask Haiku whether the email
leaks content from a flagged category. Returns a structured verdict that the
caller uses to decide whether to regenerate in strict mode.
"""
import json
import re

from anthropic import Anthropic

from .config import ANTHROPIC_API_KEY, MODEL_NOTE, PROMPTS_DIR

_client = Anthropic(api_key=ANTHROPIC_API_KEY)
_PROMPT = (PROMPTS_DIR / "info_flow_check.md").read_text(encoding="utf-8")

_token_usage = {"input": 0, "output": 0}


def reset_usage() -> None:
    _token_usage["input"] = 0
    _token_usage["output"] = 0


def get_usage() -> dict:
    return dict(_token_usage)


def _add_usage(resp) -> None:
    _token_usage["input"] += resp.usage.input_tokens
    _token_usage["output"] += resp.usage.output_tokens


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    return raw


def _parse_defensive(raw: str) -> dict | None:
    text = _strip_fences(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
        return None


def check_info_flow(email: str, sensitivity_flags: list[str]) -> dict:
    """Check if the email leaks content from flagged sensitivity categories.

    Returns:
        {
            "leaked": bool,
            "leaked_categories": list[str],
            "offending_phrase": str | None,
            "explanation": str,
        }

    If sensitivity_flags is empty, returns the no-flags result without an API call.
    If the model response cannot be parsed, returns a fail-closed result
    (leaked=True, offending_phrase=None, explanation="check failed to parse")
    so the caller can decide whether to regenerate or surface the failure.
    """
    if not sensitivity_flags:
        return {
            "leaked": False,
            "leaked_categories": [],
            "offending_phrase": None,
            "explanation": "No flags to check against.",
        }

    # Direct string replacement to avoid the literal-brace .format() collision:
    # the prompt contains literal { } in the JSON output schema example.
    system = _PROMPT.replace("{sensitivity_flags}", json.dumps(sensitivity_flags))
    system = system.replace("{email}", email)

    resp = _client.messages.create(
        model=MODEL_NOTE,
        max_tokens=1024,
        temperature=0.0,
        system=system,
        messages=[{"role": "user", "content": "Check it."}],
    )
    _add_usage(resp)

    parsed = _parse_defensive(resp.content[0].text)
    if parsed is None:
        return {
            "leaked": True,
            "leaked_categories": list(sensitivity_flags),
            "offending_phrase": None,
            "explanation": "check failed to parse",
        }

    return {
        "leaked": bool(parsed.get("leaked", False)),
        "leaked_categories": parsed.get("leaked_categories") or [],
        "offending_phrase": parsed.get("offending_phrase"),
        "explanation": parsed.get("explanation", ""),
    }
