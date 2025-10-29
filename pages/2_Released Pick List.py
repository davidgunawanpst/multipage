import streamlit as st
import requests
from datetime import datetime, date
from zoneinfo import ZoneInfo
from auth import check_password  # keep your auth

# Must be called before any other st.* UI calls
st.set_page_config(page_title="Released Pick List", layout="wide")

# --- WEBHOOK URL ---
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbxWbgUXQ5qjCCbxnxLpY7Pny_vXyK8wJ1P4G0mSFbdUil8ETYyNKrIVfCHKUMufh6PLVw/exec"

# --- Static lists ---
pic_list = [
    "Rikie Dwi Permana",
    "Idha Akhmad Sucahyo",
    "Rian Dinata",
    "Harimurti Krisandki",
    "Muchamad Mustofa",
    "Yogie Arie Wibowo"
]

db_list = [
    "DMI", "PBN", "PKS", "PMT", "PSS", "PSM", "PST"
]

def valid_number(value: str) -> bool:
    """Validates that the input contains only digits (non-empty)."""
    if not value:
        return False
    value = value.strip()
    return value.isdigit()

if check_password():
    st.title("Pick List")

    selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
    selected_db = st.selectbox("Database:", db_list)
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
        else:
            # --- Format dates as DD/MM/YYYY ---
            input_date_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")
            req_date_str = requirement_date.strftime("%d/%m/%Y")

            # --- Structured payload ---
            data_payload = {
                "database": selected_db,
                "nomor_pl": pick_number.strip(),
                "pic": selected_pic,
                "input_date": input_date_str,
                "requirement_date": req_date_str,
            }

            try:
                with st.spinner("Sending..."):
                    resp = requests.post(WEBHOOK_URL_DATA, json=data_payload, timeout=20)
                if resp.status_code in (200, 201):
                    st.success("🎉 Submission completed successfully!")
                    st.json(data_payload)  # optional, show payload for debug
                else:
                    st.error(f"❌ Data logging failed: {resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(f"❌ Network/error sending data: {e}")
