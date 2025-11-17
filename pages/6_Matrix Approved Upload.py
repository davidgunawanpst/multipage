# penomoran_matrix_app.py
import streamlit as st
import pandas as pd
import requests
import io
import base64
from typing import Optional

# ---------------------------
# CONFIG (edit only here)
# ---------------------------
SHEET_ID = "1ICIDY-69EvwZAY2EjdOhN8lCvWu4vRtjLVX1Y1-Nm4o"
WORKSHEET_NAME = "PENOMORAN MATRIX STREAMLIT"
APP_SCRIPT_ID = "REPLACE_WITH_YOUR_APP_SCRIPT_ID"  # <<--- Hardcode your Apps Script ID here
MAX_MB = 15  # fixed, not exposed in UI
# ---------------------------

st.set_page_config(page_title="PENOMORAN MATRIX - Upload PDF", layout="centered")
st.title("PENOMORAN MATRIX — Upload PDF & record Nomor Matrix + DB")

# ---------------------------
# Helpers
# ---------------------------
@st.cache_data(ttl=300)
def load_public_sheet_by_name(sheet_id: str, sheet_name: str) -> Optional[pd.DataFrame]:
    """
    Load a public Google Sheets worksheet by name using the 'gviz/tq' CSV output.
    This avoids needing gid and works with public sheets.
    """
    # note: sheet_name should be URL-encoded if it contains spaces/special chars
    sheet_name_safe = requests.utils.requote_uri(sheet_name)
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name_safe}"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        return df
    except Exception as e:
        st.error(f"Failed to load sheet '{sheet_name}' from sheet ID {sheet_id}. Make sure the sheet/tab name is exact and the sheet is public. Error: {e}")
        return None

def filter_status_empty(df: pd.DataFrame, status_col='STATUS') -> pd.DataFrame:
    # case-insensitive match for the STATUS column name
    cols_map = {c.strip().lower(): c for c in df.columns}
    if status_col.lower() in cols_map:
        real_col = cols_map[status_col.lower()]
    else:
        st.warning(f"STATUS column not found. Sheet columns: {list(df.columns)}")
        return pd.DataFrame()
    s = df[real_col].astype(str).fillna("").str.strip()
    return df[s == ""]

def unique_values_safe(df: pd.DataFrame, col: str):
    if col not in df.columns:
        return []
    vals = df[col].astype(str).fillna("").str.strip()
    return vals.loc[vals != ""].unique().tolist()

def post_to_appscript(app_script_id: str, payload: dict, timeout=120):
    url = f"https://script.google.com/macros/s/{app_script_id}/exec"
    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    return resp

# ---------------------------
# Step 1: Load sheet & validation
# ---------------------------
st.subheader("1) Source: public sheet — build Nomor Matrix validation")
st.info(f"Loading worksheet '{WORKSHEET_NAME}' from the public sheet.")

df = load_public_sheet_by_name(SHEET_ID, WORKSHEET_NAME)
if df is None:
    st.stop()

expected_cols = ["Nomor Matrix", "Tanggal Matrix", "DB", "Nomor Pick List",
                 "Tujuan Pengiriman", "Moda Pengiriman", "PIC", "Activity", "Vessel", "STATUS"]
missing = [c for c in expected_cols if c not in df.columns]
if missing:
    st.warning(f"Expected columns not found exactly: {missing}")

filtered = filter_status_empty(df, status_col="STATUS")
st.write(f"Rows with empty STATUS: {len(filtered)}")

# Nomor Matrix -> DB validation
nomor_options = unique_values_safe(filtered, "Nomor Matrix")
selected_nomor = None
selected_db = None

col1, col2 = st.columns([1,1])
with col1:
    if nomor_options:
        selected_nomor = st.selectbox("Select Nomor Matrix (validated)", options=[""] + nomor_options, index=0)
    else:
        st.warning("No Nomor Matrix options found in rows with empty STATUS.")
with col2:
    if selected_nomor:
        subset = filtered[filtered["Nomor Matrix"].astype(str).str.strip() == str(selected_nomor)]
        db_options = unique_values_safe(subset, "DB")
        selected_db = st.selectbox("Select DB (validated for chosen Nomor Matrix)", options=[""] + db_options, index=0)
    else:
        st.selectbox("Select DB (choose Nomor Matrix first)", options=[""], index=0)

# optional preview of the rows that match the selection
if selected_nomor:
    preview = filtered[filtered["Nomor Matrix"].astype(str).str.strip() == str(selected_nomor)]
    st.caption("Preview of matching rows (from sheet):")
    # show only expected columns if present
    cols_to_show = [c for c in expected_cols if c in preview.columns]
    st.dataframe(preview.loc[:, cols_to_show].reset_index(drop=True), height=200)

st.markdown("---")

# ---------------------------
# Step 2: Upload PDF (one file only, fixed max)
# ---------------------------
st.subheader(f"2) Upload a single PDF (max {MAX_MB} MB — fixed)")
uploaded_file = st.file_uploader("Upload a PDF file (only one)", type=["pdf"], accept_multiple_files=False)

valid_file_bytes = None
if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_MB:
        st.error(f"File is too large: {size_mb:.2f} MB (max {MAX_MB} MB). Please choose a smaller PDF.")
        uploaded_file = None
    else:
        # check PDF header
        if not file_bytes.startswith(b"%PDF"):
            st.error("Uploaded file does not look like a valid PDF (missing %PDF header).")
            uploaded_file = None
        else:
            valid_file_bytes = file_bytes
            st.success(f"PDF '{uploaded_file.name}' accepted ({size_mb:.2f} MB)")

st.markdown("---")

# ---------------------------
# Step 3: Submit (Apps Script ID hardcoded; not shown in UI)
# ---------------------------
st.subheader("3) Submit — record will be sent to Apps Script (hardcoded ID)")

if st.button("Submit"):
    # validations
    if APP_SCRIPT_ID == "REPLACE_WITH_YOUR_APP_SCRIPT_ID":
        st.error("APP_SCRIPT_ID is not configured in the script. Edit penomoran_matrix_app.py and add your Apps Script ID to APP_SCRIPT_ID constant.")
    elif not selected_nomor:
        st.error("Please select a Nomor Matrix.")
    elif not selected_db:
        st.error("Please select a DB.")
    elif valid_file_bytes is None:
        st.error("Please upload a valid PDF file.")
    else:
        payload = {
            "nomor_matrix": str(selected_nomor),
            "db": str(selected_db),
            "filename": uploaded_file.name,
            "file_b64": base64.b64encode(valid_file_bytes).decode("utf-8"),
        }
        with st.spinner("Posting to Apps Script..."):
            try:
                resp = post_to_appscript(APP_SCRIPT_ID, payload)
                try:
                    resp.raise_for_status()
                    # prefer JSON response if available
                    try:
                        j = resp.json()
                        st.success(f"Success! Apps Script response: {j}")
                    except Exception:
                        st.success(f"Success! HTTP {resp.status_code}. Response text (truncated): {resp.text[:1000]}")
                except Exception:
                    st.error(f"Apps Script returned error (HTTP {resp.status_code}). Response text (truncated): {resp.text[:1000]}")
            except Exception as e:
                st.error(f"Failed to contact Apps Script: {e}")

st.markdown("---")
st.caption("Notes: Apps Script ID is hardcoded in the script (APP_SCRIPT_ID). Make sure the Script is deployed and accepts POSTs at https://script.google.com/macros/s/{APP_SCRIPT_ID}/exec")
