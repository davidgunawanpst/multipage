# app.py
import streamlit as st
import pandas as pd
import requests
import io
import base64
from typing import Optional

# -----------------------
# CONFIG
# -----------------------
SHEET_ID = "1ICIDY-69EvwZAY2EjdOhN8lCvWu4vRtjLVX1Y1-Nm4o"
DEFAULT_MAX_MB = 15

st.set_page_config(page_title="Upload Matrix Approved", layout="centered")

# Sidebar settings
st.sidebar.header("Settings")
app_script_id = st.sidebar.text_input("Apps Script ID", help="Paste your Apps Script ID token (the part after /s/ in the web app URL). Example: AKfycbx...")
max_mb = int(st.sidebar.number_input("Max PDF size (MB)", min_value=1, max_value=50, value=DEFAULT_MAX_MB))

# try to set server upload limit (works in some deployments)
try:
    st.set_option("server.maxUploadSize", max_mb)
except Exception:
    pass

# -----------------------
# Helpers
# -----------------------
@st.cache_data(ttl=300)
def load_public_sheet_csv(sheet_id: str) -> Optional[pd.DataFrame]:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        return df
    except Exception as e:
        st.error(f"Failed to load sheet. Make sure the sheet is public and the ID is correct. Error: {e}")
        return None

def filter_status_empty(df: pd.DataFrame, status_col='STATUS') -> pd.DataFrame:
    if status_col not in df.columns:
        # be forgiving: try uppercase/lowercase variants
        matches = [c for c in df.columns if c.strip().lower() == status_col.lower()]
        if matches:
            status_col = matches[0]
        else:
            st.warning(f"Column '{status_col}' not found. Columns: {list(df.columns)}")
            return pd.DataFrame()
    s = df[status_col].astype(str).fillna("").str.strip()
    return df[s == ""]

def unique_values_safe(df: pd.DataFrame, col: str):
    if col not in df.columns:
        return []
    return df[col].astype(str).fillna("").str.strip().loc[lambda x: x != ""].unique().tolist()

def post_to_appscript(app_script_id: str, payload: dict, timeout=120):
    url = f"https://script.google.com/macros/s/{app_script_id}/exec"
    headers = {"Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    return resp

# -----------------------
# Step 1: Load sheet & build validation
# -----------------------
st.subheader("1) Load sheet and build Nomor Matrix validation")
st.info("Loading Google Sheet (public). If the sheet becomes private later you'll need to change this approach.")

df = load_public_sheet_csv(SHEET_ID)
if df is None:
    st.stop()

expected_cols = ["Nomor Matrix", "Tanggal Matrix", "DB", "Nomor Pick List", "Tujuan Pengiriman", "Moda Pengiriman", "PIC", "Activity", "Vessel", "STATUS"]
missing = [c for c in expected_cols if c not in df.columns]
if missing:
    st.warning(f"Sheet did not contain these expected columns (they might be named slightly differently): {missing}")

filtered = filter_status_empty(df, status_col="STATUS")
st.write(f"Rows with empty STATUS: {len(filtered)}")

nomor_options = unique_values_safe(filtered, "Nomor Matrix")
selected_nomor = None
selected_db = None

col1, col2 = st.columns(2)
with col1:
    if nomor_options:
        selected_nomor = st.selectbox("Select Nomor Matrix (validated)", options=[""] + nomor_options, index=0)
    else:
        st.warning("No Nomor Matrix options found in rows with empty STATUS.")
with col2:
    if selected_nomor:
        subset = filtered[filtered["Nomor Matrix"].astype(str).str.strip() == str(selected_nomor)]
        db_options = unique_values_safe(subset, "DB")
        selected_db = st.selectbox("Select DB (validated for the chosen Nomor Matrix)", options=[""] + db_options, index=0)
    else:
        st.selectbox("Select DB (choose Nomor Matrix first)", options=[""], index=0)

st.markdown("---")
# -----------------------
# Step 2: Upload PDF
# -----------------------
st.subheader("2) Upload a single PDF (max {} MB)".format(max_mb))
uploaded_file = st.file_uploader("Upload PDF", type=["pdf"], accept_multiple_files=False)

valid_file_bytes = None
if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > max_mb:
        st.error(f"File is too large: {size_mb:.2f} MB (max {max_mb} MB).")
        uploaded_file = None
    else:
        if not file_bytes.startswith(b"%PDF"):
            st.error("Uploaded file does not look like a PDF (missing %PDF header).")
            uploaded_file = None
        else:
            valid_file_bytes = file_bytes
            st.success(f"PDF '{uploaded_file.name}' accepted ({size_mb:.2f} MB).")

st.markdown("---")
# -----------------------
# Step 3: Submit
# -----------------------
st.subheader("3) Submit — records will be sent to your Apps Script")

if st.button("Submit"):
    # validations
    if not app_script_id:
        st.error("Please enter your Apps Script ID in the sidebar.")
    elif not selected_nomor:
        st.error("Please select a Nomor Matrix.")
    elif not selected_db:
        st.error("Please select a DB.")
    elif valid_file_bytes is None:
        st.error("Please upload a valid PDF file.")
    else:
        with st.spinner("Posting to Apps Script..."):
            payload = {
                "nomor_matrix": str(selected_nomor),
                "db": str(selected_db),
                "filename": uploaded_file.name,
                "file_b64": base64.b64encode(valid_file_bytes).decode("utf-8"),
            }
            try:
                resp = post_to_appscript(app_script_id, payload)
                try:
                    resp.raise_for_status()
                    # attempt parse JSON, but be tolerant if not JSON
                    try:
                        j = resp.json()
                        st.success(f"Success! Apps Script response: {j}")
                    except Exception:
                        st.success(f"Success! HTTP {resp.status_code}. Response text: {resp.text[:1000]}")
                except Exception as e:
                    st.error(f"Apps Script returned error (HTTP {resp.status_code}). Response text: {resp.text[:1000]}")
            except Exception as e:
                st.error(f"Failed to contact Apps Script: {e}")

st.markdown("---")
st.caption("Notes: The app posts a JSON payload (nomor_matrix, db, filename, file_b64) to your Apps Script web app URL: https://script.google.com/macros/s/{APP_SCRIPT_ID}/exec. Make sure your Apps Script is deployed and accepting POST requests.")

