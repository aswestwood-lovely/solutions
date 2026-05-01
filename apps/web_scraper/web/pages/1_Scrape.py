import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
import json
from io import BytesIO
import time

st.set_page_config(page_title="Scrape • Web Scraper", page_icon="🕷️", layout="wide")
st.title("Scrape")
st.caption("Respect robots.txt, fetch HTML, extract links and optional CSS-selector fields.")

DEFAULT_UA = "Lovely1SolutionsWebScraper/1.0 (+https://example.com)"

def fetch(url: str, ua: str, timeout: int = 20):
    headers = {"User-Agent": ua}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r

def robots_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}/robots.txt"

def check_robots_txt(url: str, ua: str) -> tuple[bool, str]:
    """
    Very simple robots.txt check:
    - Fetches robots.txt and displays it.
    - Does NOT fully implement parsing rules (we can add real parser later).
    Returns (fetched_ok, text)
    """
    try:
        r = requests.get(robots_url(url), headers={"User-Agent": ua}, timeout=15)
        if r.status_code >= 400:
            return False, f"robots.txt not found (HTTP {r.status_code})."
        return True, r.text
    except Exception as e:
        return False, f"robots.txt check failed: {e}"

st.markdown("### Target")
c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    url = st.text_input("URL", placeholder="https://example.com", key="ws_url")
with c2:
    ua = st.text_input("User-Agent", value=DEFAULT_UA, key="ws_ua")
with c3:
    delay = st.number_input("Delay seconds (between requests)", min_value=0.0, max_value=10.0, value=0.5, step=0.5, key="ws_delay")

st.markdown("### robots.txt")
if url.strip():
    ok, txt = check_robots_txt(url.strip(), ua.strip())
    if ok:
        st.success("robots.txt fetched (review before scraping).")
        st.code(txt[:3000])
    else:
        st.warning(txt)

st.divider()

st.markdown("### Optional: CSS selector fields")
st.caption("Add fields like: name=price selector=.price")

fields = st.text_area(
    "Fields (one per line: field_name=css_selector)",
    value="",
    height=120,
    key="ws_fields",
)

def parse_fields(text: str):
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        name, sel = line.split("=", 1)
        name, sel = name.strip(), sel.strip()
        if name and sel:
            out.append((name, sel))
    return out

field_list = parse_fields(fields)

st.divider()

run = st.button("Fetch & Extract", type="primary", disabled=not url.strip(), key="ws_run")

if run:
    target = url.strip()
    time.sleep(float(delay))

    try:
        r = fetch(target, ua.strip())
        html = r.text
        soup = BeautifulSoup(html, "lxml")

        title = soup.title.text.strip() if soup.title and soup.title.text else ""

        # Links
        links = []
        for a in soup.select("a[href]"):
            href = a.get("href", "").strip()
            if not href:
                continue
            full = urljoin(target, href)
            links.append(full)

        links = list(dict.fromkeys(links))  # de-dupe preserve order

        # Field extraction (first match text)
        extracted = {"url": target, "title": title, "link_count": len(links)}
        for name, sel in field_list:
            node = soup.select_one(sel)
            extracted[name] = node.get_text(strip=True) if node else ""

        st.success("Fetched and extracted.")
        st.json(extracted)

        st.markdown("### Links (preview)")
        link_df = pd.DataFrame({"link": links[:200]})
        st.dataframe(link_df, use_container_width=True, hide_index=True)

        # Save in session for Export page
        st.session_state["ws_extracted"] = extracted
        st.session_state["ws_links"] = links

    except Exception as e:
        st.error(f"Fetch failed: {e}")

st.divider()

st.markdown("### Export (quick)")
extracted = st.session_state.get("ws_extracted")
links = st.session_state.get("ws_links", [])

if extracted:
    # JSON
    st.download_button(
        "Download JSON",
        data=json.dumps({"extracted": extracted, "links": links}, indent=2),
        file_name="scrape_result.json",
        mime="application/json",
        key="ws_dl_json",
    )

    # CSV/Excel: links
    df_links = pd.DataFrame({"link": links})
    csv_bytes = df_links.to_csv(index=False).encode("utf-8")
    st.download_button("Download Links CSV", data=csv_bytes, file_name="links.csv", mime="text/csv", key="ws_dl_csv")

    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        pd.DataFrame([extracted]).to_excel(writer, index=False, sheet_name="extracted")
        df_links.to_excel(writer, index=False, sheet_name="links")
    st.download_button(
        "Download Excel",
        data=out.getvalue(),
        file_name="scrape_result.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="ws_dl_xlsx",
    )
else:
    st.info("Run Fetch & Extract to enable exports.")