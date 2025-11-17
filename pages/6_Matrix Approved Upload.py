# penomoran_matrix_app.py
import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from io import StringIO
import base64

from auth import check_password  # keep your auth as requested

# ---------------- CONFIG ----------------
SHEET_ID = "1ICIDY-69EvwZAY2EjdOhN8lCvWu4vRtjLVX1Y1-Nm4o"
SHEET_NAME = "PENOMORAN MATRIX STREAMLIT"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={requests.utils.requote_uri(SHEET_NAME)}"

APP_SCRIPT_ID = "REPLACE_WITH_YOUR_APP_SCRIPT_ID"  # <<-- hardcode your Apps Script ID here
APP_SCRIPT_URL = f"https://script.google.com/macros/s/{APP_SCRIPT_ID}/exec"
MAX_MB = 15  # fixed, not exposed in UI
# ----------------------------------------

st.set_page_config(page_title="PENOMORAN MATRIX - Upload PDF", layout="wide")


# ---------------- Helpers ----------------
def load_sheet_csv(url: str) -> pd.DataFrame:
    """Load a public Google Sheets worksheet exported as CSV."""
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


def status_is_empty_series(s: pd.Series) -> pd.Series:
    """
    Return boolean Series True where a STATUS-like series should be
    considered empty: NaN, None, empty string, or whitespace-only.
    """
    # convert to string where not na, but keep NaN detection first
    is_na = s.isna()
    s_as_str = s.fillna("").astype(str)
    is_blank_str = s_as_str.str.strip() == ""
    return is_na | is_blank_str


def get_unique_ordered_vals(seq):
    """Return order-preserving unique list (skips empty/NA values)."""
    out = []
    seen = set()
    for v in seq:
        if pd.isna(v):
            continue
        s = str(v).strip()
        if s == "":
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


# ---------------- App ----------------
if check_password():
    st.title("Upload Matrix Approved")

    # Load sheet
    try:
        with st.spinner("Loading sheet..."):
            df = load_sheet_csv(CSV_URL)
    except Exception as e:
        st.error(f"❌ Failed to load sheet '{SHEET_NAME}': {e}")
        st.stop()

    # Basic column check & normalization (keep original DF but allow case/space tolerant checks)
    df.columns = [c.strip() for c in df.columns.tolist()]

    expected = ["Nomor Matrix", "Tanggal Matrix", "DB", "Nomor Pick List", "Tujuan Pengiriman",
                "Moda Pengiriman", "PIC", "Activity", "Vessel", "STATUS"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        st.warning(f"Expected columns not found exactly: {missing}")

    # Compute boolean mask of STATUS empty correctly (covers NaN/None/blank)
    if "STATUS" in df.columns:
        empty_status_mask = status_is_empty_series(df["STATUS"])
    else:
        # If STATUS missing, treat as all non-empty (safe choice) and warn
        st.warning("'STATUS' column not found in sheet — no rows will be considered 'empty status'.")
        empty_status_mask = pd.Series([False] * len(df), index=df.index)

    # DB options come from sheet (unique DB values, order preserved)
    db_vals = get_unique_ordered_vals(df["DB"]) if "DB" in df.columns else []
    if not db_vals:
        st.warning("No DB values found in sheet. Make sure the 'DB' column exists and has values.")

    # --- Selection UI: DB first ---
    selected_db = st.selectbox("Database (DB):", options=[""] + db_vals, index=0)

    # --- Populate Nomor Matrix options based on DB & STATUS empty ---
    nomor_options = []
    if selected_db:
        # filter by DB equals selected_db and status empty
        # handle DB column missing gracefully
        if "DB" not in df.columns or "Nomor Matrix" not in df.columns:
            st.error("Required columns 'DB' and/or 'Nomor Matrix' not found in sheet.")
        else:
            mask_db = df["DB"].astype(str).fillna("").str.strip() == str(selected_db).strip()
            final_mask = mask_db & empty_status_mask
            filtered = df[final_mask].copy()
            nomor_options = get_unique_ordered_vals(filtered["Nomor Matrix"])
            st.write(f"Nomor Matrix options found: {len(nomor_options)}")
    
    selected_nomor = None
    if not nomor_options:
        st.selectbox("Nomor Matrix:", options=["— none available —"], index=0)
    else:
        selected_nomor = st.selectbox("Nomor Matrix:", options=[""] + nomor_options, index=0)

    # Small preview of matching rows (after selections) for confirmation
    if selected_db and selected_nomor:
        mask_db = df["DB"].astype(str).fillna("").str.strip() == str(selected_db).strip()
        final_mask = mask_db & empty_status_mask & (df["Nomor Matrix"].astype(str).fillna("").str.strip() == str(selected_nomor).strip())
        preview = df.loc[final_mask, [c for c in expected if c in df.columns]].reset_index(drop=True)
        st.caption("Preview of matching row(s):")
        st.dataframe(preview, height=200)

    st.markdown("---")

    # --- File upload (single PDF, fixed 15 MB) ---
    st.subheader(f"3) Upload PDF (single file — max {MAX_MB} MB)")
    uploaded = st.file_uploader("Choose a PDF file", type=["pdf"], accept_multiple_files=False)
    valid_bytes = None
    if uploaded is not None:
        raw = uploaded.read()
        size_mb = len(raw) / (1024 * 1024)
        if size_mb > MAX_MB:
            st.error(f"File too large: {size_mb:.2f} MB (max {MAX_MB} MB).")
            uploaded = None
        else:
            if not raw.startswith(b"%PDF"):
                st.error("Uploaded file does not look like a valid PDF (missing '%PDF' header).")
                uploaded = None
            else:
                valid_bytes = raw
                st.success(f"Accepted PDF: {uploaded.name} ({size_mb:.2f} MB)")

    # Debug expander (similar simple debugging UI)
    with st.expander("🔎 Debug: raw sheet & filtered rows (open while testing)"):
        st.subheader("Raw sheet head (first 50 rows)")
        st.dataframe(df.head(50))
        st.subheader("Rows where STATUS is empty (count)")
        st.write(f"Count: {int(empty_status_mask.sum())}")
        st.dataframe(df[empty_status_mask].head(200))

    st.markdown("---")

    # --- Submit ---
    st.subheader("4) Submit — sends data to hardcoded Apps Script")
    if st.button("✅ Submit"):
        # validations
        if APP_SCRIPT_ID == "REPLACE_WITH_YOUR_APP_SCRIPT_ID":
            st.error("APP_SCRIPT_ID is not configured in the script. Edit penomoran_matrix_app.py and add your Apps Script ID to APP_SCRIPT_ID.")
        elif not selected_db:
            st.warning("Please select a Database (DB).")
        elif not selected_nomor:
            st.warning("Please select a Nomor Matrix.")
        elif valid_bytes is None:
            st.warning("Please upload a valid PDF file.")
        else:
            # timestamp Jakarta
            ts = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y %H:%M:%S")
            payload = {
                "timestamp": ts,
                "db": str(selected_db),
                "nomor_matrix": str(selected_nomor),
                "filename": uploaded.name,
                "file_b64": base64.b64encode(valid_bytes).decode("utf-8"),
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
