import streamlit as st
import pandas as pd
import json
from io import BytesIO

st.set_page_config(page_title="Export • Data Analytics Tool", page_icon="📦", layout="wide")
st.title("Export")
st.caption("Download your dataset and a quick summary.")

df = st.session_state.get("df")
if df is None or not isinstance(df, pd.DataFrame):
    st.info("Upload a dataset on the **Explore** page first.")
    st.stop()

st.markdown("### Export cleaned data")
st.caption("For now, this exports the dataset as-is. Next we can add cleaning rules (trim strings, fix dates, etc.).")

csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv_bytes, file_name="data_export.csv", mime="text/csv")

# Excel export
out = BytesIO()
with pd.ExcelWriter(out, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="data")
st.download_button(
    "Download Excel",
    data=out.getvalue(),
    file_name="data_export.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.divider()
st.markdown("### Export summary (JSON)")
summary = {
    "rows": int(df.shape[0]),
    "cols": int(df.shape[1]),
    "columns": [{"name": c, "dtype": str(df[c].dtype), "missing": int(df[c].isna().sum())} for c in df.columns],
}
st.download_button(
    "Download Summary JSON",
    data=json.dumps(summary, indent=2),
    file_name="data_summary.json",
    mime="application/json",
)