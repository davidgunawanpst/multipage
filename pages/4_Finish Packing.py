import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from io import StringIO, BytesIO
import base64
from auth import check_password

# Pillow for image compression
from PIL import Image

# --- WEBHOOK URLs ---
WEBHOOK_URL_PHOTO = "https://script.google.com/macros/s/AKfycbwJi6C7PDW3ZsoGSGrgKhMcEMMEE4hBVcuiKndyow9ifP7x_Nc_sru--TU_Jf6p8aGM/exec"
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbwJi6C7PDW3ZsoGSGrgKhMcEMMEE4hBVcuiKndyow9ifP7x_Nc_sru--TU_Jf6p8aGM/exec"

# --- Google Sheet details (public) ---
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
SHEET_NAME = "List All Packing"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

# --- PIC List ---
pic_list = [
    "Rikie Dwi Permana",
    "Idha Akhmad Sucahyo",
    "Rian Dinata",
    "Harimurti Krisandki",
    "Muchamad Mustofa",
    "Yogie Arie Wibowo"
]

# --- Upload / compression policy ---
MAX_BYTES_PER_FILE = 8 * 1024 * 1024   # 8 MB raw file allowed (before compression check)
MAX_TOTAL_BYTES = 40 * 1024 * 1024     # 40 MB total (after compression)
COMPRESS_MAX_WIDTH = 1600              # max image width in pixels (resize if wider)
COMPRESS_QUALITY = 80                  # JPEG quality (0-100)
UPLOAD_TIMEOUT = 60                    # seconds for requests.post
UPLOAD_RETRIES = 3                     # number of attempts per upload


# === Utility functions ===

def load_sheet_csv(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


def compress_image_bytes(file_bytes: bytes, max_width=COMPRESS_MAX_WIDTH, quality=COMPRESS_QUALITY) -> bytes:
    """
    Compress / resize image bytes and return new JPEG bytes.
    If the image is not convertible to JPEG, tries to save as PNG.
    """
    try:
        img = Image.open(BytesIO(file_bytes)).convert("RGB")
    except Exception:
        # if Pillow can't open, return original bytes
        return file_bytes

    # Resize if wider than max_width
    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    out_buf = BytesIO()
    # Save as JPEG to reduce size; fallback to PNG if JPEG fails
    try:
        img.save(out_buf, format="JPEG", quality=quality, optimize=True)
    except Exception:
        out_buf = BytesIO()
        img.save(out_buf, format="PNG", optimize=True)
    return out_buf.getvalue()


def post_with_retries(url: str, json_payload: dict, timeout=UPLOAD_TIMEOUT, retries=UPLOAD_RETRIES):
    """
    POST with simple exponential backoff retries; returns response or raises final exception.
    """
    import time
    backoff = 1
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, json=json_payload, timeout=timeout)
            return resp
        except requests.RequestException as e:
            last_exc = e
            if attempt == retries:
                raise
            time.sleep(backoff)
            backoff *= 2
    if last_exc:
        raise last_exc


# Extraction helpers (same logic as before)
def extract_from_unique_code(unique_code_value):
    if unique_code_value is None:
        return None
    try:
        if pd.isna(unique_code_value):
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


def clean_candidate(val):
    if val is None:
        return None
    try:
        if pd.isna(val):
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


def get_available_picks(df: pd.DataFrame, selected_db: str) -> list:
    df = df.copy()
    df.columns = df.columns.str.strip()

    required = {"Database", "Pick List NO.", "Start Packing", "Finish Packing"}
    if not required.issubset(set(df.columns)):
        missing = required - set(df.columns)
        raise ValueError(f"Sheet missing required columns: {missing}")

    df["Database"] = df["Database"].astype(str).str.strip()

    start_raw = df["Start Packing"]
    finish_raw = df["Finish Packing"]

    start_has_value = ~(start_raw.isna() | (start_raw.astype(str).str.strip().str.lower().isin(['', 'nan', 'none'])))
    finish_empty = (finish_raw.isna() | (finish_raw.astype(str).str.strip().str.lower().isin(['', 'nan', 'none'])))

    filtered = df[(df["Database"] == selected_db) & (start_has_value) & (finish_empty)].copy()

    picks = []
    for _, row in filtered.iterrows():
        raw_pl = row.get("Pick List NO.", None)
        candidate = clean_candidate(raw_pl)
        if candidate is None:
            unique_val = row.get("Unique Code", None) if "Unique Code" in row.index else None
            extracted = extract_from_unique_code(unique_val)
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

    digits = [x for x in ordered if x.isdigit()]
    nondigits = [x for x in ordered if not x.isdigit()]
    digits_sorted = sorted(digits, key=lambda s: int(s))
    return digits_sorted + nondigits


# === Streamlit UI ===
if check_password():
    st.set_page_config(page_title="Finish Packing", layout="wide")
    st.title("📦 Finish Packing")

    selected_pic = st.selectbox("PIC :", pic_list)
    db_list = ["DMI", "PBN", "PKS", "PMT", "PSS", "PSM", "PST"]
    selected_db = st.selectbox("Database:", db_list)

    # Load sheet & create dropdown for pick numbers
    try:
        with st.spinner("Loading pick list from Google Sheet..."):
            df_sheet = load_sheet_csv(CSV_URL)
            available_picks = get_available_picks(df_sheet, selected_db)
    except Exception as e:
        st.error(f"❌ Failed to load Google Sheet: {e}")
        df_sheet = pd.DataFrame()
        available_picks = []

    if not available_picks:
        st.warning("No available Pick Lists where Start Packing exists and Finish Packing is empty.")
        pick_numbers = st.multiselect("Pick List Number(s):", [])
    else:
        pick_numbers = st.multiselect("Pick List Number(s):", available_picks)

    # --- Peti ---
    jumlah_peti = int(st.number_input("Jumlah Peti", min_value=0, step=1, value=0))
    peti_details = []
    for i in range(int(jumlah_peti)):
        st.markdown(f"**Detail Peti #{i+1}**")
        berat = st.text_input(f"Berat Peti #{i+1} (Kg)")
        panjang = st.text_input(f"Panjang Peti #{i+1} (cm)")
        lebar = st.text_input(f"Lebar Peti #{i+1} (cm)")
        tinggi = st.text_input(f"Tinggi Peti #{i+1} (cm)")
        peti_details.append({"berat": berat, "panjang": panjang, "lebar": lebar, "tinggi": tinggi})

    # --- Dus ---
    jumlah_dus = int(st.number_input("Jumlah Dus", min_value=0, step=1, value=0))
    dus_details = []
    for i in range(int(jumlah_dus)):
        st.markdown(f"**Detail Dus #{i+1}**")
        berat = st.text_input(f"Berat Dus #{i+1} (Kg)")
        panjang = st.text_input(f"Panjang Dus #{i+1} (cm)")
        lebar = st.text_input(f"Lebar Dus #{i+1} (cm)")
        tinggi = st.text_input(f"Tinggi Dus #{i+1} (cm)")
        dus_details.append({"berat": berat, "panjang": panjang, "lebar": lebar, "tinggi": tinggi})

    # --- Plastik ---
    jumlah_plastik = int(st.number_input("Jumlah Karung", min_value=0, step=1, value=0))
    plastik_details = []
    for i in range(int(jumlah_plastik)):
        st.markdown(f"**Detail Karung #{i+1}**")
        berat = st.text_input(f"Berat Karung #{i+1} (Kg)")
        panjang = st.text_input(f"Panjang Karung #{i+1} (cm)")
        lebar = st.text_input(f"Lebar Karung #{i+1} (cm)")
        tinggi = st.text_input(f"Tinggi Karung #{i+1} (cm)")
        plastik_details.append({"berat": berat, "panjang": panjang, "lebar": lebar, "tinggi": tinggi})

    # --- Upload Proof Photos ---
    uploaded_files = st.file_uploader("Upload photos (unlimited):", accept_multiple_files=True, type=["jpg", "jpeg", "png"])
    st.caption(f"Per-file limit: {MAX_BYTES_PER_FILE//1024//1024} MB raw. After compression total upload limit: {MAX_TOTAL_BYTES//1024//1024} MB.")

    # --- Submit Button ---
    if st.button("✅ Submit"):
        # Basic validation
        if not selected_pic or not selected_pic.strip():
            st.warning("Please fill in Nama PIC.")
            st.stop()
        if not selected_db or not selected_db.strip():
            st.warning("Please fill in Database.")
            st.stop()
        if not pick_numbers:
            st.warning("Please select at least one Pick List number.")
            st.stop()
        if not uploaded_files:
            st.warning("Please upload at least one photo.")
            st.stop()

        # Prepare folder name and timestamp
        timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")
        picks_csv = ", ".join(pick_numbers)
        safe_picks_join = "_".join(pick_numbers)
        folder_name = f"Outbound_{selected_db}_{safe_picks_join}"

        # === Step 1: Process & upload photos (one-by-one) ===
        images_payload_for_post = []
        total_compressed_bytes = 0
        photo_success = True
        photo_errors = []

        # First pass: read & compress, enforce per-file limit and total limit
        processed_images = []
        for file in uploaded_files:
            try:
                raw_bytes = file.read()
            except Exception as e:
                photo_success = False
                photo_errors.append(f"Failed to read file {file.name}: {e}")
                continue

            # Reject excessively large raw files up-front
            if len(raw_bytes) > MAX_BYTES_PER_FILE:
                # try compress anyway but warn
                compressed = compress_image_bytes(raw_bytes)
                if len(compressed) > MAX_BYTES_PER_FILE:
                    photo_success = False
                    photo_errors.append(f"File {file.name} is too large even after compression ({len(compressed)/1024/1024:.1f} MB). Max per-file: {MAX_BYTES_PER_FILE/1024/1024:.0f} MB.")
                    continue
            else:
                compressed = compress_image_bytes(raw_bytes)

            total_compressed_bytes += len(compressed)
            processed_images.append({"filename": file.name, "bytes": compressed})

        # Check total size
        if total_compressed_bytes > MAX_TOTAL_BYTES:
            photo_success = False
            photo_errors.append(f"Total compressed image size {total_compressed_bytes/1024/1024:.1f} MB exceeds limit of {MAX_TOTAL_BYTES/1024/1024:.0f} MB. Try fewer or smaller images.")

        # If any processing error happened, abort now and show messages
        if not photo_success:
            st.error("Photo upload aborted due to the following issues:")
            for e in photo_errors:
                st.write(f"- {e}")
            st.stop()

        # Now send images one-by-one with retries.
        # First image's request should create folder on server and return folderUrl (if your webhook supports that).
        drive_folder_url = "UPLOAD_FAILED"
        for idx, img in enumerate(processed_images):
            # Prepare base64
            b64 = base64.b64encode(img["bytes"]).decode("utf-8")
            payload = {
                "folder_name": folder_name,
                "images": [
                    {"filename": img["filename"], "content": b64}
                ]
            }

            try:
                resp = post_with_retries(WEBHOOK_URL_PHOTO, payload)
            except Exception as e:
                photo_success = False
                photo_errors.append(f"Network/error uploading {img['filename']}: {e}")
                # stop further uploads
                break

            # Evaluate response
            if resp.status_code != 200:
                # Server returned error; include body
                body = resp.text
                photo_success = False
                photo_errors.append(f"Server returned {resp.status_code} for {img['filename']}: {body[:1000]}")
                break

            # On success try to parse json and extract folderUrl if this is first image
            try:
                j = resp.json()
                if idx == 0 and isinstance(j, dict):
                    drive_folder_url = j.get("folderUrl", drive_folder_url)
            except Exception:
                # not JSON or no folderUrl — still ok
                pass

        # If photo upload failed, reject submission and show errors
        if not photo_success:
            st.error("Photo upload failed — submission aborted. See details:")
            for e in photo_errors:
                st.write(f"- {e}")
            st.stop()

        # === Step 2: Send metadata only if photos uploaded OK ===
        data_payload = {
            "timestamp": timestamp,
            "PIC": selected_pic,
            "database": selected_db,
            "finishpl": picks_csv,
            "jumlah_peti": int(jumlah_peti),
            "peti_details": peti_details,
            "jumlah_dus": int(jumlah_dus),
            "dus_details": dus_details,
            "jumlah_plastik": int(jumlah_plastik),
            "plastik_details": plastik_details,
            "drive_folder_link": drive_folder_url
        }

        data_success = False
        try:
            data_response = requests.post(WEBHOOK_URL_DATA, json=data_payload, timeout=30)
            if data_response.status_code == 200:
                st.success("✅ Data logged successfully.")
                data_success = True
            else:
                st.error(f"❌ Data logging failed: {data_response.status_code} - {data_response.text[:1000]}")
        except Exception as e:
            st.error(f"❌ Logging error: {e}")

        # Final status
        if data_success:
            st.success("🎉 Submission completed successfully!")
            if drive_folder_url and drive_folder_url != "UPLOAD_FAILED":
                st.markdown(f"[📂 View uploaded folder]({drive_folder_url})")
        else:
            st.error("Submission partially failed: photos uploaded but data logging failed.")
