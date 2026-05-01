import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import json
from io import BytesIO

BASE = Path(__file__).resolve().parents[2]  # .../apps/data_analytics_tool
sys.path.insert(0, str(BASE / "shared"))

from analytics_core import get_conn, init_db  # type: ignore

st.set_page_config(page_title="Export • Data Analytics Tool", page_icon="📦", layout="wide")
st.title("Export")
st.caption("Download the currently selected table as CSV/Excel, plus a JSON summary.")

conn = get_conn()
init_db(conn)

table = st.session_state.get("da_table_name", "")
contains = st.session_state.get("da_contains", "")

if not table:
    st.info("No table selected yet. Go to **Preview + KPIs** first.")
    st.stop()

st.markdown(f"### Selected table: **{table}**")

respect_filter = st.checkbox("Apply the current contains-filter to export", value=False, key="export_apply_filter")
limit = st.number_input("Row limit for export (0 = no limit)", min_value=0, max_value=500000, value=0, step=1000, key="export_limit")

st.divider()

# Load data
try:
    sql = f'SELECT * FROM "{table}"'
    if int(limit) > 0:
        sql += f" LIMIT {int(limit)}"

    df = pd.read_sql_query(sql, conn)

    if respect_filter and str(contains).strip():
        txt = str(contains).strip()
        mask = df.astype(str).apply(lambda s: s.str.contains(txt, case=False, na=False))
        df = df[mask.any(axis=1)]

    st.success(f"Ready to export {df.shape[0]:,} rows × {df.shape[1]:,} cols")
    st.dataframe(df.head(50), use_container_width=True)

    # Exports
    st.markdown("## Download")

    # CSV
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV",
        data=csv_bytes,
        file_name=f"{table}_export.csv",
        mime="text/csv",
        key="dl_csv",
    )

    # Excel
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="data")

    st.download_button(
        "Download Excel",
        data=out.getvalue(),
        file_name=f"{table}_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dl_xlsx",
    )

    # JSON Summary
    summary = {
        "table": table,
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "columns": [
            {
                "name": c,
                "dtype": str(df[c].dtype),
                "missing": int(df[c].isna().sum()),
                "unique": int(df[c].nunique(dropna=True)),
            }
            for c in df.columns
        ],
    }

    st.download_button(
        "Download Summary JSON",
        data=json.dumps(summary, indent=2),
        file_name=f"{table}_summary.json",
        mime="application/json",
        key="dl_json",
    )

except Exception as e:
    st.error(f"Export failed: {e}")