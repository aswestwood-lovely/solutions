import streamlit as st
import sys
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parents[2]  # .../apps/data_analytics_tool
sys.path.insert(0, str(BASE / "shared"))

from analytics_core import get_conn, init_db, list_datasets, list_tables_for_dataset, compute_kpis  # type: ignore

st.set_page_config(page_title="Preview + KPIs • Data Analytics Tool", page_icon="🔎", layout="wide")
st.title("Preview + KPIs")
st.caption("Choose dataset/table, preview rows, quick filter, and compute KPIs.")

conn = get_conn()
init_db(conn)

# -----------------------------
# State defaults
# -----------------------------
st.session_state.setdefault("da_dataset_key", "")
st.session_state.setdefault("da_table_name", "")
st.session_state.setdefault("da_contains", "")
st.session_state.setdefault("da_limit", 500)
st.session_state.setdefault("da_kpi_numeric_col", "(auto)")

# --- Load datasets ---
datasets = list_datasets(conn=conn) or []
if not datasets:
    st.info("No datasets found. Go to **Import** first.")
    st.stop()

# Build choices
ds_labels = [f"{d.get('name','')} ({d.get('dataset_key','')})" for d in datasets]
key_by_label = {lbl: datasets[i].get("dataset_key") for i, lbl in enumerate(ds_labels)}

# Pick dataset default
default_ds_index = 0
if st.session_state["da_dataset_key"]:
    for i, d in enumerate(datasets):
        if d.get("dataset_key") == st.session_state["da_dataset_key"]:
            default_ds_index = i
            break

ds_choice = st.selectbox("Dataset", ds_labels, index=default_ds_index, key="da_ds_select")
ds = datasets[ds_labels.index(ds_choice)]
dataset_key = ds.get("dataset_key")
st.session_state["da_dataset_key"] = dataset_key

# Tables for dataset
tables = list_tables_for_dataset(dataset_key, conn=conn) or []
if not tables:
    st.warning("No tables found for this dataset.")
    st.stop()

# Pick table default
default_tbl_index = 0
if st.session_state["da_table_name"] in tables:
    default_tbl_index = tables.index(st.session_state["da_table_name"])

table = st.selectbox("Table", tables, index=default_tbl_index, key="da_table_select")
st.session_state["da_table_name"] = table

# Quick contains filter (fetch then filter in pandas)
q = st.text_input("Quick filter (contains; applies to all columns)", value=st.session_state["da_contains"], key="da_contains_input")
st.session_state["da_contains"] = q

limit = st.number_input("Preview row limit", min_value=50, max_value=5000, value=int(st.session_state["da_limit"]), step=50, key="da_limit_input")
st.session_state["da_limit"] = int(limit)

st.divider()

# Load preview
try:
    df = pd.read_sql_query(f'SELECT * FROM "{table}" LIMIT {int(limit)}', conn)

    if q.strip():
        txt = q.strip()
        mask = df.astype(str).apply(lambda s: s.str.contains(txt, case=False, na=False))
        df = df[mask.any(axis=1)]

    # Hide internal IDs if present
    HIDE_COLS = ["id", "dataset_key", "table_key", "transaction_id", "txn_id"]
    df_show = df.drop(columns=[c for c in HIDE_COLS if c in df.columns], errors="ignore")

    st.markdown("### Preview")
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### KPIs")

    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    numeric_options = ["(auto)"] + num_cols

    # preserve selection if valid
    saved = st.session_state.get("da_kpi_numeric_col", "(auto)")
    idx = numeric_options.index(saved) if saved in numeric_options else 0

    numeric_col = st.selectbox("Numeric column for Sum/Avg", numeric_options, index=idx, key="da_kpi_numcol")
    st.session_state["da_kpi_numeric_col"] = numeric_col

    chosen = None if numeric_col == "(auto)" else numeric_col
    if chosen is None:
        chosen = num_cols[0] if num_cols else None

    kpis = compute_kpis(table, numeric_col=chosen, filters=None, conn=conn)

    m1, m2, m3 = st.columns(3)
    m1.metric("Count", f"{kpis.get('count', '—')}")
    m2.metric(f"Sum ({chosen or '—'})", f"{kpis.get('sum', '—') if chosen else '—'}")
    m3.metric(f"Avg ({chosen or '—'})", f"{kpis.get('avg', '—') if chosen else '—'}")

    st.caption("Tip: Go to **Export** to download the selected table.")

except Exception as e:
    st.error(f"Preview/KPI failed: {e}")