# portfolio_web/streamlit_app.py

import streamlit as st
from data.apps import APPS
from components.ui import inject_css, app_card

st.set_page_config(
    page_title="Lovely1 Solutions • App Suite",
    page_icon="✨",
    layout="wide",
)

inject_css()

# Sidebar: Dev Mode toggle
with st.sidebar:
    st.session_state["dev_mode"] = st.toggle(
        "Local Dev Mode",
        value=st.session_state.get("dev_mode", True),
    )
    st.caption("Dev Mode uses localhost ports. Turn off to use hosted URLs.")
    st.query_params["dev"] = "1" if st.session_state["dev_mode"] else "0"

st.title("Lovely1 Solutions")
st.subheader("A practical suite of apps for **finance**, **utilities**, and more.")

a, b, c = st.columns([1.4, 1, 1])
with a:
    st.write(
        "Use the portfolio to open each web app (local dev now, hosted later), "
        "or download desktop builds when available."
    )
    x, y = st.columns(2)
    with x:
        if st.button("Explore Apps"):
            st.switch_page("pages/1_Apps.py")
    with y:
        st.button("Sign In (coming soon)", disabled=True)

with b:
    st.markdown("### What you get")
    st.write("✅ Consistent UI patterns")
    st.write("✅ Exports where applicable")
    st.write("✅ Desktop + Web versions")

with c:
    st.markdown("### Member perks")
    st.write("⭐ Discounts (future store)")
    st.write("⭐ Saved profiles/settings")
    st.write("⭐ Expanded features")

st.divider()

st.markdown("## App Catalog (Grouped)")
by_cat = {}
for a in APPS:
    by_cat.setdefault(a["category"], []).append(a)

for cat in sorted(by_cat.keys()):
    st.markdown(f"### {cat}")
    items = sorted(by_cat[cat], key=lambda x: x["name"])
    cols = st.columns(3)
    for i, app in enumerate(items):
        with cols[i % 3]:
            app_card(app)

st.divider()
st.caption("© Lovely1 Solutions • Built with Streamlit")