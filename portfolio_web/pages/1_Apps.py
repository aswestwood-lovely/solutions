# portfolio_web/pages/1_Apps.py

import streamlit as st
from data.apps import APPS
from components.ui import inject_css, app_card, filter_apps, app_open_url

st.set_page_config(page_title="Apps • Lovely1 Solutions", page_icon="🧩", layout="wide")
inject_css()

# Sidebar: Dev Mode toggle (keep consistent with Home)
with st.sidebar:
    st.session_state["dev_mode"] = st.toggle(
        "Local Dev Mode",
        value=st.session_state.get("dev_mode", True),
    )
    st.caption("Dev Mode uses localhost ports. Turn off to use hosted URLs.")
    st.query_params["dev"] = "1" if st.session_state["dev_mode"] else "0"

st.title("Apps")
st.caption("Search, filter, and open your tools. This page reads from portfolio_web/data/apps.py.")

cats = ["All"] + sorted({a["category"] for a in APPS})
access_options = sorted({a["access"] for a in APPS})

c1, c2, c3 = st.columns([1, 1.2, 1.6])
with c1:
    category = st.selectbox("Category", cats, index=0)
with c2:
    access_levels = st.multiselect("Access", access_options, default=access_options)
with c3:
    search = st.text_input("Search", placeholder="Type: loans, scraper, analytics, payoff...")

filtered = filter_apps(APPS, category, access_levels, search)

st.divider()

selected_id = st.session_state.get("selected_app_id")
selected = next((a for a in APPS if a["id"] == selected_id), None)

left, right = st.columns([1.3, 1])

with right:
    st.markdown("### App Details")
    if selected:
        st.markdown(f"**{selected['name']}**")
        st.write(selected["summary"])
        st.write(f"**Category:** {selected['category']}")
        st.write(f"**Access:** {selected['access']}")
        st.write("**Tags:** " + ", ".join(selected.get("tags", [])))

        st.divider()
        st.markdown("#### Actions")

        open_url = app_open_url(selected)
        if open_url and selected.get("access") != "Coming Soon":
            st.link_button("Open Web", open_url)
        else:
            st.button("Open Web", disabled=True)

        if selected.get("download_url"):
            st.link_button("Download Desktop", selected["download_url"])
        else:
            st.button("Download Desktop", disabled=True)

        if selected.get("docs_url"):
            st.link_button("Open Docs", selected["docs_url"])
        else:
            st.caption("Tip: Add docs_url in portfolio_web/data/apps.py")

    else:
        st.write("Click **Details** on any app card to see it here.")

with left:
    st.markdown(f"### Results ({len(filtered)})")
    if not filtered:
        st.warning("No apps match your filters.")
    else:
        cols = st.columns(2)
        for i, app in enumerate(filtered):
            with cols[i % 2]:
                app_card(app)