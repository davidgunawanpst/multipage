import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from io import StringIO
import base64
from auth import check_password

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

# === Utility functions ===

def load_sheet_csv(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))


def extract_from_unique_code(unique_code_value):
    """Extract fallback Pick List from 'Unique Code' column (e.g. 'DMI|DMI-Manual-1' → 'DMI-Manual-1')."""
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


def get_available_picks(df: pd.DataFrame, selected_db: str) -> list:
    """
    Return Pick List numbers for selected DB where:
      - Start Packing is present
      - Finish Packing is empty
    Combines numeric and string pick numbers.
    """
    df = df.copy()
    df.columns = df.columns.str.strip()

    required = {"Database", "Pick List NO.", "Start Packing", "Finish Packing"}
    if not required.issubset(set(df.columns)):
        missing = required - set(df.columns)
        raise ValueError(f"Sheet missing required columns: {missing}")

    df["Database"] = df["Database"].astype(str).str.strip()

    # Handle blanks / None / NaN
    start_raw = df["Start Packing"]
    finish_raw = df["Finish Packing"]

    start_has_value = ~(start_raw.isna() | (start_raw.astype(str).str.strip().str.lower().isin(['', 'nan', 'none'])))
    finish_empty = (finish_raw.isna() | (finish_raw.astype(str).str.strip().str.lower().isin(['', 'nan', 'none'])))

    filtered = df[(df["Database"] == selected_db) & (start_has_value) & (finish_empty)].copy()

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

    # Deduplicate while keeping order
    seen = set()
    ordered = []
    for p in picks:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    # Sort numbers first, then strings
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

    # Load Sheet
    try:
        with st.spinner("Loading pick list from Google Sheet..."):
            df_sheet = load_sheet_csv(CSV_URL)
            available_picks = get_available_picks(df_sheet, selected_db)
    except Exception as e:
        st.error(f"❌ Failed to load Google Sheet: {e}")
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

    # --- Submit ---
    if st.button("✅ Submit"):
        if not selected_pic.strip():
            st.warning("Please fill in Nama PIC.")
        elif not selected_db.strip():
            st.warning("Please fill in Database.")
        elif not pick_numbers:
            st.warning("Please select at least one Pick List number.")
        elif not uploaded_files:
            st.warning("Please upload at least one photo.")
        else:
            timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")
            picks_csv = ", ".join(pick_numbers)
            safe_picks_join = "_".join(pick_numbers)
            folder_name = f"Outbound_{selected_db}_{safe_picks_join}"

            # === Upload Photos ===
            try:
                images_payload = []
                for file in uploaded_files:
                    file_bytes = file.read()
                    images_payload.append({
                        "filename": file.name,
                        "content": base64.b64encode(file_bytes).decode("utf-8")
                    })

                photo_payload = {"folder_name": folder_name, "images": images_payload}
                drive_folder_url = "UPLOAD_FAILED"
                photo_success = False

                photo_response = requests.post(WEBHOOK_URL_PHOTO, json=photo_payload, timeout=60)
                if photo_response.status_code == 200:
                    json_resp = photo_response.json()
                    drive_folder_url = json_resp.get("folderUrl", "UPLOAD_FAILED")
                    st.success("✅ Photos uploaded successfully.")
                    if drive_folder_url != "UPLOAD_FAILED":
                        st.markdown(f"[📂 View uploaded folder]({drive_folder_url})")
                    photo_success = True
                else:
                    st.error(f"❌ Photo upload failed: {photo_response.status_code} - {photo_response.text}")
            except Exception as e:
                st.error(f"❌ Photo upload error: {e}")
                photo_success = False
                drive_folder_url = "UPLOAD_FAILED"

            # === Log Data ===
            data_payload = {
                "timestamp": timestamp,
                "PIC": selected_pic,
                "database": selected_db,
                "finishpl": picks_csv,
                "jumlah_peti": jumlah_peti,
                "peti_details": peti_details,
                "jumlah_dus": jumlah_dus,
                "dus_details": dus_details,
                "jumlah_plastik": jumlah_plastik,
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
                    st.error(f"❌ Data logging failed: {data_response.status_code} - {data_response.text}")
            except Exception as e:
                st.error(f"❌ Logging error: {e}")

            if photo_success and data_success:
                st.success("🎉 Submission completed successfully!")
            elif not photo_success and not data_success:
                st.error("🚨 Submission failed for both photo and data.")
            elif not photo_success:
                st.warning("⚠️ Data logged, but photo upload failed.")
            elif not data_success:
                st.warning("⚠️ Photos uploaded, but data logging failed.")
