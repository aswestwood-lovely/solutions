import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parents[2]  # .../apps/data_analytics_tool
sys.path.insert(0, str(BASE / "shared"))

from analytics_core import get_conn, init_db, list_datasets, list_tables_for_dataset  # type: ignore

st.set_page_config(page_title="Charts • Data Analytics Tool", page_icon="📊", layout="wide")
st.title("Charts")
st.caption("Quick chart: Top categories by SUM(numeric).")

conn = get_conn()
init_db(conn)

# -----------------------------
# State defaults
# -----------------------------
st.session_state.setdefault("chart_dataset_key", "")
st.session_state.setdefault("chart_table_name", "")
st.session_state.setdefault("chart_cat_col", "")
st.session_state.setdefault("chart_num_col", "")
st.session_state.setdefault("chart_topn", 15)
st.session_state.setdefault("chart_limit", 2000)

# -----------------------------
# Dataset + Table selection (remembered)
# -----------------------------
datasets = list_datasets(conn=conn) or []
if not datasets:
    st.info("No datasets found. Go to **Import** first.")
    st.stop()

ds_labels = [f"{d.get('name','')} ({d.get('dataset_key','')})" for d in datasets]

default_ds_index = 0
if st.session_state["chart_dataset_key"]:
    for i, d in enumerate(datasets):
        if d.get("dataset_key") == st.session_state["chart_dataset_key"]:
            default_ds_index = i
            break

ds_choice = st.selectbox("Dataset", ds_labels, index=default_ds_index, key="chart_ds_select")
ds = datasets[ds_labels.index(ds_choice)]
dataset_key = ds.get("dataset_key")
st.session_state["chart_dataset_key"] = dataset_key

tables = list_tables_for_dataset(dataset_key, conn=conn) or []
if not tables:
    st.warning("No tables found for this dataset.")
    st.stop()

default_tbl_index = 0
if st.session_state["chart_table_name"] in tables:
    default_tbl_index = tables.index(st.session_state["chart_table_name"])

table = st.selectbox("Table", tables, index=default_tbl_index, key="chart_table_select")
st.session_state["chart_table_name"] = table

limit = st.number_input(
    "Row limit for chart sampling",
    min_value=100,
    max_value=20000,
    value=int(st.session_state["chart_limit"]),
    step=100,
    key="chart_limit_input",
)
st.session_state["chart_limit"] = int(limit)

st.divider()

# -----------------------------
# Load data
# -----------------------------
try:
    df = pd.read_sql_query(f'SELECT * FROM "{table}" LIMIT {int(limit)}', conn)
except Exception as e:
    st.error(f"Could not load table: {e}")
    st.stop()

obj_cols = [c for c in df.columns if df[c].dtype == object]
num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

if not obj_cols or not num_cols:
    st.info("Need at least one text column and one numeric column to chart.")
    st.stop()

# -----------------------------
# Remembered column choices
# -----------------------------
def pick_index(options: list[str], saved: str) -> int:
    if saved in options:
        return options.index(saved)
    return 0

cat_idx = pick_index(obj_cols, st.session_state.get("chart_cat_col", ""))
num_idx = pick_index(num_cols, st.session_state.get("chart_num_col", ""))

cat_col = st.selectbox("Category (text) column", obj_cols, index=cat_idx, key="chart_cat_select")
num_col = st.selectbox("Numeric column", num_cols, index=num_idx, key="chart_num_select")

st.session_state["chart_cat_col"] = cat_col
st.session_state["chart_num_col"] = num_col

top_n = st.number_input(
    "Top N categories",
    min_value=5,
    max_value=50,
    value=int(st.session_state["chart_topn"]),
    step=1,
    key="chart_topn_input",
)
st.session_state["chart_topn"] = int(top_n)

st.divider()

# -----------------------------
# Chart
# -----------------------------
try:
    g = df.groupby(cat_col)[num_col].sum().sort_values(ascending=False).head(int(top_n))

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.bar(g.index.astype(str), g.values)
    ax.set_title(f"Top {len(g)} {cat_col} by SUM({num_col})")
    ax.tick_params(axis="x", labelrotation=45)

    st.pyplot(fig, clear_figure=True)

except Exception as e:
    st.error(f"Chart failed: {e}")