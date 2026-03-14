import streamlit as st
import sys
from pathlib import Path
import json
import pandas as pd
from io import BytesIO

BASE = Path(__file__).resolve().parents[2]  # .../apps/debt_calculator
sys.path.insert(0, str(BASE / "web"))       # so we can import app_state + validators

from app_state import get_active_profile, load_section, save_section
from validators import validate_bill

st.set_page_config(page_title="Import/Export • Debt Calculator", page_icon="📦", layout="wide")

st.title("Import / Export")
st.caption("Export or import your bills for the active profile (JSON + Excel).")

active = get_active_profile()
st.markdown(f"### Active profile: **{active.name}**")
st.divider()

# Load current bills
bills_payload = load_section("bills")
bills = (bills_payload or {}).get("items", []) or []
df = pd.DataFrame(bills) if bills else pd.DataFrame()

# -----------------------------
# EXPORT SECTION
# -----------------------------
st.markdown("## Export")

c1, c2 = st.columns([1.1, 1.4])

with c1:
    st.write("### JSON (backup)")
    export_obj = {"profile": {"id": active.id, "name": active.name}, "bills": bills}
    export_json = json.dumps(export_obj, indent=2)

    st.download_button(
        label="Download JSON",
        data=export_json,
        file_name=f"debt_calculator_{active.name.replace(' ', '_').lower()}_bills.json",
        mime="application/json",
    )

    st.write("")

    st.write("### Excel (.xlsx)")
    if bills:
        out = BytesIO()
        # Ensure consistent column order
        preferred_cols = [
            "name", "amount", "due_day", "apr", "min_payment", "planned_payment",
            "include_in_strategy", "status", "override", "custom_order", "notes"
        ]
        export_df = df.copy()
        for col in preferred_cols:
            if col not in export_df.columns:
                export_df[col] = None
        export_df = export_df[preferred_cols]

        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False, sheet_name="bills")

        st.download_button(
            label="Download Excel",
            data=out.getvalue(),
            file_name=f"debt_calculator_{active.name.replace(' ', '_').lower()}_bills.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.info("No bills to export yet.")

with c2:
    st.write("### Preview")
    if bills:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No bills saved for this profile yet.")

st.divider()

# -----------------------------
# IMPORT SECTION
# -----------------------------
st.markdown("## Import")

st.warning(
    "Import can replace the current bills list for this profile. "
    "Download an export first if you want a backup."
)

tab_json, tab_excel = st.tabs(["Import JSON", "Import Excel"])

# ---------- JSON IMPORT ----------
with tab_json:
    uploaded = st.file_uploader("Upload JSON export", type=["json"], key="import_json_uploader")

    if uploaded:
        try:
            raw = uploaded.read().decode("utf-8")
            obj = json.loads(raw)

            incoming_bills = obj.get("bills", [])
            if not isinstance(incoming_bills, list):
                raise ValueError("Invalid JSON: 'bills' must be a list.")

            def normalize_bill(b: dict) -> dict | None:
                name = str(b.get("name", "")).strip()
                amount = float(b.get("amount", 0.0) or 0.0)
                if not name or amount <= 0:
                    return None
                return {
                    "name": name,
                    "amount": amount,
                    "due_day": int(b.get("due_day", 1) or 1),
                    "apr": float(b.get("apr", 0.0) or 0.0),
                    "min_payment": float(b.get("min_payment", 0.0) or 0.0),
                    "planned_payment": float(b.get("planned_payment", b.get("min_payment", 0.0) or 0.0) or 0.0),
                    "include_in_strategy": bool(b.get("include_in_strategy", True)),
                    "status": str(b.get("status", "Current") or "Current"),
                    "override": b.get("override", {}) or {},
                    "custom_order": int(b.get("custom_order", 999999) or 999999),
                    "notes": str(b.get("notes", "") or "").strip(),
                }

            cleaned = []
            for b in incoming_bills:
                if isinstance(b, dict):
                    nb = normalize_bill(b)
                    if nb:
                        cleaned.append(nb)

            st.success(f"Parsed {len(cleaned)} bills from JSON.")
            st.dataframe(pd.DataFrame(cleaned), use_container_width=True, hide_index=True)

            colA, colB = st.columns(2)
            with colA:
                if st.button("Replace current bills with JSON import", key="import_json_replace"):
                    save_section("bills", {"items": cleaned})
                    st.success("Import complete. Bills replaced for this profile.")
                    st.rerun()
            with colB:
                if st.button("Merge JSON import (append)", key="import_json_merge"):
                    merged = bills + cleaned
                    save_section("bills", {"items": merged})
                    st.success("Merge complete. Bills appended for this profile.")
                    st.rerun()

        except Exception as e:
            st.error(f"Import failed: {e}")

validated = []
bad = []
for i, b in enumerate(cleaned):
    ok, errs, cb = validate_bill(b)
    if ok:
        validated.append(cb)
    else:
        bad.append((i, errs))

if bad:
    st.warning(f"{len(bad)} rows were rejected due to validation errors.")
    for i, errs in bad[:10]:
        st.write(f"- Row {i}: " + "; ".join(errs))

cleaned = validated

# ---------- EXCEL IMPORT ----------
with tab_excel:
    uploaded_xlsx = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"], key="import_excel_uploader")

    if uploaded_xlsx:
        try:
            incoming_df = pd.read_excel(uploaded_xlsx, engine="openpyxl")
            st.write("### Detected columns")
            st.write(list(incoming_df.columns))

            st.divider()
            st.write("### Map your columns")

            # Expected fields
            expected = {
                "name": "name",
                "amount": "amount",
                "due_day": "due_day",
                "apr": "apr",
                "min_payment": "min_payment",
                "planned_payment": "planned_payment",
                "include_in_strategy": "include_in_strategy",
                "status": "status",
                "custom_order": "custom_order",
                "notes": "notes",
            }

            cols = ["(none)"] + list(incoming_df.columns)

            mapping = {}
            map_cols = st.columns(2)
            i = 0
            for field, label in expected.items():
                with map_cols[i % 2]:
                    mapping[field] = st.selectbox(
                        f"{field} column",
                        cols,
                        index=cols.index(label) if label in cols else 0,
                        key=f"map_{field}",
                    )
                i += 1

            st.caption("Override is optional. If you want it, include a column named 'override' containing JSON like {'payment': 200}.")

            override_col = st.selectbox(
                "override column (optional)",
                ["(none)"] + list(incoming_df.columns),
                index=(["(none)"] + list(incoming_df.columns)).index("override") if "override" in incoming_df.columns else 0,
                key="map_override",
            )

            def get_val(row, field):
                col = mapping[field]
                if col == "(none)":
                    return None
                return row.get(col)

            cleaned = []
            for _, row in incoming_df.iterrows():
                name = str(get_val(row, "name") or "").strip()
                amount = float(get_val(row, "amount") or 0.0)

                if not name or amount <= 0:
                    continue

                due_day = int(get_val(row, "due_day") or 1)
                apr = float(get_val(row, "apr") or 0.0)
                min_payment = float(get_val(row, "min_payment") or 0.0)

                planned_payment = get_val(row, "planned_payment")
                planned_payment = float(planned_payment) if planned_payment not in (None, "") else float(min_payment)

                include_in_strategy = get_val(row, "include_in_strategy")
                include_in_strategy = True if include_in_strategy in (None, "", "True", True, 1) else bool(include_in_strategy)

                status = str(get_val(row, "status") or "Current")

                custom_order = get_val(row, "custom_order")
                custom_order = int(custom_order) if custom_order not in (None, "") else 999999

                notes = str(get_val(row, "notes") or "").strip()

                override = {}
                if override_col != "(none)":
                    raw_override = row.get(override_col)
                    if isinstance(raw_override, str) and raw_override.strip():
                        try:
                            override = json.loads(raw_override)
                        except Exception:
                            # if not valid JSON, ignore
                            override = {}
                    elif isinstance(raw_override, dict):
                        override = raw_override

                cleaned.append(
                    {
                        "name": name,
                        "amount": amount,
                        "due_day": due_day,
                        "apr": apr,
                        "min_payment": min_payment,
                        "planned_payment": planned_payment,
                        "include_in_strategy": include_in_strategy,
                        "status": status,
                        "override": override,
                        "custom_order": custom_order,
                        "notes": notes,
                    }
                )

            st.divider()
            st.success(f"Parsed {len(cleaned)} bills from Excel.")
            st.dataframe(pd.DataFrame(cleaned), use_container_width=True, hide_index=True)

            colA, colB = st.columns(2)
            with colA:
                if st.button("Replace current bills with Excel import", key="import_excel_replace"):
                    save_section("bills", {"items": cleaned})
                    st.success("Import complete. Bills replaced for this profile.")
                    st.rerun()
            with colB:
                if st.button("Merge Excel import (append)", key="import_excel_merge"):
                    merged = bills + cleaned
                    save_section("bills", {"items": merged})
                    st.success("Merge complete. Bills appended for this profile.")
                    st.rerun()

        except Exception as e:
            st.error(f"Excel import failed: {e}")