import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import date

BASE = Path(__file__).resolve().parents[1]  # .../apps/iou_manager
# (If you later add shared_lib imports, add paths here.)

st.set_page_config(page_title="Loan Manager (Web)", page_icon="🤝", layout="wide")

st.title("IOU / Personal Loan Manager (Web)")
st.caption("Track loans, payments, and balances. (Web build starter)")

# --- Minimal persistent storage (local .data) ---
DATA_DIR = BASE / "web" / ".data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOANS_PATH = DATA_DIR / "loans.json"

def load_loans():
    if LOANS_PATH.exists():
        import json
        return json.loads(LOANS_PATH.read_text(encoding="utf-8")) or []
    return []

def save_loans(loans):
    import json
    LOANS_PATH.write_text(json.dumps(loans, indent=2), encoding="utf-8")

loans = load_loans()

# --- Add loan form ---
st.subheader("Add a Loan")

with st.form("add_loan", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        borrower = st.text_input("Borrower name *", key="add_borrower")
        principal = st.number_input("Principal *", min_value=0.0, step=50.0, format="%.2f", key="add_principal")
    with c2:
        apr = st.number_input("APR %", min_value=0.0, step=0.25, format="%.2f", key="add_apr")
        start = st.date_input("Start date", value=date.today(), key="add_start")
    with c3:
        term_months = st.number_input("Term months (optional)", min_value=0, max_value=600, value=0, key="add_term")
        notes = st.text_input("Notes", key="add_notes")

    submitted = st.form_submit_button("Add Loan")
    if submitted:
        if not borrower.strip():
            st.error("Borrower name is required.")
        elif principal <= 0:
            st.error("Principal must be > 0.")
        else:
            loans.append({
                "borrower": borrower.strip(),
                "principal": float(principal),
                "apr": float(apr),
                "start_date": start.isoformat(),
                "term_months": int(term_months),
                "notes": notes.strip(),
                "payments": [],  # list of {"date": "...", "amount": 123.45}
            })
            save_loans(loans)
            st.success("Loan added.")
            st.rerun()

st.divider()

# --- Loans table (no IDs shown) ---
st.subheader("Loans")

if not loans:
    st.info("No loans yet. Add one above.")
    st.stop()

df = pd.DataFrame([{
    "borrower": L["borrower"],
    "principal": L["principal"],
    "apr": L["apr"],
    "start_date": L["start_date"],
    "term_months": L.get("term_months", 0),
    "payments_count": len(L.get("payments", [])),
    "notes": L.get("notes", ""),
} for L in loans])

st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()

# --- Record payment ---
st.subheader("Record a Payment")

idx = st.number_input("Select loan # (row index)", min_value=0, max_value=len(loans)-1, value=0, key="pay_idx")
loan = loans[int(idx)]

p1, p2, p3 = st.columns(3)
with p1:
    st.write(f"**Borrower:** {loan['borrower']}")
with p2:
    st.write(f"**Principal:** ${loan['principal']:,.2f}")
with p3:
    st.write(f"**APR:** {loan['apr']:,.2f}%")

with st.form("add_payment", clear_on_submit=True):
    pay_date = st.date_input("Payment date", value=date.today(), key="pay_date")
    pay_amt = st.number_input("Payment amount", min_value=0.0, step=25.0, format="%.2f", key="pay_amt")
    pay_submit = st.form_submit_button("Add Payment")
    if pay_submit:
        if pay_amt <= 0:
            st.error("Payment must be > 0.")
        else:
            loan.setdefault("payments", []).append({"date": pay_date.isoformat(), "amount": float(pay_amt)})
            save_loans(loans)
            st.success("Payment recorded.")
            st.rerun()

st.divider()

# --- Simple balance calculation (principal - sum(payments)) ---
paid = sum(float(p["amount"]) for p in loan.get("payments", []))
remaining = max(0.0, float(loan["principal"]) - paid)

st.subheader("Loan Summary")
m1, m2, m3 = st.columns(3)
m1.metric("Total Paid", f"${paid:,.2f}")
m2.metric("Remaining (simple)", f"${remaining:,.2f}")
m3.metric("Payments", f"{len(loan.get('payments', []))}")

if loan.get("payments"):
    pay_df = pd.DataFrame(loan["payments"])
    st.dataframe(pay_df, use_container_width=True, hide_index=True)