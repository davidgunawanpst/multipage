import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from io import StringIO
import base64
from auth import check_password

# --- WEBHOOK URLs ---
WEBHOOK_URL_PHOTO = "https://script.google.com/macros/s/AKfycbxJ0WaJpIakFtUO4WfdDWrWfiekXeWMPJIeJWwTjcpERB1x-POBjTzCoXzXnDO15s4Q/exec"
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbxJ0WaJpIakFtUO4WfdDWrWfiekXeWMPJIeJWwTjcpERB1x-POBjTzCoXzXnDO15s4Q/exec"

# --- Google Sheet details (public) ---
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
SHEET_NAME = "SLA Packing"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

# --- Vessel Sheet ---
VESSEL_SHEET_ID = "18rlYmNpArAvEZrD3yyy7iAFDpHvFqEvN7pvztb1VcVM"
VESSEL_SHEET_NAME = "Vessel"
VESSEL_CSV_URL = f"https://docs.google.com/spreadsheets/d/{VESSEL_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={VESSEL_SHEET_NAME}"

# --- PIC List ---
pic_list = [
    "Rikie Dwi Permana",
    "Idha Akhmad Sucahyo",
    "Rian Dinata",
    "Harimurti Krisandki",
    "Muchamad Mustofa",
    "Yogie Arie Wibowo"
]

def load_sheet_csv(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))

def get_available_picks(df: pd.DataFrame, selected_db: str) -> list:
    df = df.copy()
    df.columns = df.columns.str.strip()

    required = {"Database", "Pick List NO.", "Start Packing", "Finish Packing"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"Sheet missing required columns: {required - set(df.columns)}")

    db_col = df["Database"].astype(str).str.strip()
    start_col = df["Start Packing"]
    finish_col = df["Finish Packing"]

    start_has_value = ~(start_col.isna() | (start_col.astype(str).str.strip() == ""))
    finish_empty = (finish_col.isna() | (finish_col.astype(str).str.strip() == ""))

    filtered = df[(db_col == selected_db) & start_has_value & finish_empty]

    def clean_pick(x):
        if pd.isna(x):
            return None
        if isinstance(x, float) and x.is_integer():
            return str(int(x))
        if isinstance(x, int):
            return str(x)
        return str(x).strip()

    picks_series = filtered["Pick List NO."].map(clean_pick).dropna().astype(str).str.strip()
    picks_unique = sorted(set(picks_series.tolist()))
    return picks_unique

def get_vessels_for_db(selected_db: str) -> list:
    """Fetch vessels from Vessel sheet for the selected DB"""
    try:
        df_vessel = load_sheet_csv(VESSEL_CSV_URL)
        df_vessel.columns = df_vessel.columns.str.strip()
        if not {"DB", "Vessel  Name"}.issubset(df_vessel.columns):
            return []
        df_filtered = df_vessel[df_vessel["DB"].astype(str).str.strip() == selected_db]
        vessels = sorted(set(df_filtered["Vessel  Name"].dropna().astype(str).str.strip()))
        return vessels
    except Exception as e:
        st.warning(f"⚠️ Could not load vessel list: {e}")
        return []

if check_password():
    st.set_page_config(page_title="Finish Packing", layout="wide")
    st.title("Finish Packing")

    selected_pic = st.selectbox("PIC :", pic_list)
    db_list = ["DMI", "PBN", "PKS", "PMT", "PSS", "PSM", "PST"]
    selected_db = st.selectbox("Database:", db_list)

    # --- Vessel selector (NEW) ---
    vessels = get_vessels_for_db(selected_db)
    if vessels:
        selected_vessel = st.selectbox("Vessel Name:", vessels)
    else:
        selected_vessel = st.text_input("Vessel Name (manual entry if not found):")

    # Load sheet & create dropdown for pick numbers
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

    # --- Submit Button ---
    if st.button("✅ Submit"):
        if not selected_pic or not selected_pic.strip():
            st.warning("Please fill in Nama PIC.")
        elif not selected_db or not selected_db.strip():
            st.warning("Please fill in Database.")
        elif not pick_numbers:
            st.warning("Please select at least one Pick List number.")
        elif not selected_vessel or not selected_vessel.strip():
            st.warning("Please select or input a Vessel Name.")
        elif not uploaded_files:
            st.warning("Please upload at least one photo.")
        else:
            timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")
            picks_csv = ", ".join(pick_numbers)
            safe_picks_join = "_".join(pick_numbers)
            folder_name = f"Outbound_{selected_db}_{safe_picks_join}"

            # Step 1: Upload Photos
            try:
                images_payload = []
                for file in uploaded_files:
                    file_bytes = file.read()
                    images_payload.append({
                        "filename": file.name,
                        "content": base64.b64encode(file_bytes).decode("utf-8")
                    })

                photo_payload = {
                    "folder_name": folder_name,
                    "images": images_payload
                }

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

            # Step 2: Send Metadata (payload field names preserved)
            data_payload = {
                "timestamp": timestamp,
                "PIC": selected_pic,
                "database": selected_db,
                "vessel_name": selected_vessel,     # 🆕 include vessel
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
                    st.error(f"❌ Data logging failed: {data_response.status_code} - {data_response.text}")
            except Exception as e:
                st.error(f"❌ Logging error: {e}")

            # Final Status
            if photo_success and data_success:
                st.success("🎉 Submission completed successfully!")
            elif not photo_success and not data_success:
                st.error("🚨 Submission failed for both photo and data.")
            elif not photo_success:
                st.warning("⚠️ Data logged, but photo upload failed.")
            elif not data_success:
                st.warning("⚠️ Photos uploaded, but data logging failed.")
