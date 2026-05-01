import streamlit as st
import pandas as pd

st.set_page_config(page_title="Charts • Data Analytics Tool", page_icon="📊", layout="wide")
st.title("Charts")
st.caption("Quick charts based on your uploaded dataset.")

df = st.session_state.get("df")
if df is None or not isinstance(df, pd.DataFrame):
    st.info("Upload a dataset on the **Explore** page first.")
    st.stop()

st.markdown("### Choose columns")
cols = list(df.columns)
x = st.selectbox("X column", cols, index=0, key="chart_x")
y = st.selectbox("Y column (optional)", ["(none)"] + cols, index=0, key="chart_y")

st.divider()
st.markdown("### Chart")

if y == "(none)":
    # Histogram-like bar of value counts (top 50)
    vc = df[x].value_counts(dropna=False).head(50)
    st.bar_chart(vc)
    st.caption("Showing top 50 value counts.")
else:
    # Scatter if both numeric, otherwise grouped mean if possible
    if pd.api.types.is_numeric_dtype(df[x]) and pd.api.types.is_numeric_dtype(df[y]):
        chart_df = df[[x, y]].dropna()
        st.scatter_chart(chart_df, x=x, y=y)
    else:
        # Group-by average (if y numeric)
        if not pd.api.types.is_numeric_dtype(df[y]):
            st.warning("For non-numeric Y, choose a numeric Y to chart grouped averages.")
        else:
            g = df[[x, y]].dropna().groupby(x)[y].mean().sort_values(ascending=False).head(50)
            st.bar_chart(g)
            st.caption("Showing top 50 grouped averages.")