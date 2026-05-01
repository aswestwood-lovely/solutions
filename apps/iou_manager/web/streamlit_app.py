import streamlit as st
from pathlib import Path
from datetime import date, datetime, timedelta
import json
import uuid
import pandas as pd

st.set_page_config(page_title="Loan Manager (Web)", page_icon="🤝", layout="wide")
st.title("IOU / Personal Loan Manager (Web)")
st.caption("Borrower directory + multiple loans per borrower + scheduled due tracking (start date + frequency).")

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
# Payment math + schedule
# -----------------------------
def calc_payment_per_period(principal: float, apr_pct: float, term_periods: int, periods_per_year: int) -> float:
    """
    Amortizing payment per period. Works for weekly/bi-weekly/monthly.
    If apr_pct == 0, payment = principal / term_periods.
    """
    if term_periods <= 0 or principal <= 0:
        return 0.0
    r = (apr_pct / 100.0) / periods_per_year
    if r <= 0:
        return principal / term_periods
    return principal * (r * (1 + r) ** term_periods) / ((1 + r) ** term_periods - 1)


def periods_per_year(frequency: str) -> int:
    f = (frequency or "Monthly").lower()
    if f in ("weekly", "week"):
        return 52
    if f in ("bi-weekly", "biweekly", "bi week", "bi-week"):
        return 26
    return 12  # monthly default


def period_days(frequency: str) -> int:
    f = (frequency or "Monthly").lower()
    if f in ("weekly", "week"):
        return 7
    if f in ("bi-weekly", "biweekly", "bi week", "bi-week"):
        return 14
    return 0  # monthly handled separately


def _parse_date(s: str) -> date | None:
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def add_months(d: date, months: int) -> date:
    # Add months while clamping day to end-of-month
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    next_month = (date(y, m, 28) + timedelta(days=4)).replace(day=1)
    last_day = (next_month - timedelta(days=1)).day
    day = min(d.day, last_day)
    return date(y, m, day)


def next_due_date(start: date, frequency: str, today: date) -> date:
    """Next scheduled due date ON or AFTER today, anchored to start."""
    if today <= start:
        return start

    f = (frequency or "Monthly").lower()
    if f in ("weekly", "week", "bi-weekly", "biweekly", "bi week", "bi-week"):
        step = period_days(frequency)
        delta_days = (today - start).days
        n = (delta_days + step - 1) // step  # ceil
        return start + timedelta(days=n * step)

    # Monthly: advance by whole months until >= today
    k = 0
    cur = start
    while cur < today:
        k += 1
        cur = add_months(start, k)
    return cur


def last_due_date(start: date, frequency: str, today: date) -> date:
    """Most recent scheduled due date ON or BEFORE today, anchored to start."""
    if today <= start:
        return start

    f = (frequency or "Monthly").lower()
    if f in ("weekly", "week", "bi-weekly", "biweekly", "bi week", "bi-week"):
        step = period_days(frequency)
        delta_days = (today - start).days
        n = delta_days // step
        return start + timedelta(days=n * step)

    # Monthly
    k = 0
    cur = start
    while True:
        nxt = add_months(start, k + 1)
        if nxt > today:
            return cur
        k += 1
        cur = nxt


def payment_made_in_window(loan: dict, start_d: date, end_d: date) -> bool:
    """Any payment recorded between start_d and end_d inclusive."""
    for p in loan.get("payments", []):
        d = _parse_date(p.get("date", ""))
        if d and start_d <= d <= end_d:
            return True
    return False

def period_window_for_due(start: date, frequency: str, due: date) -> tuple[date, date]:
    """
    Returns the period window [period_start, period_end] that this due date belongs to.
    We define period_start as the previous due date, and period_end as the day before this due date.
    """
    prev = last_due_date(start, frequency, due)
    # If due == start, prev == start. The first window is [start, start] for simplicity.
    if due == start:
        return start, due
    return prev, due - timedelta(days=1)

def due_status(loan: dict, today: date) -> tuple[str, date]:
    """
    Returns (status, relevant_due_date)
    - Overdue: we are after the last due date and there's no payment recorded since that due date
    - Due: today == due date and no payment recorded yet for that period
    - Not due: otherwise
    """
    start = _parse_date(loan.get("start_date", "")) or today
    freq = loan.get("payment_frequency", "Monthly")

    last_due = last_due_date(start, freq, today)
    nxt_due = next_due_date(start, freq, today)

    # Current period window is [last_due, nxt_due)
    # If a payment exists between last_due and today, we consider it satisfied for this period.
    paid_this_period = payment_made_in_window(loan, last_due, today)

    if not paid_this_period and today > last_due:
        return "Overdue", last_due
    if not paid_this_period and today == last_due:
        return "Due", last_due
    return "Not due", nxt_due

def add_period(d: date, frequency: str, n: int = 1) -> date:
    f = (frequency or "Monthly").lower()
    if f in ("weekly", "week"):
        return d + timedelta(days=7 * n)
    if f in ("bi-weekly", "biweekly", "bi week", "bi-week"):
        return d + timedelta(days=14 * n)
    # monthly default
    return add_months(d, n)

def next_n_due_dates(start: date, frequency: str, from_date: date, n: int = 5) -> list[date]:
    first = next_due_date(start, frequency, from_date)
    dates = [first]
    cur = first
    for _ in range(n - 1):
        cur = add_period(cur, frequency, 1)
        dates.append(cur)
    return dates

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

    # NEW: frequency-based schedule
    if "payment_frequency" not in L:
        # If old due-day exists, we default to Monthly
        L["payment_frequency"] = "Monthly"
        # Remove legacy field if present
        if "payment_due_day" in L:
            L.pop("payment_due_day", None)
        changed = True

    L.setdefault("agreed_payment", 0.0)
    L.setdefault("payment_per_period", 0.0)  # agreed or calculated per period
    L.setdefault("remind_email", True)
    L.setdefault("remind_text", False)

    # compute payment_per_period if missing/0 and term_periods is set (and agreed payment blank)
    principal = float(L.get("principal", 0.0) or 0.0)
    apr = float(L.get("apr", 0.0) or 0.0)

    # term_periods: interpret existing term_months as periods for Monthly; for weekly/biweekly it is still "periods"
    term_periods = int(L.get("term_periods", 0) or 0)
    if term_periods <= 0:
        # Backward compatibility: if you previously used term_months, keep it as term_periods for Monthly loans.
        tm = int(L.get("term_months", 0) or 0)
        if tm > 0:
            term_periods = tm
            L["term_periods"] = term_periods
            changed = True

    agreed = float(L.get("agreed_payment", 0.0) or 0.0)
    if float(L.get("payment_per_period", 0.0) or 0.0) <= 0:
        if agreed > 0:
            L["payment_per_period"] = agreed
        elif term_periods > 0:
            ppy = periods_per_year(L.get("payment_frequency", "Monthly"))
            L["payment_per_period"] = float(calc_payment_per_period(principal, apr, term_periods, ppy))
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
                start = st.date_input("Start date (schedule anchor)", value=date.today(), key="loan_add_start")
            with cols[1]:
                frequency = st.selectbox("Payment frequency", ["Weekly", "Bi-weekly", "Monthly"], index=2, key="loan_add_frequency")
            with cols[2]:
                term_periods = st.number_input("Number of payments (periods)", min_value=0, max_value=5000, value=0, key="loan_add_term_periods")

            agreed_payment = st.number_input(
                "Agreed payment per period (optional)",
                min_value=0.0,
                step=25.0,
                format="%.2f",
                key="loan_add_agreed_payment",
            )

            preview = float(agreed_payment) if agreed_payment > 0 else (
                float(calc_payment_per_period(float(principal), float(apr), int(term_periods), periods_per_year(frequency)))
                if int(term_periods) > 0 else 0.0
            )
            st.caption(f"Payment per period used: ${preview:,.2f} (frequency: {frequency})")

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
                    payment_per_period = float(agreed_payment) if agreed_payment > 0 else 0.0
                    if payment_per_period <= 0 and int(term_periods) > 0:
                        payment_per_period = float(
                            calc_payment_per_period(float(principal), float(apr), int(term_periods), periods_per_year(frequency))
                        )

                    loans.append({
                        "id": new_id(),
                        "borrower_id": name_to_id[bsel],
                        "principal": float(principal),
                        "apr": float(apr),
                        "start_date": start.isoformat(),
                        "payment_frequency": frequency,
                        "term_periods": int(term_periods),
                        "agreed_payment": float(agreed_payment),
                        "payment_per_period": float(payment_per_period),
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
                    "frequency": L.get("payment_frequency", "Monthly"),
                    "term_periods": int(L.get("term_periods", 0) or 0),
                    "payment_per_period": float(L.get("payment_per_period", 0.0) or 0.0),
                    "due_status": status,
                    "relevant_due_date": due_dt.isoformat(),
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
                f"{i}: {borrower_name(L.get('borrower_id'))} • ${float(L.get('principal', 0)):,.2f} • {L.get('payment_frequency','Monthly')}"
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
                    frequency = st.selectbox(
                        "Payment frequency",
                        ["Weekly", "Bi-weekly", "Monthly"],
                        index=["Weekly", "Bi-weekly", "Monthly"].index(L.get("payment_frequency", "Monthly")),
                        key=f"{row_key}_frequency",
                    )
                with c[2]:
                    term_periods = st.number_input(
                        "Number of payments (periods)",
                        min_value=0, max_value=5000,
                        value=int(L.get("term_periods", 0) or 0),
                        key=f"{row_key}_term_periods",
                    )

                agreed_payment = st.number_input(
                    "Agreed payment per period (optional)",
                    min_value=0.0,
                    step=25.0,
                    format="%.2f",
                    value=float(L.get("agreed_payment", 0.0) or 0.0),
                    key=f"{row_key}_agreed_payment",
                )

                preview = float(agreed_payment) if agreed_payment > 0 else (
                    float(calc_payment_per_period(float(principal), float(apr), int(term_periods), periods_per_year(frequency)))
                    if int(term_periods) > 0 else 0.0
                )
                st.caption(f"Payment per period used: ${preview:,.2f} (frequency: {frequency})")

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
                        payment_per_period = float(agreed_payment) if agreed_payment > 0 else 0.0
                        if payment_per_period <= 0 and int(term_periods) > 0:
                            payment_per_period = float(
                                calc_payment_per_period(float(principal), float(apr), int(term_periods), periods_per_year(frequency))
                            )

                        loans[idx]["borrower_id"] = name_to_id[bsel]
                        loans[idx]["principal"] = float(principal)
                        loans[idx]["apr"] = float(apr)
                        loans[idx]["start_date"] = start_txt.strip()
                        loans[idx]["payment_frequency"] = frequency
                        loans[idx]["term_periods"] = int(term_periods)
                        loans[idx]["agreed_payment"] = float(agreed_payment)
                        loans[idx]["payment_per_period"] = float(payment_per_period)
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
        f"{i}: {borrower_name(L.get('borrower_id'))} • ${float(L.get('principal', 0)):,.2f} • {L.get('payment_frequency','Monthly')}"
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

    st.divider()
    st.markdown("### Schedule preview (next 5 due dates)")

    start_anchor = _parse_date(L.get("start_date", "")) or today
    freq = L.get("payment_frequency", "Monthly")

    preview_dates = next_n_due_dates(start_anchor, freq, today, n=5)

    rows = []
    for i, d in enumerate(preview_dates):
        period_start, period_end = period_window_for_due(start_anchor, freq, d)
        paid = payment_made_in_window(L, period_start, period_end)
        rows.append(
            {
                "#": i + 1,
                "due_date": d.isoformat(),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "status": "Paid" if paid else "Unpaid",
            }
        )

    preview_df = pd.DataFrame(rows)
    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    st.caption(
        f"Anchor: {start_anchor.isoformat()} • Frequency: {freq} • Rule: Paid if any payment occurs within that period.")
    b = borrowers_by_id.get(L.get("borrower_id"), {})
    borrower_email = (b.get("email") or "").strip()
    borrower_phone = (b.get("phone") or "").strip()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Borrower", borrower_name(L.get("borrower_id")))
    m2.metric("Payment per period", f"${float(L.get('payment_per_period', 0.0) or 0.0):,.2f}")
    m3.metric("Total Paid", f"${paid:,.2f}")
    m4.metric("Remaining (simple)", f"${remaining:,.2f}")

    if status in ("Due", "Overdue"):
        st.error(f"Payment {status} — relevant due date: {due_dt.isoformat()} (no payment recorded for current period).")
    else:
        st.success(f"Payment status: {status} • Next due date: {due_dt.isoformat()}")

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