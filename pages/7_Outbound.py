# app.py
import streamlit as st
import pandas as pd
import requests
from io import StringIO, BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
import base64
from PIL import Image

# optional auth hook (if you have auth.py); fallback to allow all
try:
    from auth import check_password
except Exception:
    def check_password():
        return True

# -----------------------
# CONFIG (edit as needed)
# -----------------------
APPS_SCRIPT_URL = "PUT_YOUR_APPS_SCRIPT_URL_HERE"  # <- replace with your Apps Script URL
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
SHEET_NAME = "List All Packing"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

# Upload limits (same defaults you used)
MAX_BYTES_PER_FILE = 8 * 1024 * 1024   # 8 MB raw file allowed (before compression check)
MAX_TOTAL_BYTES = 40 * 1024 * 1024     # 40 MB total (after compression)
COMPRESS_MAX_WIDTH = 1600              # max width for image resize
COMPRESS_QUALITY = 80                  # JPEG quality (0-100)

DB_LIST = ["DMI", "PBN", "PKS", "PMT", "PSS", "PSM", "PST"]

# -----------------------
# Helpers
# -----------------------
def load_sheet_csv(url: str) -> pd.DataFrame:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text), dtype=object)

def compress_image_bytes(file_bytes: bytes, max_width=COMPRESS_MAX_WIDTH, quality=COMPRESS_QUALITY) -> bytes:
    try:
        img = Image.open(BytesIO(file_bytes)).convert("RGB")
    except Exception:
        # if not an image or can't open, return original
        return file_bytes

    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    out = BytesIO()
    try:
        img.save(out, format="JPEG", quality=quality, optimize=True)
    except Exception:
        out = BytesIO()
        img.save(out, format="PNG", optimize=True)
    return out.getvalue()

def clean_candidate(val):
    if val is None:
        return None
    try:
        import pandas as _pd
        if _pd.isna(val):
            return None
    except Exception:
        pass
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val).strip()
    if isinstance(val, int):
        return str(val)
    s = str(val).strip()
    if s.lower() in {"", "nan", "none", "na"}:
        return None
    return s

def extract_from_unique_code(unique_code_value):
    if unique_code_value is None:
        return None
    try:
        import pandas as _pd
        if _pd.isna(unique_code_value):
            return None
    except Exception:
        pass
    s = str(unique_code_value).strip()
    if not s:
        return None
    if '|' in s:
        parts = [p.strip() for p in s.split('|') if p.strip()]
        if parts:
            return parts[-1]
    tokens = [t.strip() for t in s.replace('/', ' ').split() if t.strip()]
    if tokens:
        return tokens[-1]
    return s or None

def get_available_picks(df: pd.DataFrame, selected_db: str) -> list:
    # expects columns: Database, Pick List NO., Finish Packing, Nomor Matrix (case-sensitive names from sheet)
    df = df.copy()
    df.columns = df.columns.str.strip()
    # ensure required columns exist
    required = {"Database", "Pick List NO.", "Finish Packing", "Nomor Matrix"}
    if not required.issubset(set(df.columns)):
        missing = required - set(df.columns)
        raise ValueError(f"Sheet missing required columns: {missing}")

    df["Database"] = df["Database"].astype(str).str.strip()
    finish_nonempty = ~(df["Finish Packing"].isna() | df["Finish Packing"].astype(str).str.strip().str.lower().isin(['', 'nan', 'none']))
    nomor_nonempty = ~(df["Nomor Matrix"].isna() | df["Nomor Matrix"].astype(str).str.strip().str.lower().isin(['', 'nan', 'none']))

    filtered = df[(df["Database"] == selected_db) & finish_nonempty & nomor_nonempty].copy()

    picks = []
    for _, row in filtered.iterrows():
        raw_pl = row.get("Pick List NO.", None)
        candidate = clean_candidate(raw_pl)
        if candidate is None:
            unique = row.get("Unique Code", None) if "Unique Code" in row.index else None
            extracted = extract_from_unique_code(unique)
            candidate = clean_candidate(extracted)
        if candidate:
            picks.append(candidate)

    # dedupe preserving order
    seen = set()
    ordered = []
    for p in picks:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    digits = [x for x in ordered if str(x).isdigit()]
    nondigits = [x for x in ordered if not str(x).isdigit()]
    digits_sorted = sorted(digits, key=lambda s: int(s))
    return digits_sorted + nondigits

# -----------------------
# UI
# -----------------------
if check_password():
    st.set_page_config(page_title="Upload Photos (Finish Packing)", layout="wide")
    st.title("📸 Upload Photos — Finish Packing")

    # 1) DB select
    selected_db = st.selectbox("Database (DB):", DB_LIST)

    # 2) Pick List selection from sheet
    with st.spinner("Loading pick lists..."):
        try:
            df_sheet = load_sheet_csv(CSV_URL)
            available_picks = get_available_picks(df_sheet, selected_db)
        except Exception as e:
            st.error(f"Failed to load sheet or parse picks: {e}")
            df_sheet = pd.DataFrame()
            available_picks = []

    if not available_picks:
        st.warning("No available Pick Lists where Finish Packing is not empty and Nomor Matrix is not empty.")
        pick_numbers = st.multiselect("Pick List Number(s):", [])
    else:
        pick_numbers = st.multiselect("Pick List Number(s):", available_picks)

    # 3) Photo uploader (multiple)
    uploaded_files = st.file_uploader("Upload photos (JPG/PNG) — multiple allowed:", accept_multiple_files=True, type=["jpg", "jpeg", "png"])
    st.caption(f"Per-file raw limit: {MAX_BYTES_PER_FILE//1024//1024} MB. Total compressed limit: {MAX_TOTAL_BYTES//1024//1024} MB.")

    # Submit
    if st.button("✅ Submit"):
        # validations
        if not selected_db:
            st.warning("Please select a Database.")
            st.stop()
        if not pick_numbers:
            st.warning("Please select at least one Pick List number.")
            st.stop()
        if not uploaded_files:
            st.warning("Please upload at least one photo.")
            st.stop()

        # Process images: compress and check sizes
        processed = []
        total_compressed = 0
        errors = []
        for file in uploaded_files:
            try:
                raw = file.read()
            except Exception as e:
                errors.append(f"Failed to read {file.name}: {e}")
                continue

            # attempt compression
            compressed = compress_image_bytes(raw)
            # enforce per-file raw or compressed? original used raw threshold, keep that:
            if len(raw) > MAX_BYTES_PER_FILE and len(compressed) > MAX_BYTES_PER_FILE:
                errors.append(f"{file.name} too large even after compression ({len(compressed)/1024/1024:.1f} MB). Max per-file: {MAX_BYTES_PER_FILE/1024/1024:.0f} MB.")
                continue

            processed.append({"filename": file.name, "bytes": compressed})
            total_compressed += len(compressed)

        if errors:
            st.error("Errors processing images:")
            for e in errors:
                st.write("-", e)
            st.stop()

        if total_compressed > MAX_TOTAL_BYTES:
            st.error(f"Total compressed size {total_compressed/1024/1024:.1f} MB exceeds limit of {MAX_TOTAL_BYTES/1024/1024:.0f} MB. Reduce number/size of images.")
            st.stop()

        # Build payload
        timestamp_iso = datetime.now(ZoneInfo("Asia/Jakarta")).isoformat()
        photos_payload = []
        for p in processed:
            photos_payload.append({
                "filename": p["filename"],
                "content_b64": base64.b64encode(p["bytes"]).decode("utf-8")
            })

        payload = {
            "timestamp": timestamp_iso,
            "database": selected_db,
            "pick_lists": pick_numbers,
            "photos": photos_payload
        }

        # Send to Apps Script
        try:
            resp = requests.post(APPS_SCRIPT_URL, json=payload, timeout=60)
            if resp.status_code in (200, 201):
                st.success("✅ Submission successful.")
                # optionally show returned json
                try:
                    st.json(resp.json())
                except Exception:
                    st.write("Server response (non-JSON):")
                    st.write(resp.text)
            else:
                st.error(f"Server returned {resp.status_code}: {resp.text[:1000]}")
        except Exception as e:
            st.error(f"Failed to send payload: {e}")
