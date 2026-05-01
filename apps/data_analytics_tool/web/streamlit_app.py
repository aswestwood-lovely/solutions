import streamlit as st

st.set_page_config(page_title="Data Analytics Tool (Web)", page_icon="📈", layout="wide")

st.title("Data Analytics Tool (Web)")
st.caption("Upload data, explore, chart, and export.")

st.markdown("### Pages")
st.write("- Explore: upload + profile your dataset")
st.write("- Charts: quick visuals")
st.write("- Export: download cleaned data + summary")

st.info("Go to **Explore** to upload your first dataset.")