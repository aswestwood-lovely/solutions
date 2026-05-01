import streamlit as st

st.set_page_config(page_title="Data Analytics Tool (Web)", page_icon="📈", layout="wide")

st.title("Data Analytics Tool (Web)")
st.caption("Streamlit UI using your analytics_core + SQLite pipeline (import → preview → KPIs → chart).")

st.markdown("### Pages")
st.write("- **Import**: upload a file into SQLite (dataset + staging table)")
st.write("- **Preview + KPIs**: choose dataset/table, filter, preview, KPIs")
st.write("- **Charts**: quick bar chart (category vs SUM(numeric))")

st.info("Start on **Import**.")