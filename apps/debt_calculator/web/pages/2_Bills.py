import streamlit as st
import sys
from pathlib import Path
import pandas as pd

# --- Path setup so we can import shared core + app_state ---
BASE = Path(__file__).resolve().parents[2]  # .../apps/debt_calculator
sys.path.insert(0, str(BASE / "shared"))
sys.path.insert(0, str(BASE / "web"))  # so we can import app_state.py

from validators import validate_bill, find_duplicates, payoff_risk_flags

from app_state import (
    get_active_profile, list_profiles, set_active_profile,
    add_profile, rename_profile, delete_profile,
    load_section, save_section
)

st.set_page_config(page_title="Bills • Debt Calculator", page_icon="🧾", layout="wide")

st.title("Bills")
st.caption("Add, edit, and manage bills for the selected profile (persistent storage).")

# -----------------------------
# Persistence helpers
# -----------------------------
def load_bills() -> list[dict]:
    payload = load_section("bills")
    return (payload or {}).get("items", []) or []

def save_bills(items: list[dict]) -> None:
    save_section("bills", {"items": items})

# -----------------------------
# Profile controls
# -----------------------------
profiles_list = list_profiles()
active = get_active_profile()

name_to_id = {p.name: p.id for p in profiles_list}
names = [p.name for p in profiles_list]
current_index = names.index(active.name) if active.name in names else 0

st.subheader("Profile")
colp1, colp2, colp3, colp4 = st.columns([2, 1, 1, 1])

with colp1:
    selected_name = st.selectbox("Active profile", names, index=current_index, key="profile_select")
    selected_id = name_to_id[selected_name]
    if selected_id != active.id:
        set_active_profile(selected_id)
        st.session_state.pop("bills_cache", None)
        st.rerun()

with colp2:
    new_name = st.text_input("New profile name", value="", placeholder="e.g., Household", key="profile_new_name")
    if st.button("Add Profile", key="profile_add_btn"):
        add_profile((new_name or "New Profile").strip())
        st.session_state.pop("bills_cache", None)
        st.rerun()

with colp3:
    rename_to = st.text_input("Rename active to", value="", placeholder="New name", key="profile_rename_to")
    if st.button("Rename", key="profile_rename_btn"):
        rename_profile(active.id, (rename_to or active.name).strip())
        st.rerun()

with colp4:
    if st.button("Delete Active", key="profile_delete_btn"):
        try:
            delete_profile(active.id)
            st.session_state.pop("bills_cache", None)
            st.rerun()
        except Exception as e:
            st.error(str(e))

st.divider()

# -----------------------------
# Load bills once per profile (cache in session_state)
# -----------------------------
if "bills_cache" not in st.session_state:
    st.session_state["bills_cache"] = load_bills()

bills = st.session_state["bills_cache"]

st.markdown("### Data Health Check")

# Validate + normalize all bills
cleaned_all = []
all_errors = []
for i, b in enumerate(bills):
    ok, errs, cleaned = validate_bill(b)
    cleaned_all.append(cleaned)
    if not ok:
        all_errors.append((i, errs))

# Auto-normalize in memory (and persist) if anything changed shape
if cleaned_all != bills:
    bills[:] = cleaned_all
    save_bills(bills)

dups = find_duplicates(bills)
risks = payoff_risk_flags(bills)

if all_errors:
    st.error("Some bills have validation issues:")
    for i, errs in all_errors:
        st.write(f"- Row {i}: " + "; ".join(errs))

if dups:
    st.warning("Duplicate bill names detected (case/spacing ignored):")
    for k, idxs in dups.items():
        st.write(f"- **{k}** appears at rows: {idxs}")

if risks:
    st.warning("Payoff risk flags:")
    for w in risks:
        st.write(f"- {w}")

if (not all_errors) and (not dups) and (not risks):
    st.success("Looks good — no obvious issues detected.")

st.divider()

# -----------------------------
# Add Bill form (INCLUDING payoff fields)
# -----------------------------
st.markdown("### Add a bill")

with st.form("add_bill_form", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        name = st.text_input("Bill name *", key="add_name")
        amount = st.number_input("Balance/Amount *", min_value=0.0, step=10.0, format="%.2f", key="add_amount")
    with c2:
        due_day = st.number_input("Due day (1-31)", min_value=1, max_value=31, value=1, key="add_due_day")
        apr = st.number_input("APR % (optional)", min_value=0.0, step=0.25, format="%.2f", key="add_apr")
    with c3:
        min_payment = st.number_input("Min payment (optional)", min_value=0.0, step=10.0, format="%.2f", key="add_min_payment")
        notes = st.text_input("Notes (optional)", key="add_notes")

    st.divider()
    st.markdown("#### Payoff settings (optional)")

    p1, p2, p3 = st.columns(3)
    with p1:
        include_in_strategy = st.checkbox("Include in payoff strategy", value=True, key="add_include_in_strategy")
        status = st.selectbox("Status", ["Current", "Delinquent", "Collections", "Paid"], index=0, key="add_status")
    with p2:
        planned_payment = st.number_input("Planned payment", min_value=0.0, step=10.0, format="%.2f", key="add_planned_payment")
        custom_order = st.number_input("Custom order (lower = earlier)", min_value=1, max_value=999999, value=999999, key="add_custom_order")
    with p3:
        override_mode = st.selectbox("Override mode", ["None", "Payment", "Target Months"], index=0, key="add_override_mode")

        override_value = 0.0
        override_months = 12
        if override_mode == "Payment":
            override_value = st.number_input("Override payment", min_value=0.0, step=10.0, format="%.2f", key="add_override_payment")
        elif override_mode == "Target Months":
            override_months = st.number_input("Target months", min_value=1, max_value=600, value=12, key="add_override_months")

    submitted = st.form_submit_button("Add bill")
    if submitted:
        if not name.strip():
            st.error("Bill name is required.")
        elif amount <= 0:
            st.error("Amount must be greater than 0.")
        else:
            override = {}
            if override_mode == "Payment":
                override = {"payment": float(override_value)}
            elif override_mode == "Target Months":
                override = {"target_months": int(override_months)}

            bills.append(
                {
                    "name": name.strip(),
                    "amount": float(amount),
                    "due_day": int(due_day),
                    "apr": float(apr),
                    "min_payment": float(min_payment),
                    "notes": notes.strip(),

                    # payoff fields
                    "include_in_strategy": bool(include_in_strategy),
                    "planned_payment": float(planned_payment) if planned_payment > 0 else float(min_payment),
                    "status": status,
                    "override": override,
                    "custom_order": int(custom_order),
                }
            )
            save_bills(bills)
            st.success("Bill added.")
            st.rerun()

st.divider()

# -----------------------------
# Bills table + edit/delete
# -----------------------------
st.markdown("### Current bills")

if not bills:
    st.info("No bills yet. Add one above.")
    st.stop()

df = pd.DataFrame(bills)
st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown("#### Edit / Delete")

idx = st.number_input(
    "Select bill # (row index)",
    min_value=0,
    max_value=len(bills) - 1,
    value=0,
    key="edit_row_index",
)

selected = bills[int(idx)]
row_key = f"edit_{int(idx)}"

with st.form("edit_bill_form"):
    e1, e2, e3 = st.columns(3)

    with e1:
        ename = st.text_input("Bill name", value=selected.get("name", ""), key=f"{row_key}_name")
        eamount = st.number_input(
            "Balance/Amount",
            min_value=0.0,
            step=10.0,
            value=float(selected.get("amount", 0.0)),
            format="%.2f",
            key=f"{row_key}_amount",
        )
        einclude = st.checkbox(
            "Include in payoff strategy",
            value=bool(selected.get("include_in_strategy", True)),
            key=f"{row_key}_include",
        )

    with e2:
        edue = st.number_input(
            "Due day",
            min_value=1,
            max_value=31,
            value=int(selected.get("due_day", 1)),
            key=f"{row_key}_due_day",
        )
        eapr = st.number_input(
            "APR %",
            min_value=0.0,
            step=0.25,
            value=float(selected.get("apr", 0.0)),
            format="%.2f",
            key=f"{row_key}_apr",
        )
        estatus = st.selectbox(
            "Status",
            ["Current", "Delinquent", "Collections", "Paid"],
            index=["Current", "Delinquent", "Collections", "Paid"].index(
                selected.get("status", "Current") if selected.get("status", "Current") in ["Current", "Delinquent", "Collections", "Paid"] else "Current"
            ),
            key=f"{row_key}_status",
        )

    with e3:
        emin = st.number_input(
            "Min payment",
            min_value=0.0,
            step=10.0,
            value=float(selected.get("min_payment", 0.0)),
            format="%.2f",
            key=f"{row_key}_min_payment",
        )
        eplanned = st.number_input(
            "Planned payment",
            min_value=0.0,
            step=10.0,
            value=float(selected.get("planned_payment", selected.get("min_payment", 0.0) or 0.0)),
            format="%.2f",
            key=f"{row_key}_planned_payment",
        )
        enotes = st.text_input("Notes", value=selected.get("notes", ""), key=f"{row_key}_notes")

    st.divider()
    st.markdown("#### Overrides (optional)")

    cur_override = selected.get("override", {}) or {}
    cur_mode = "None"
    cur_payment = 0.0
    cur_months = 12

    if isinstance(cur_override, dict):
        if "payment" in cur_override:
            cur_mode = "Payment"
            cur_payment = float(cur_override.get("payment") or 0.0)
        elif "target_months" in cur_override:
            cur_mode = "Target Months"
            cur_months = int(cur_override.get("target_months") or 12)

    o1, o2, o3 = st.columns([1.2, 1, 1])

    with o1:
        override_mode_edit = st.selectbox(
            "Override mode",
            ["None", "Payment", "Target Months"],
            index=["None", "Payment", "Target Months"].index(cur_mode),
            key=f"{row_key}_override_mode",
        )

    with o2:
        override_payment = st.number_input(
            "Override payment",
            min_value=0.0,
            step=10.0,
            value=cur_payment,
            format="%.2f",
            disabled=(override_mode_edit != "Payment"),
            key=f"{row_key}_override_payment",
        )

    with o3:
        override_months = st.number_input(
            "Target months",
            min_value=1,
            max_value=600,
            value=cur_months,
            disabled=(override_mode_edit != "Target Months"),
            key=f"{row_key}_override_months",
        )

    st.divider()
    st.markdown("#### Custom strategy order (only used if Strategy = Custom)")
    custom_order = st.number_input(
        "Custom order (lower = earlier payoff target)",
        min_value=1,
        max_value=999999,
        value=int(selected.get("custom_order", 999999) or 999999),
        key=f"{row_key}_custom_order",
    )

    csave, cdel = st.columns([1, 1])
    save_clicked = csave.form_submit_button("Save changes")
    delete_clicked = cdel.form_submit_button("Delete bill")

    if save_clicked:
        override = {}
        if override_mode_edit == "Payment":
            override = {"payment": float(override_payment)}
        elif override_mode_edit == "Target Months":
            override = {"target_months": int(override_months)}

        bills[int(idx)] = {
            "name": ename.strip(),
            "amount": float(eamount),
            "due_day": int(edue),
            "apr": float(eapr),
            "min_payment": float(emin),
            "planned_payment": float(eplanned) if eplanned > 0 else float(emin),
            "include_in_strategy": bool(einclude),
            "status": estatus,
            "override": override,
            "custom_order": int(custom_order),
            "notes": enotes.strip(),
        }

        save_bills(bills)
        st.success("Saved.")
        st.rerun()

    if delete_clicked:
        bills.pop(int(idx))
        save_bills(bills)
        st.success("Deleted.")
        st.rerun()