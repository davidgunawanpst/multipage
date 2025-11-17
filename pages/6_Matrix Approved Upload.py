# penomoran_matrix_app.py
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from io import StringIO
import base64

from auth import check_password  # keep your auth as requested

# --- Config (edit only these) ---
SHEET_ID = "1ICIDY-69EvwZAY2EjdOhN8lCvWu4vRtjLVX1Y1-Nm4o"
SHEET_NAME = "PENOMORAN MATRIX STREAMLIT"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={requests.utils.requote_uri(SHEET_NAME)}"

APP_SCRIPT_ID = "REPLACE_WITH_YOUR_APP_SCRIPT_ID"  # <<-- hardcode your Apps Script ID here
APP_SCRIPT_URL = f"https://script.google.com/macros/s/{APP_SCRIPT_ID}/exec"
MAX_MB = 15  # fixed, not exposed to UI
# ---------------------------------

st.set_page_config(page_title="PENOMORAN MATRIX - Upload PDF", layout="wide")

# --- Helpers ---
def load_sheet_csv(url: str) -> pd.DataFrame:
    """Load a public Google Sheet worksheet exported as CSV."""
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))

def filter_rows_status_empty(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows where STATUS is empty (case-insensitive match for column)."""
    cols_map = {c.strip().lower(): c for c in df.columns}
    if "status" not in cols_map:
        st.warning(f"'STATUS' column not found. Columns in sheet: {list(df.columns)}")
        return pd.DataFrame()
    status_col = cols_map["status"]
    clean = df[status_col].astype(str).fillna("").str.strip()
    return df[clean == ""]

def unique_values(df: pd.DataFrame, col: str) -> list:
    if col not in df.columns:
        return []
    vals = df[col].astype(str).fillna("").str.strip()
    vals = vals.loc[vals != ""]
    # preserve order
    seen = set()
    out = []
    for v in vals.tolist():
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out

# --- Main app ---
if check_password():
    st.title("📥 PENOMORAN MATRIX — Upload PDF & record Nomor Matrix + DB")

    st.markdown("This app reads the public sheet, filters rows where `STATUS` is blank, lets you select a validated `Nomor Matrix` and its `DB`, upload one PDF (<= 15 MB), then sends data to a hardcoded Apps Script webapp.")

    # load sheet
    try:
        with st.spinner("Loading sheet..."):
            df = load_sheet_csv(CSV_URL)
    except Exception as e:
        st.error(f"❌ Failed to load sheet '{SHEET_NAME}': {e}")
        st.stop()

    # preview & column check
    expected = ["Nomor Matrix", "Tanggal Matrix", "DB", "Nomor Pick List", "Tujuan Pengiriman", "Moda Pengiriman", "PIC", "Activity", "Vessel", "STATUS"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        st.warning(f"Expected columns not found exactly: {missing}")

    filtered = filter_rows_status_empty(df)
    st.write(f"Rows with empty STATUS: {len(filtered)}")

    # selections
    nomor_options = unique_values(filtered, "Nomor Matrix")
    selected_nomor = None
    selected_db = None

    col1, col2 = st.columns(2)
    with col1:
        if nomor_options:
            selected_nomor = st.selectbox("Nomor Matrix (validated)", options=[""] + nomor_options, index=0)
        else:
            st.warning("No Nomor Matrix values available in rows with empty STATUS.")
    with col2:
        if selected_nomor:
            subset = filtered[filtered["Nomor Matrix"].astype(str).str.strip() == str(selected_nomor)]
            db_options = unique_values(subset, "DB")
            if db_options:
                selected_db = st.selectbox("DB (validated for chosen Nomor Matrix)", options=[""] + db_options, index=0)
            else:
                st.selectbox("DB (no DB found for selected Nomor Matrix)", options=[""], index=0)
        else:
            st.selectbox("DB (choose Nomor Matrix first)", options=[""], index=0)

    # small preview for confirmation
    if selected_nomor:
        st.caption("Preview of matching rows:")
        cols_to_show = [c for c in expected if c in filtered.columns]
        st.dataframe(filtered.loc[filtered["Nomor Matrix"].astype(str).str.strip() == str(selected_nomor), cols_to_show].reset_index(drop=True), height=200)

    st.markdown("---")

    # file upload (single PDF, fixed max size)
    st.subheader(f"Upload PDF (single file, max {MAX_MB} MB)")
    uploaded = st.file_uploader("Choose a PDF file", type=["pdf"], accept_multiple_files=False)
    valid_file_bytes = None
    if uploaded is not None:
        raw = uploaded.read()
        size_mb = len(raw) / (1024 * 1024)
        if size_mb > MAX_MB:
            st.error(f"File too large: {size_mb:.2f} MB (max {MAX_MB} MB).")
            uploaded = None
        else:
            if not raw.startswith(b"%PDF"):
                st.error("Uploaded file does not look like a valid PDF (missing %PDF header).")
                uploaded = None
            else:
                valid_file_bytes = raw
                st.success(f"Accepted PDF: {uploaded.name} ({size_mb:.2f} MB)")

    st.markdown("---")

    # debug expander (same friendly style, keep simple)
    with st.expander("🔎 Debug: raw sheet & matched rows (open while testing)"):
        try:
            st.subheader("Raw sheet head (first 50 rows)")
            st.dataframe(df.head(50))
            st.subheader("Rows with STATUS blank (filtered)")
            st.write(f"Count: {len(filtered)}")
            st.dataframe(filtered.head(200))
        except Exception as de:
            st.write("Debug error:", de)

    # submit
    if st.button("✅ Submit"):
        if APP_SCRIPT_ID == "REPLACE_WITH_YOUR_APP_SCRIPT_ID":
            st.error("APP_SCRIPT_ID not configured. Edit penomoran_matrix_app.py and set APP_SCRIPT_ID to your Apps Script ID.")
        elif not selected_nomor:
            st.warning("Please select a Nomor Matrix.")
        elif not selected_db:
            st.warning("Please select a DB.")
        elif valid_file_bytes is None:
            st.warning("Please upload a valid PDF file.")
        else:
            # timestamp Jakarta
            ts = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y %H:%M:%S")
            payload = {
                "timestamp": ts,
                "nomor_matrix": str(selected_nomor),
                "db": str(selected_db),
                "filename": uploaded.name,
                "file_b64": base64.b64encode(valid_file_bytes).decode("utf-8"),
            }
            try:
                with st.spinner("Sending to Apps Script..."):
                    resp = requests.post(APP_SCRIPT_URL, json=payload, timeout=60)
                if resp.status_code in (200, 201):
                    st.success("🎉 Submission successful!")
                    st.json(payload)
                else:
                    st.error(f"❌ Apps Script returned {resp.status_code}: {resp.text}")
            except Exception as e:
                st.error(f"❌ Error sending data: {e}")
