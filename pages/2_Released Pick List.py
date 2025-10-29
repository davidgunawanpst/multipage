import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from io import StringIO
from auth import check_password  # keep your auth

# --- PAGE CONFIG ---
st.set_page_config(page_title="Released Pick List", layout="wide")

# --- WEBHOOK URL ---
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbxWbgUXQ5qjCCbxnxLpY7Pny_vXyK8wJ1P4G0mSFbdUil8ETYyNKrIVfCHKUMufh6PLVw/exec"

# --- GOOGLE SHEET: VESSEL LIST ---
VESSEL_SHEET_ID = "18rlYmNpArAvEZrD3yyy7iAFDpHvFqEvN7pvztb1VcVM"
VESSEL_SHEET_NAME = "Vessel Name"
VESSEL_CSV_URL = f"https://docs.google.com/spreadsheets/d/{VESSEL_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={VESSEL_SHEET_NAME}"

# --- Static lists ---
pic_list = [
    "Rikie Dwi Permana",
    "Idha Akhmad Sucahyo",
    "Rian Dinata",
    "Harimurti Krisandki",
    "Muchamad Mustofa",
    "Yogie Arie Wibowo"
]

db_list = ["DMI", "PBN", "PKS", "PMT", "PSS", "PSM", "PST"]

# --- Helper functions ---
def valid_number(value: str) -> bool:
    """Validates that the input contains only digits (non-empty)."""
    if not value:
        return False
    value = value.strip()
    return value.isdigit()

@st.cache_data(ttl=600)
def load_vessel_data(url: str) -> pd.DataFrame:
    """Load the Vessel sheet as a DataFrame."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Failed to load vessel list: {e}")
        return pd.DataFrame(columns=["DB", "Vessel Name"])

# --- APP ---
if check_password():
    st.title("Released Pick List")

    selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
    selected_db = st.selectbox("Database:", db_list)

    # Load vessel data
    df_vessel = load_vessel_data(VESSEL_CSV_URL)

    # Filter vessels by DB
    vessels_for_db = df_vessel[df_vessel["DB"].astype(str).str.strip() == selected_db]
    vessel_options = sorted(vessels_for_db["Vessel Name"].dropna().astype(str).unique().tolist())

    if not vessel_options:
        vessel_name = st.text_input("Vessel Name (no entry in sheet, type manually):")
    else:
        vessel_name = st.selectbox("Vessel Name:", vessel_options)

    pick_number = st.text_input("Nomor (numbers only):", placeholder="e.g. 12345")

    # Calendar input for Requirement Date
    today_jkt = datetime.now(ZoneInfo("Asia/Jakarta")).date()
    requirement_date = st.date_input(
        "Requirement Date (click calendar):",
        value=today_jkt,
        help="Pick the required date (click the calendar icon)."
    )

    if st.button("✅ Submit"):
        # Basic validation
        if not pick_number or not pick_number.strip():
            st.warning("Nomor is required.")
        elif not valid_number(pick_number):
            st.warning("Nomor must contain digits only.")
        elif not vessel_name or not vessel_name.strip():
            st.warning("Please select or enter a Vessel Name.")
        else:
            # Format dates
            input_date_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")
            req_date_str = requirement_date.strftime("%d/%m/%Y")

            # Build payload
            data_payload = {
                "database": selected_db,
                "nomor_pl": pick_number.strip(),
                "pic": selected_pic,
                "vessel_name": vessel_name.strip(),
                "input_date": input_date_str,
                "requirement_date": req_date_str,
            }

            try:
                with st.spinner("Sending..."):
                    resp = requests.post(WEBHOOK_URL_DATA, json=data_payload, timeout=20)
                if resp.status_code in (200, 201):
                    st.success("🎉 Submission completed successfully!")
                    st.json(data_payload)
                else:
                    st.error(f"❌ Data logging failed: {resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(f"❌ Network/error sending data: {e}")
