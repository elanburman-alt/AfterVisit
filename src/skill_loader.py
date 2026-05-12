from dataclasses import dataclass
from pathlib import Path
import frontmatter

ADJACENT_SEGMENTS = {
    "prospect":       ["new_donor"],
    "new_donor":      ["prospect", "mid_5k_10k"],
    "mid_5k_10k":     ["new_donor"],
    "major_15k_50k":  ["lead_100k_plus"],
    "lead_100k_plus": ["major_15k_50k"],
}


@dataclass
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
        self.skill_dir = skill_dir
        self.skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        self.references = self._load_refs(skill_dir / "references")

    def _load_refs(self, refs_dir: Path) -> list[Reference]:
        refs: list[Reference] = []
        for path in sorted(refs_dir.glob("*.md")):
            post = frontmatter.load(path)
            refs.append(Reference(
                id=str(post.get("id") or path.stem),
                meeting_type=str(post.get("meeting_type") or ""),
                donor_segment=str(post.get("donor_segment") or ""),
                program=post.get("program"),
                tags=list(post.get("tags") or []),
                body=post.content,
                path=path,
            ))
        return refs

    def select(self, meeting_type: str, donor_segment: str, k: int = 3) -> list[Reference]:
        pool = [r for r in self.references if r.meeting_type == meeting_type]
        exact = [r for r in pool if r.donor_segment == donor_segment]
        if len(exact) >= k:
            return exact[:k]
        adj = ADJACENT_SEGMENTS.get(donor_segment, [])
        nearby = [r for r in pool if r.donor_segment in adj and r not in exact]
        return (exact + nearby)[:k]

    def voice_rules(self) -> str:
        md = self.skill_md
        start = md.find("## How to use what you load")
        end = md.find("## References")
        if start == -1 or end == -1:
            return md
        return md[start:end].strip()
