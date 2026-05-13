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
    sensitivity_aware: bool = False


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
                sensitivity_aware=bool(post.get("sensitivity_aware") or False),
            ))
        return refs

    def select(self, meeting_type: str, donor_segment: str, k: int = 3,
               sensitivity_aware_preferred: bool = False) -> list[Reference]:
        """Return up to k references matching meeting_type and donor_segment.

        Sensitivity-aware references (frontmatter `sensitivity_aware: true`)
        are gated behind the preference flag (v1.6):

        - sensitivity_aware_preferred=False: sensitivity-aware refs are
          EXCLUDED from the pool. This preserves v1 routing for cases
          where the note's sensitivity_flags list is empty.
        - sensitivity_aware_preferred=True: sensitivity-aware refs are
          INCLUDED and stably sorted to the front of the candidate list
          so they lead the exemplars.

        Callers should pass True when the note's sensitivity_flags list
        is non-empty; otherwise leave as False.
        """
        pool = [r for r in self.references if r.meeting_type == meeting_type]
        if not sensitivity_aware_preferred:
            pool = [r for r in pool if not r.sensitivity_aware]

        exact = [r for r in pool if r.donor_segment == donor_segment]
        if len(exact) >= k:
            candidates = exact
        else:
            adj = ADJACENT_SEGMENTS.get(donor_segment, [])
            nearby = [r for r in pool if r.donor_segment in adj and r not in exact]
            candidates = exact + nearby

        if sensitivity_aware_preferred:
            # Stable sort: sensitivity-aware refs first, preserving relative
            # order among each group.
            candidates = sorted(candidates, key=lambda r: 0 if r.sensitivity_aware else 1)

        return candidates[:k]

    def voice_rules(self) -> str:
        md = self.skill_md
        start = md.find("## How to use what you load")
        end = md.find("## References")
        if start == -1 or end == -1:
            return md
        return md[start:end].strip()
