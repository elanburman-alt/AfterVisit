import pytest

from src.config import SKILL_DIR
from src.skill_loader import ADJACENT_SEGMENTS, EmailVoiceSkill


@pytest.fixture(scope="module")
def skill():
    return EmailVoiceSkill(SKILL_DIR)


def test_hard_filter_excludes_mismatched_meeting_type(skill):
    refs = skill.select("decline", "mid_5k_10k", k=3)
    assert all(r.meeting_type == "decline" for r in refs)


def test_empty_result_returns_empty_list(skill):
    refs = skill.select("not_a_real_type", "prospect", k=3)
    assert refs == []


def test_determinism(skill):
    a = skill.select("cultivation", "mid_5k_10k", k=3)
    b = skill.select("cultivation", "mid_5k_10k", k=3)
    assert [r.id for r in a] == [r.id for r in b]


def test_at_most_k_results(skill):
    assert len(skill.select("cultivation", "mid_5k_10k", k=2)) <= 2
    assert len(skill.select("cultivation", "mid_5k_10k", k=3)) <= 3


def test_draft_scaffolds_excluded(skill):
    # Bodies that still contain "<!-- DRAFT SCAFFOLD" must not be loaded.
    for r in skill.references:
        assert "<!-- DRAFT SCAFFOLD" not in r.body, f"draft leaked: {r.path.name}"


def test_adjacency_map_matches_skill_md(skill):
    md = skill.skill_md
    documented = [
        ("prospect", "new_donor"),
        ("mid_5k_10k", "new_donor"),
        ("major_15k_50k", "lead_100k_plus"),
    ]
    for a, b in documented:
        assert f"`{a}` ↔ `{b}`" in md or f"`{b}` ↔ `{a}`" in md, f"adjacency {a}↔{b} not documented in SKILL.md"
        assert b in ADJACENT_SEGMENTS.get(a, []), f"{a}→{b} documented but missing in code"
        assert a in ADJACENT_SEGMENTS.get(b, []), f"{b}→{a} documented but missing in code"
