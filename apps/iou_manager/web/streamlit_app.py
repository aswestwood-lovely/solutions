import streamlit as st
from pathlib import Path
from datetime import date, datetime, timedelta
import json
import uuid
import pandas as pd

st.set_page_config(page_title="Loan Manager (Web)", page_icon="🤝", layout="wide")
st.title("IOU / Personal Loan Manager (Web)")
st.caption("Borrower directory + multiple loans per borrower + payment due tracking (web build).")

# -----------------------------
# Storage
# -----------------------------
BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / ".data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BORROWERS_PATH = DATA_DIR / "borrowers.json"
LOANS_PATH = DATA_DIR / "loans.json"


def _read_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_borrowers():
    return _read_json(BORROWERS_PATH, [])


def save_borrowers(borrowers):
    _write_json(BORROWERS_PATH, borrowers)


def load_loans():
    return _read_json(LOANS_PATH, [])


def save_loans(loans):
    _write_json(LOANS_PATH, loans)


def new_id() -> str:
    return uuid.uuid4().hex


# -----------------------------
# Payment math + due tracking
# -----------------------------
def calc_monthly_payment(principal: float, apr_pct: float, term_months: int) -> float:
    """
    Standard amortizing payment formula.
    If apr_pct == 0, payment = principal / term_months.
    """
    if term_months <= 0 or principal <= 0:
        return 0.0
    r = (apr_pct / 100.0) / 12.0
    if r <= 0:
        return principal / term_months
    return principal * (r * (1 + r) ** term_months) / ((1 + r) ** term_months - 1)


def _parse_date(s: str) -> date | None:
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def cycle_start_for(today: date) -> date:
    return today.replace(day=1)


def payment_made_this_cycle(loan: dict, today: date) -> bool:
    start = cycle_start_for(today)
    for p in loan.get("payments", []):
        d = _parse_date(p.get("date", ""))
        if d and start <= d <= today:
            return True
    return False


def due_date_for_month(today: date, due_day: int) -> date:
    d = min(max(1, int(due_day)), 31)
    next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    last_day = (next_month - timedelta(days=1)).day
    d = min(d, last_day)
    return today.replace(day=d)


def due_status(loan: dict, today: date) -> tuple[str, date]:
    """
    returns (status, due_date) where status is: 'Not due', 'Due', 'Overdue'
    """
    due_day = int(loan.get("payment_due_day", 1) or 1)
    due_dt = due_date_for_month(today, due_day)
    paid = payment_made_this_cycle(loan, today)

    if paid:
        return "Not due", due_dt
    if today < due_dt:
        return "Not due", due_dt
    if today == due_dt:
        return "Due", due_dt
    return "Overdue", due_dt


# -----------------------------
# Load data + migration
# -----------------------------
borrowers = load_borrowers()
loans = load_loans()

# Ensure borrowers have fields: id, name, email, phone
for b in borrowers:
    b.setdefault("email", "")
    b.setdefault("phone", "")

# Migration: if loans contain legacy "borrower" string instead of borrower_id, create/attach borrowers
borrower_name_to_id = {b.get("name", "").strip().lower(): b["id"] for b in borrowers if b.get("name")}
changed = False

for L in loans:
    # migrate borrower string -> borrower_id
    if "borrower_id" not in L:
        name = str(L.get("borrower", "")).strip()
        if name:
            key = name.lower()
            if key not in borrower_name_to_id:
                bid = new_id()
                borrowers.append({"id": bid, "name": name, "email": "", "phone": ""})
                borrower_name_to_id[key] = bid
                changed = True
            L["borrower_id"] = borrower_name_to_id[key]
            changed = True
        if "borrower" in L:
            L.pop("borrower", None)
            changed = True

    # ensure loan fields exist
    L.setdefault("id", new_id())
    L.setdefault("payments", [])
    L.setdefault("payment_due_day", 1)
    L.setdefault("agreed_payment", 0.0)
    L.setdefault("monthly_payment", 0.0)  # agreed or calculated
    L.setdefault("remind_email", True)
    L.setdefault("remind_text", False)

    # if monthly_payment missing/0, compute if term_months exists and agreed_payment is blank
    principal = float(L.get("principal", 0.0) or 0.0)
    apr = float(L.get("apr", 0.0) or 0.0)
    term_months = int(L.get("term_months", 0) or 0)
    agreed = float(L.get("agreed_payment", 0.0) or 0.0)
    if float(L.get("monthly_payment", 0.0) or 0.0) <= 0:
        if agreed > 0:
            L["monthly_payment"] = agreed
        elif term_months > 0:
            L["monthly_payment"] = float(calc_monthly_payment(principal, apr, term_months))
        changed = True

if changed:
    save_borrowers(borrowers)
    save_loans(loans)

borrowers_by_id = {b["id"]: b for b in borrowers}


def borrower_name(borrower_id: str) -> str:
    b = borrowers_by_id.get(borrower_id)
    return b["name"] if b else "(Unknown)"


# -----------------------------
# Tabs
# -----------------------------
tab_borrowers, tab_loans, tab_payments = st.tabs(["Borrowers", "Loans", "Payments"])

# =============================
# Borrowers tab
# =============================
with tab_borrowers:
    st.subheader("Borrower Directory")

    left, right = st.columns([1.2, 1])

    with left:
        st.markdown("### Add borrower")
        with st.form("add_borrower_form", clear_on_submit=True):
            bname = st.text_input("Borrower name *", key="add_borrower_name")
            email = st.text_input("Email (optional)", key="add_borrower_email")
            phone = st.text_input("Phone (optional)", key="add_borrower_phone")
            submitted = st.form_submit_button("Add borrower")
            if submitted:
                if not bname.strip():
                    st.error("Borrower name is required.")
                else:
                    exists = any(b["name"].strip().lower() == bname.strip().lower() for b in borrowers)
                    if exists:
                        st.warning("Borrower already exists (same name).")
                    else:
                        borrowers.append({
                            "id": new_id(),
                            "name": bname.strip(),
                            "email": email.strip(),
                            "phone": phone.strip(),
                        })
                        save_borrowers(borrowers)
                        st.success("Borrower added.")
                        st.rerun()

        st.divider()
        st.markdown("### Borrowers list (no IDs shown)")

        if not borrowers:
            st.info("No borrowers yet. Add one above.")
        else:
            bdf = pd.DataFrame([{"name": b["name"], "email": b.get("email", ""), "phone": b.get("phone", "")} for b in borrowers])
            st.dataframe(bdf, use_container_width=True, hide_index=True)

    with right:
        st.markdown("### Edit / Delete borrower")

        if not borrowers:
            st.info("Add a borrower first.")
        else:
            idx = st.number_input(
                "Select borrower # (row index)",
                min_value=0,
                max_value=len(borrowers) - 1,
                value=0,
                key="borrower_edit_idx",
            )
            b = borrowers[int(idx)]
            row_key = f"borrower_{b['id']}"

            with st.form("edit_borrower_form"):
                new_name = st.text_input("Borrower name", value=b.get("name", ""), key=f"{row_key}_name")
                new_email = st.text_input("Email", value=b.get("email", ""), key=f"{row_key}_email")
                new_phone = st.text_input("Phone", value=b.get("phone", ""), key=f"{row_key}_phone")
                save_btn = st.form_submit_button("Save")
                del_btn = st.form_submit_button("Delete")

                if save_btn:
                    if not new_name.strip():
                        st.error("Name cannot be empty.")
                    else:
                        borrowers[int(idx)]["name"] = new_name.strip()
                        borrowers[int(idx)]["email"] = new_email.strip()
                        borrowers[int(idx)]["phone"] = new_phone.strip()
                        save_borrowers(borrowers)
                        st.success("Updated.")
                        st.rerun()

                if del_btn:
                    borrower_id = b["id"]
                    has_loans = any(L.get("borrower_id") == borrower_id for L in loans)
                    if has_loans:
                        st.error("Cannot delete borrower: borrower has existing loans. Delete or reassign loans first.")
                    else:
                        borrowers.pop(int(idx))
                        save_borrowers(borrowers)
                        st.success("Deleted.")
                        st.rerun()

# =============================
# Loans tab
# =============================
with tab_loans:
    st.subheader("Loans")

    if not borrowers:
        st.info("Add a borrower first (Borrowers tab).")
        st.stop()

    left, right = st.columns([1.25, 1])

    with left:
        st.markdown("### Add loan")

        borrower_names = [b["name"] for b in borrowers]
        name_to_id = {b["name"]: b["id"] for b in borrowers}

        with st.form("add_loan_form", clear_on_submit=True):
            bsel = st.selectbox("Borrower *", borrower_names, key="loan_add_borrower")
            principal = st.number_input("Principal *", min_value=0.0, step=50.0, format="%.2f", key="loan_add_principal")
            apr = st.number_input("APR %", min_value=0.0, step=0.25, format="%.2f", key="loan_add_apr")

            cols = st.columns(3)
            with cols[0]:
                start = st.date_input("Start date", value=date.today(), key="loan_add_start")
            with cols[1]:
                term_months = st.number_input("Term months (optional)", min_value=0, max_value=600, value=0, key="loan_add_term")
            with cols[2]:
                due_day = st.number_input("Agreed payment day (1–31)", min_value=1, max_value=31, value=1, key="loan_add_due_day")

            agreed_payment = st.number_input(
                "Agreed monthly payment (optional)",
                min_value=0.0,
                step=25.0,
                format="%.2f",
                key="loan_add_agreed_payment",
            )

            # preview the payment that will be used
            preview_payment = float(agreed_payment) if agreed_payment > 0 else (
                float(calc_monthly_payment(float(principal), float(apr), int(term_months))) if int(term_months) > 0 else 0.0
            )
            st.caption(f"Monthly payment used: ${preview_payment:,.2f}")

            r1, r2 = st.columns(2)
            with r1:
                remind_email = st.checkbox("Email reminder", value=True, key="loan_add_remind_email")
            with r2:
                remind_text = st.checkbox("Text reminder", value=False, key="loan_add_remind_text")

            notes = st.text_input("Notes", key="loan_add_notes")
            submitted = st.form_submit_button("Add loan")

            if submitted:
                if principal <= 0:
                    st.error("Principal must be > 0.")
                else:
                    monthly_payment = float(agreed_payment) if agreed_payment > 0 else 0.0
                    if monthly_payment <= 0 and int(term_months) > 0:
                        monthly_payment = float(calc_monthly_payment(float(principal), float(apr), int(term_months)))

                    loans.append({
                        "id": new_id(),
                        "borrower_id": name_to_id[bsel],
                        "principal": float(principal),
                        "apr": float(apr),
                        "start_date": start.isoformat(),
                        "term_months": int(term_months),
                        "payment_due_day": int(due_day),
                        "agreed_payment": float(agreed_payment),
                        "monthly_payment": float(monthly_payment),
                        "remind_email": bool(remind_email),
                        "remind_text": bool(remind_text),
                        "notes": notes.strip(),
                        "payments": [],
                    })
                    save_loans(loans)
                    st.success("Loan added.")
                    st.rerun()

        st.divider()
        st.markdown("### Loans list (no IDs shown)")

        filter_name = st.selectbox("Filter by borrower", ["All"] + borrower_names, index=0, key="loan_filter_borrower")
        filtered = loans if filter_name == "All" else [L for L in loans if borrower_name(L.get("borrower_id")) == filter_name]

        if not filtered:
            st.info("No loans match this filter.")
        else:
            rows = []
            today = date.today()
            for L in filtered:
                paid = sum(float(p["amount"]) for p in L.get("payments", []))
                remaining = max(0.0, float(L.get("principal", 0.0)) - paid)  # simple remaining
                status, due_dt = due_status(L, today)

                rows.append({
                    "borrower": borrower_name(L.get("borrower_id")),
                    "principal": float(L.get("principal", 0.0)),
                    "apr": float(L.get("apr", 0.0)),
                    "start_date": L.get("start_date", ""),
                    "term_months": int(L.get("term_months", 0) or 0),
                    "payment_due_day": int(L.get("payment_due_day", 1) or 1),
                    "due_status": status,
                    "due_date_this_month": due_dt.isoformat(),
                    "monthly_payment": float(L.get("monthly_payment", 0.0) or 0.0),
                    "paid_total": paid,
                    "remaining_simple": remaining,
                    "payments_count": len(L.get("payments", [])),
                    "remind_email": bool(L.get("remind_email", True)),
                    "remind_text": bool(L.get("remind_text", False)),
                    "notes": L.get("notes", ""),
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with right:
        st.markdown("### Edit / Delete loan")

        if not loans:
            st.info("No loans yet. Add one on the left.")
        else:
            loan_labels = [
                f"{i}: {borrower_name(L.get('borrower_id'))} • ${float(L.get('principal', 0)):,.2f} @ {float(L.get('apr', 0)):.2f}%"
                for i, L in enumerate(loans)
            ]
            sel = st.selectbox("Select loan", loan_labels, key="loan_edit_select")
            idx = int(sel.split(":")[0])
            L = loans[idx]
            row_key = f"loan_{L.get('id', 'noid')}"

            with st.form("edit_loan_form"):
                borrower_names = [b["name"] for b in borrowers]
                current_borrower = borrower_name(L.get("borrower_id"))
                b_index = borrower_names.index(current_borrower) if current_borrower in borrower_names else 0
                name_to_id = {b["name"]: b["id"] for b in borrowers}

                bsel = st.selectbox("Borrower", borrower_names, index=b_index, key=f"{row_key}_borrower")
                principal = st.number_input(
                    "Principal", min_value=0.0, step=50.0, format="%.2f",
                    value=float(L.get("principal", 0.0)), key=f"{row_key}_principal"
                )
                apr = st.number_input(
                    "APR %", min_value=0.0, step=0.25, format="%.2f",
                    value=float(L.get("apr", 0.0)), key=f"{row_key}_apr"
                )

                c = st.columns(3)
                with c[0]:
                    start_txt = st.text_input("Start date (YYYY-MM-DD)", value=str(L.get("start_date", "")), key=f"{row_key}_start")
                with c[1]:
                    term_months = st.number_input(
                        "Term months", min_value=0, max_value=600,
                        value=int(L.get("term_months", 0) or 0), key=f"{row_key}_term"
                    )
                with c[2]:
                    due_day = st.number_input(
                        "Agreed payment day (1–31)", min_value=1, max_value=31,
                        value=int(L.get("payment_due_day", 1) or 1), key=f"{row_key}_due_day"
                    )

                agreed_payment = st.number_input(
                    "Agreed monthly payment (optional)",
                    min_value=0.0,
                    step=25.0,
                    format="%.2f",
                    value=float(L.get("agreed_payment", 0.0) or 0.0),
                    key=f"{row_key}_agreed_payment",
                )

                preview_payment = float(agreed_payment) if agreed_payment > 0 else (
                    float(calc_monthly_payment(float(principal), float(apr), int(term_months))) if int(term_months) > 0 else 0.0
                )
                st.caption(f"Monthly payment used: ${preview_payment:,.2f}")

                r1, r2 = st.columns(2)
                with r1:
                    remind_email = st.checkbox("Email reminder", value=bool(L.get("remind_email", True)), key=f"{row_key}_remind_email")
                with r2:
                    remind_text = st.checkbox("Text reminder", value=bool(L.get("remind_text", False)), key=f"{row_key}_remind_text")

                notes = st.text_input("Notes", value=L.get("notes", ""), key=f"{row_key}_notes")

                save_btn = st.form_submit_button("Save")
                del_btn = st.form_submit_button("Delete")

                if save_btn:
                    if principal <= 0:
                        st.error("Principal must be > 0.")
                    else:
                        monthly_payment = float(agreed_payment) if agreed_payment > 0 else 0.0
                        if monthly_payment <= 0 and int(term_months) > 0:
                            monthly_payment = float(calc_monthly_payment(float(principal), float(apr), int(term_months)))

                        loans[idx]["borrower_id"] = name_to_id[bsel]
                        loans[idx]["principal"] = float(principal)
                        loans[idx]["apr"] = float(apr)
                        loans[idx]["start_date"] = start_txt.strip()
                        loans[idx]["term_months"] = int(term_months)
                        loans[idx]["payment_due_day"] = int(due_day)
                        loans[idx]["agreed_payment"] = float(agreed_payment)
                        loans[idx]["monthly_payment"] = float(monthly_payment)
                        loans[idx]["remind_email"] = bool(remind_email)
                        loans[idx]["remind_text"] = bool(remind_text)
                        loans[idx]["notes"] = notes.strip()

                        save_loans(loans)
                        st.success("Loan updated.")
                        st.rerun()

                if del_btn:
                    loans.pop(idx)
                    save_loans(loans)
                    st.success("Loan deleted.")
                    st.rerun()

# =============================
# Payments tab
# =============================
with tab_payments:
    st.subheader("Payments")

    if not loans:
        st.info("No loans yet. Add a loan first.")
        st.stop()

    loan_labels = [
        f"{i}: {borrower_name(L.get('borrower_id'))} • ${float(L.get('principal', 0)):,.2f} @ {float(L.get('apr', 0)):.2f}%"
        for i, L in enumerate(loans)
    ]
    sel = st.selectbox("Select loan", loan_labels, key="pay_select_loan")
    idx = int(sel.split(":")[0])
    L = loans[idx]
    row_key = f"pay_{L.get('id', 'noid')}"

    paid = sum(float(p["amount"]) for p in L.get("payments", []))
    remaining = max(0.0, float(L.get("principal", 0.0)) - paid)  # simple remaining

    today = date.today()
    status, due_dt = due_status(L, today)

    b = borrowers_by_id.get(L.get("borrower_id"), {})
    borrower_email = (b.get("email") or "").strip()
    borrower_phone = (b.get("phone") or "").strip()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Borrower", borrower_name(L.get("borrower_id")))
    m2.metric("Monthly payment", f"${float(L.get('monthly_payment', 0.0) or 0.0):,.2f}")
    m3.metric("Total Paid", f"${paid:,.2f}")
    m4.metric("Remaining (simple)", f"${remaining:,.2f}")

    if status in ("Due", "Overdue"):
        st.error(f"Payment {status} — due date this month: {due_dt.isoformat()} (no payment recorded this cycle).")
    else:
        st.success(f"Payment status: {status} (due date this month: {due_dt.isoformat()})")

    st.divider()

    st.markdown("### Add payment")
    with st.form("add_payment_form", clear_on_submit=True):
        pdate = st.date_input("Payment date", value=today, key=f"{row_key}_date")
        pamt = st.number_input("Payment amount", min_value=0.0, step=25.0, format="%.2f", key=f"{row_key}_amt")
        submit = st.form_submit_button("Add payment")
        if submit:
            if pamt <= 0:
                st.error("Payment must be > 0.")
            else:
                L.setdefault("payments", []).append({"date": pdate.isoformat(), "amount": float(pamt)})
                save_loans(loans)
                st.success("Payment recorded.")
                st.rerun()

    st.divider()

    st.markdown("### Notifications (stub)")
    c1, c2 = st.columns(2)

    with c1:
        if st.button("Send Email Reminder", key=f"{row_key}_send_email"):
            if not borrower_email:
                st.warning("No borrower email on file. Add it under Borrowers tab.")
            else:
                st.info("Email reminder queued (stub). Next step: wire SMTP/SendGrid.")

    with c2:
        if st.button("Send Text Reminder", key=f"{row_key}_send_text"):
            if not borrower_phone:
                st.warning("No borrower phone on file. Add it under Borrowers tab.")
            else:
                st.info("Text reminder queued (stub). Next step: wire Twilio.")

    st.caption("Note: Automatic sending requires a scheduled job. For now, reminders can be sent manually from here.")

    st.divider()
    st.markdown("### Payment history (no IDs shown)")

    pays = L.get("payments", [])
    if not pays:
        st.info("No payments yet.")
    else:
        pdf = pd.DataFrame(pays)
        st.dataframe(pdf, use_container_width=True, hide_index=True)

        st.markdown("#### Delete a payment")
        pidx = st.number_input(
            "Select payment # (row index)",
            min_value=0,
            max_value=len(pays) - 1,
            value=0,
            key=f"{row_key}_del_idx",
        )
        if st.button("Delete payment", key=f"{row_key}_del_btn"):
            pays.pop(int(pidx))
            save_loans(loans)
            st.success("Payment deleted.")
            st.rerun()