import streamlit as st


def inject_css():
    st.markdown(
        """
        <style>
          .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px; }
          .app-card {
              border: 1px solid rgba(49,51,63,.2);
              border-radius: 16px;
              padding: 16px;
              background: rgba(255,255,255,0.03);
              margin-bottom: 14px;
          }
          .muted { opacity: 0.75; }
          .tag {
              display: inline-block;
              padding: 2px 10px;
              border-radius: 999px;
              border: 1px solid rgba(49,51,63,.2);
              margin-right: 6px;
              margin-top: 6px;
              font-size: 0.8rem;
              opacity: 0.9;
          }
          .badge {
              display: inline-block;
              padding: 3px 10px;
              border-radius: 999px;
              font-size: 0.8rem;
              border: 1px solid rgba(49,51,63,.2);
              margin-left: 8px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def access_badge(access: str) -> str:
    if access == "Public":
        return "✅ Public"
    if access == "Member":
        return "⭐ Member"
    if access == "Admin":
        return "🛡️ Admin"
    if access == "Coming Soon":
        return "🚧 Coming Soon"
    return access


def get_dev_mode() -> bool:
    # session toggle first; fallback to query param ?dev=1
    if "dev_mode" in st.session_state:
        return bool(st.session_state["dev_mode"])
    qp = st.query_params
    return str(qp.get("dev", "0")).lower() in ("1", "true", "yes", "on")


def app_open_url(app: dict) -> str:
    """
    Picks local_url when dev_mode=True, otherwise hosted_url.
    Returns "" if none.
    """
    dev = get_dev_mode()
    url = (app.get("local_url") if dev else app.get("hosted_url")) or ""
    return url.strip()


def filter_apps(apps, category, access_levels, search_text):
    out = []
    s = (search_text or "").strip().lower()

    for a in apps:
        if category != "All" and a.get("category") != category:
            continue
        if access_levels and a.get("access") not in access_levels:
            continue
        if s:
            blob = " ".join(
                [
                    a.get("name", ""),
                    a.get("summary", ""),
                    a.get("category", ""),
                    " ".join(a.get("tags", [])),
                ]
            ).lower()
            if s not in blob:
                continue
        out.append(a)
    return out


def app_card(app: dict, key_prefix: str = "card"):
    st.markdown('<div class="app-card">', unsafe_allow_html=True)

    title = f"**{app.get('name','')}** <span class='badge'>{access_badge(app.get('access',''))}</span>"
    st.markdown(title, unsafe_allow_html=True)
    st.markdown(f"<div class='muted'>{app.get('summary','')}</div>", unsafe_allow_html=True)

    tags_html = "".join([f"<span class='tag'>{t}</span>" for t in app.get("tags", [])])
    st.markdown(tags_html, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1])

    k_details = f"{key_prefix}_details_{app['id']}"
    k_web = f"{key_prefix}_web_{app['id']}"
    k_dl = f"{key_prefix}_dl_{app['id']}"
    k_docs = f"{key_prefix}_docs_{app['id']}"

    with c1:
        if st.button("Details", key=k_details):
            st.session_state["selected_app_id"] = app["id"]
            st.switch_page("pages/1_Apps.py")

    with c2:
        url = app_open_url(app)
        if url and app.get("access") != "Coming Soon":
            st.link_button("Open Web", url, key=k_web)
        else:
            st.button("Open Web", disabled=True, key=k_web)

    with c3:
        if app.get("download_url"):
            st.link_button("Download", app["download_url"], key=k_dl)
        else:
            st.button("Download", disabled=True, key=k_dl)

    if app.get("docs_url"):
        st.link_button("Docs", app["docs_url"], key=k_docs)

    st.markdown("</div>", unsafe_allow_html=True)