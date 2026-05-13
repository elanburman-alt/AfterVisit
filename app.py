import json
from pathlib import Path

import streamlit as st

from src.config import ACTIVITY_LOG
from src.generate import run
from src.mock_salesforce import post_activity
from src.redact import detect_categories

DONOR_SEGMENTS = ["prospect", "new_donor", "mid_5k_10k", "major_15k_50k", "lead_100k_plus"]
MEETING_TYPES  = ["discovery", "cultivation", "solicitation", "stewardship", "decline"]

FLAG_COLORS = {
    "health":             "#dc2626",
    "family":             "#ea580c",
    "financial":          "#ca8a04",
    "board_dynamics":     "#2563eb",
    "donor_relationship": "#9333ea",
    "other":              "#6b7280",
}
FLAG_LABELS = {
    "health":             "health",
    "family":             "family",
    "financial":          "financial",
    "board_dynamics":     "board",
    "donor_relationship": "relationship",
    "other":              "other",
}

SAMPLE_CHOICES = [
    "(none — enter your own bullets)",
    "tc_01: easy cultivation, mid-tier donor",
    "tc_05: normal solicitation, major donor",
    "tc_10: edge stewardship with sensitive health disclosure",
    "tc_13: edge cultivation with confidential governance question",
    "tc_15: edge stewardship with family hardship disclosure",
]
SAMPLE_CHOICE_TO_ID = {
    "tc_01: easy cultivation, mid-tier donor": "tc_01",
    "tc_05: normal solicitation, major donor": "tc_05",
    "tc_10: edge stewardship with sensitive health disclosure": "tc_10",
    "tc_13: edge cultivation with confidential governance question": "tc_13",
    "tc_15: edge stewardship with family hardship disclosure": "tc_15",
}

INFO_FLOW_BADGES = {
    "no_flags_to_check":       ("⚪", "Info-flow: no flags to check",        "#6b7280"),
    "clean_first_try":         ("🟢", "Info-flow: clean on first try",       "#16a34a"),
    "regenerated_clean":       ("🟡", "Info-flow: regenerated after leak caught", "#ca8a04"),
    "still_leaked_after_regen":("🔴", "Info-flow: human review required",    "#dc2626"),
}


def _chip_html(flag: str) -> str:
    return (
        f'<span style="background:{FLAG_COLORS.get(flag, "#6b7280")};'
        f' color:white; padding:3px 10px; border-radius:12px;'
        f' font-size:0.85em; margin-right:6px; display:inline-block;">'
        f'{FLAG_LABELS.get(flag, flag)}</span>'
    )


@st.cache_data
def _load_test_cases() -> list[dict]:
    return json.loads(Path("data/test_cases.json").read_text(encoding="utf-8"))


def _apply_sample_to_state(case: dict) -> None:
    st.session_state["donor_name"]    = case["donor_name"]
    st.session_state["donor_segment"] = case["donor_segment"]
    st.session_state["meeting_type"]  = case["meeting_type"]
    st.session_state["bullets_text"]  = "\n".join(case["bullets"])


st.set_page_config(page_title="AfterVisit", layout="wide")
st.title("AfterVisit")

# Initialize form defaults before any form widgets render.
st.session_state.setdefault("donor_segment", "mid_5k_10k")
st.session_state.setdefault("meeting_type", "cultivation")
st.session_state.setdefault("donor_name", "")
st.session_state.setdefault("bullets_text", "")

# Sample case dropdown sits just above the form. Forms don't rerun on inner
# widget changes, so the dropdown lives outside the form to drive
# auto-population via session_state.
sample_choice = st.selectbox(
    "Load sample case (optional)", SAMPLE_CHOICES, key="_sample_choice"
)
if sample_choice != st.session_state.get("_last_sample"):
    st.session_state["_last_sample"] = sample_choice
    case_id = SAMPLE_CHOICE_TO_ID.get(sample_choice)
    if case_id:
        case = next((c for c in _load_test_cases() if c["id"] == case_id), None)
        if case is not None:
            _apply_sample_to_state(case)

with st.form("input"):
    col1, col2 = st.columns(2)
    donor_name    = col1.text_input("Donor name", key="donor_name")
    donor_segment = col1.selectbox("Donor segment", DONOR_SEGMENTS, key="donor_segment")
    meeting_type  = col2.selectbox("Meeting type", MEETING_TYPES, key="meeting_type")
    bullets_text  = st.text_area("Bullets (one per line)", height=200, key="bullets_text")
    st.checkbox("I disclosed sensitive content", key="disclosed")
    submitted = st.form_submit_button("Generate")

if submitted:
    if not donor_name or not bullets_text.strip():
        st.error("Donor name and bullets are required.")
    else:
        bullets = [b.strip() for b in bullets_text.splitlines() if b.strip()]
        with st.spinner("Generating note and email..."):
            try:
                st.session_state["result"] = run(bullets, donor_name, donor_segment, meeting_type)
                st.session_state["filed_id"] = None
            except Exception as e:
                st.error(f"Generation failed: {e}")

result = st.session_state.get("result")
if result:
    left, right = st.columns(2)

    with left:
        st.subheader("Salesforce Note")
        flags = result["note"].get("sensitivity_flags") or []
        if flags:
            st.markdown("".join(_chip_html(f) for f in flags), unsafe_allow_html=True)
        st.json(result["note"])
        read_it = st.checkbox("I've read the note", key="read_it")
        if st.button("Approve and File", disabled=not read_it):
            sf = post_activity(result["note"])
            if sf.get("status") == "ok":
                st.session_state["filed_id"] = sf["id"]
                st.success(f"Filed: {sf['id']}")
            else:
                st.error(sf)

    with right:
        st.subheader("Thank-you Email")
        email_categories = detect_categories(result["email"])
        leak = sorted(set(flags) & set(email_categories))
        if leak:
            st.warning(
                f"⚠ Email contains content matching flagged "
                f"categories ({', '.join(leak)}) — review before copying."
            )
        st.markdown(result["email"])
        refs = result.get("references_used") or []
        st.caption(f"Refs used: {', '.join(refs) if refs else '(none)'}")

        info_flow = result.get("info_flow") or {}
        status = info_flow.get("status")
        if status:
            emoji, text, color = INFO_FLOW_BADGES.get(
                status, ("⚪", f"Info-flow: {status}", "#6b7280")
            )
            st.markdown(
                f'<span style="background:{color}; color:white;'
                f' padding:4px 10px; border-radius:12px;'
                f' font-size:0.85em; display:inline-block;">'
                f'{emoji} {text}</span>',
                unsafe_allow_html=True,
            )
            first_check = info_flow.get("first_check") or {}
            offending = first_check.get("offending_phrase")
            if first_check.get("leaked") and offending:
                st.caption(f'_Caught phrase:_ "{offending}"')

st.divider()
st.subheader("Recent activity log")
if ACTIVITY_LOG.exists():
    log = json.loads(ACTIVITY_LOG.read_text(encoding="utf-8"))
    for record in log[-5:]:
        subject = record["note"].get("subject", "")
        st.text(f"{record['posted_at']}  {record['id'][:8]}  {subject}")
else:
    st.caption("(no activity filed yet)")
