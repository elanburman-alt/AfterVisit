import json

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


def _chip_html(flag: str) -> str:
    return (
        f'<span style="background:{FLAG_COLORS.get(flag, "#6b7280")};'
        f' color:white; padding:3px 10px; border-radius:12px;'
        f' font-size:0.85em; margin-right:6px; display:inline-block;">'
        f'{FLAG_LABELS.get(flag, flag)}</span>'
    )

st.set_page_config(page_title="AfterVisit", layout="wide")
st.title("AfterVisit")

with st.form("input"):
    col1, col2 = st.columns(2)
    donor_name    = col1.text_input("Donor name")
    donor_segment = col1.selectbox("Donor segment", DONOR_SEGMENTS, index=2)
    meeting_type  = col2.selectbox("Meeting type", MEETING_TYPES, index=1)
    bullets_text  = st.text_area("Bullets (one per line)", height=200)
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

st.divider()
st.subheader("Recent activity log")
if ACTIVITY_LOG.exists():
    log = json.loads(ACTIVITY_LOG.read_text(encoding="utf-8"))
    for record in log[-5:]:
        subject = record["note"].get("subject", "")
        st.text(f"{record['posted_at']}  {record['id'][:8]}  {subject}")
else:
    st.caption("(no activity filed yet)")
