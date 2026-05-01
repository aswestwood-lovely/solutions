import streamlit as st
import pandas as pd

st.set_page_config(page_title="Explore • Data Analytics Tool", page_icon="🔎", layout="wide")
st.title("Explore")
st.caption("Upload CSV/Excel, preview data, and view quick profiling stats.")

uploaded = st.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx"], key="upload_data")

def load_df(file):
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file, engine="openpyxl")

if uploaded:
    try:
        df = load_df(uploaded)
        st.session_state["df"] = df  # store for other pages

        st.success(f"Loaded {df.shape[0]:,} rows × {df.shape[1]:,} columns")

        st.markdown("### Preview")
        st.dataframe(df.head(50), use_container_width=True)

        st.divider()
        st.markdown("### Column summary")

        summary = pd.DataFrame({
            "column": df.columns,
            "dtype": [str(df[c].dtype) for c in df.columns],
            "missing": [int(df[c].isna().sum()) for c in df.columns],
            "missing_%": [float(df[c].isna().mean() * 100) for c in df.columns],
            "unique": [int(df[c].nunique(dropna=True)) for c in df.columns],
        })
        st.dataframe(summary, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("### Basic stats (numeric)")
        num = df.select_dtypes(include="number")
        if num.shape[1] == 0:
            st.info("No numeric columns detected.")
        else:
            st.dataframe(num.describe().T, use_container_width=True)

    except Exception as e:
        st.error(f"Could not load file: {e}")
else:
    st.info("Upload a file to begin.")