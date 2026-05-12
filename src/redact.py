import re

HEALTH = [
    r"\bcancer\b", r"\bstroke\b", r"\bdiagnos(is|ed)\b", r"\btreatment\b",
    r"\bICU\b", r"\bhospice\b", r"\bsurgery\b", r"\bchemo(therapy)?\b",
    r"\bdementia\b", r"\bAlzheimer'?s\b", r"\btransplant\b", r"\bterminal\b",
]
FAMILY = [
    r"\bdivorce(d)?\b", r"\bpassed (away|on)\b",
    r"\blost (his|her|their|my) (husband|wife|son|daughter|mother|father|parent)\b",
    r"\bwidow(er)?\b", r"\bfuneral\b", r"\bmiscarriage\b",
]
FINANCIAL = [
    r"\bbankruptcy\b", r"\blay[- ]?off\b", r"\blaid off\b",
    r"\blost (his|her|their|my) job\b", r"\bforeclos(ure|ed)\b",
]

CATEGORIES = {"health": HEALTH, "family": FAMILY, "financial": FINANCIAL}


def redact(bullets: list[str]) -> list[str]:
    out: list[str] = []
    for bullet in bullets:
        line = bullet
        for category, patterns in CATEGORIES.items():
            for pattern in patterns:
                line = re.sub(pattern, f"[redacted: {category}]", line, flags=re.IGNORECASE)
        out.append(line)
    return out


def detect_categories(text: str) -> list[str]:
    """Return categories whose patterns match anywhere in text. Used to scan
    post-generation output (e.g., the email body) for keywords matching
    sensitive categories — a leakage check, not redaction."""
    matches: list[str] = []
    for category, patterns in CATEGORIES.items():
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                matches.append(category)
                break
    return matches
