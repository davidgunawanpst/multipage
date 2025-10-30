import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from io import StringIO
from auth import check_password  # your auth module

# --- PAGE CONFIG ---
st.set_page_config(page_title="Released Pick List", layout="wide")

# --- WEBHOOK URL ---
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbwevKRUTmhsGL3pODzZOTTfOevcheEirORDr6MNt7jx2F31xMkCUYziMbZm4mV4c7Dkcg/exec"

# --- GOOGLE SHEETS ---
VESSEL_SHEET_ID = "18rlYmNpArAvEZrD3yyy7iAFDpHvFqEvN7pvztb1VcVM"
VESSEL_SHEET_NAME = "Vessel Name"
VESSEL_CSV_URL = f"https://docs.google.com/spreadsheets/d/{VESSEL_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={VESSEL_SHEET_NAME}"

MANUAL_PICKLIST_SHEET_NAME = "Manual Pick List"
MANUAL_PICKLIST_CSV_URL = f"https://docs.google.com/spreadsheets/d/{VESSEL_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={MANUAL_PICKLIST_SHEET_NAME}"

# --- STATIC LISTS ---
pic_list = [
    "Rikie Dwi Permana",
    "Idha Akhmad Sucahyo",
    "Rian Dinata",
    "Harimurti Krisandki",
    "Muchamad Mustofa",
    "Yogie Arie Wibowo"
]
db_list = ["DMI", "PBN", "PKS", "PMT", "PSS", "PSM", "PST"]

# --- HELPERS ---
@st.cache_data(ttl=600)
def load_csv(url: str) -> pd.DataFrame:
    """Generic CSV loader with safe fallback."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Failed to load sheet: {e}")
        return pd.DataFrame()

def valid_number(value: str) -> bool:
    """Check numeric input."""
    if not value:
        return False
    return value.strip().isdigit()

# --- APP ---
if check_password():
    st.title("Released Pick List")

    selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
    selected_db = st.selectbox("Database:", db_list)
    release_type = st.radio("Release Type:", ["Normal", "Manual"])
    urgent = st.radio("Urgent?", ["Normal", "Urgent"])

    # --- Load Vessel Data ---
    df_vessel = load_csv(VESSEL_CSV_URL)
    vessels_for_db = df_vessel[df_vessel["DB"].astype(str).str.strip() == selected_db]
    vessel_options = sorted(vessels_for_db["Vessel Name"].dropna().astype(str).unique().tolist())

    if not vessel_options:
        vessel_name = st.text_input("Vessel Name (no entry in sheet, type manually):")
    else:
        vessel_name = st.selectbox("Vessel Name:", vessel_options)

    today_jkt = datetime.now(ZoneInfo("Asia/Jakarta")).date()
    requirement_date = st.date_input(
        "Requirement Date (click calendar):",
        value=today_jkt,
        help="Pick the required date (click the calendar icon)."
    )

    # --- Normal Flow ---
    if release_type == "Normal":
        pick_number = st.text_input("Nomor PL (numbers only):", placeholder="e.g. 12345")

    # --- Manual Flow ---
    else:
        st.info("Manual mode active. Pick List number will be generated automatically.")
        df_manual = load_csv(MANUAL_PICKLIST_CSV_URL)
        next_number = 1
        if not df_manual.empty and "Nomor" in df_manual.columns:
            try:
                existing_numbers = pd.to_numeric(df_manual["Nomor"], errors="coerce").dropna()
                if not existing_numbers.empty:
                    next_number = int(existing_numbers.max()) + 1
            except Exception:
                pass

        kode_picklist_manual = f"{selected_db}-Manual-{next_number}"
        st.write(f"🧾 **Generated Pick List Code:** `{kode_picklist_manual}`")

        remarks = st.text_input("Remarks (e.g. Vendor - Barang):")

    # --- Submit Button ---
    if st.button("✅ Submit"):
        input_date_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")
        req_date_str = requirement_date.strftime("%d/%m/%Y")

        # Basic validation
        if not vessel_name or not vessel_name.strip():
            st.warning("Please select or enter a Vessel Name.")
        elif release_type == "Normal" and not valid_number(pick_number):
            st.warning("Nomor PL must contain digits only.")
        elif release_type == "Manual" and not remarks.strip():
            st.warning("Please fill in Remarks (Vendor - Barang).")
        else:
            # --- Payload Build ---
            if release_type == "Normal":
                data_payload = {
                    "release_type": "Normal",
                    "database": selected_db,
                    "nomor_pl": pick_number.strip(),
                    "vessel_name": vessel_name.strip(),
                    "pic": selected_pic,
                    "input_date": input_date_str,
                    "requirement_date": req_date_str,
                    "urgent_status": urgent
                }
            else:
                data_payload = {
                    "release_type": "Manual",
                    "database": selected_db,
                    "pic": selected_pic,
                    "nomor": next_number,
                    "kode_picklist_manual": kode_picklist_manual,
                    "vessel_name": vessel_name.strip(),
                    "remarks": remarks.strip(),
                    "input_date": input_date_str,
                    "requirement_date": req_date_str,
                    "urgent_status":urgent
                }

            # --- Send to Webhook ---
            try:
                with st.spinner("Sending data to server..."):
                    resp = requests.post(WEBHOOK_URL_DATA, json=data_payload, timeout=25)
                if resp.status_code in (200, 201):
                    st.success("🎉 Submission completed successfully!")
                    st.json(data_payload)
                else:
                    st.error(f"❌ Data logging failed: {resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(f"❌ Network/error sending data: {e}")
