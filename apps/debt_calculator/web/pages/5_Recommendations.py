import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import date

BASE = Path(__file__).resolve().parents[2]  # .../apps/debt_calculator
sys.path.insert(0, str(BASE / "shared"))
sys.path.insert(0, str(BASE / "web"))

from app_state import get_active_profile, load_section
import core.payoff as payoff

st.set_page_config(page_title="Recommendations • Debt Calculator", page_icon="✅", layout="wide")

st.title("Recommendations")
st.caption("Actionable suggestions based on your debts, payoff plan settings, and risk checks.")

active = get_active_profile()
bills = (load_section("bills") or {}).get("items", []) or []

def bills_to_debts(bills_list):
    debts = []
    for i, b in enumerate(bills_list):
        debts.append(
            {
                "id": b.get("id", i),
                "name": b.get("name", f"Debt {i+1}"),
                "balance": float(b.get("amount", 0.0) or 0.0),
                "apr": float(b.get("apr", 0.0) or 0.0),
                "min_payment": float(b.get("min_payment", 0.0) or 0.0),
                "planned_payment": float(b.get("planned_payment", b.get("min_payment", 0.0) or 0.0) or 0.0),
                "include_in_strategy": bool(b.get("include_in_strategy", True)),
                "override": b.get("override", {}) or {},
                "status": b.get("status", "Current"),
                "custom_order": int(b.get("custom_order", 999999) or 999999),
            }
        )
    return debts

if not bills:
    st.info("No bills found. Add bills first.")
    st.stop()

debts = bills_to_debts(bills)

# Controls
c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])
with c1:
    strategy = st.selectbox("Strategy", ["Avalanche", "Snowball", "Custom"], index=0)
with c2:
    extra_payment = st.number_input("Extra monthly payment", min_value=0.0, step=25.0, value=0.0, format="%.2f")
with c3:
    status_override = st.checkbox("Status override priority", value=True)
with c4:
    start = st.date_input("Start date", value=date.today())

plan = payoff.monthly_plan(debts, strategy=strategy, extra_payment=float(extra_payment), status_override=bool(status_override))
plan_df = pd.DataFrame(plan)

# ---------- Recommendations ----------
st.divider()
st.subheader("Recommendations")

recs = []

# 1) Payment too low to cover interest (risk: never pays down)
for d in debts:
    if not d.get("include_in_strategy", True):
        continue
    if d["balance"] <= 0:
        continue
    apr = float(d.get("apr", 0.0))
    pay = float(d.get("planned_payment", 0.0))
    if apr > 0 and pay > 0:
        monthly_interest = d["balance"] * (apr / 100.0) / 12.0
        if pay <= monthly_interest:
            recs.append((
                "High priority",
                f"Increase payment for **{d['name']}**",
                f"Your planned payment (${pay:,.2f}) may not cover monthly interest (~${monthly_interest:,.2f})."
            ))

# 2) Missing min payments
for d in debts:
    if d["balance"] > 0 and float(d.get("min_payment", 0.0)) <= 0:
        recs.append((
            "High priority",
            f"Add a minimum payment for **{d['name']}**",
            "Payoff planning works best when each debt has a realistic minimum payment."
        ))

# 3) Status issues
for d in debts:
    status = str(d.get("status", "Current")).lower()
    if status in {"delinquent", "collections"}:
        recs.append((
            "Important",
            f"Stabilize **{d['name']}** (status: {d.get('status')})",
            "Consider contacting the creditor, confirming terms, and preventing fees before aggressive extra payments."
        ))

# 4) Strategy alignment
if strategy == "Avalanche":
    recs.append(("Tip", "Avalanche minimizes interest", "Focus stays on highest APR debt once minimums are covered."))
elif strategy == "Snowball":
    recs.append(("Tip", "Snowball builds momentum", "Focus stays on smallest balance first for quick wins."))

# 5) Extra allocation highlight
if not plan_df.empty:
    extra_alloc = plan_df[plan_df["kind"] == "extra"].copy()
    if not extra_alloc.empty:
        top = extra_alloc.sort_values("payment", ascending=False).head(1).iloc[0]
        recs.append((
            "Good move",
            f"Extra payment is primarily targeting **{top['name']}**",
            "Consistency month-to-month is what makes the plan work."
        ))

# 6) Overrides present
for d in debts:
    ov = d.get("override") or {}
    if isinstance(ov, dict) and ov:
        recs.append((
            "Note",
            f"Override active on **{d['name']}**",
            f"Override settings: {ov}. Make sure this matches your intent."
        ))

if not recs:
    st.success("No major issues detected. Your setup looks solid.")
else:
    for level, title, detail in recs:
        st.markdown(f"### {level}: {title}")
        st.write(detail)

st.divider()
st.subheader("Plan preview")
st.dataframe(plan_df, use_container_width=True, hide_index=True)