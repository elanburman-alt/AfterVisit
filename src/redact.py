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
