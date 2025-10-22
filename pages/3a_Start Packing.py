import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from auth import check_password  # keep your auth

# Must be called before any other st.* UI calls
st.set_page_config(page_title="Packing Start", layout="wide")

# --- WEBHOOK URL ---
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbx6xwu7cRczDUK69Ghziz6Vv6Z5X8d8WD8D4OpKGSqq-izJOKMlqEYk-K0Z6Uu3I8O_5Q/exec"

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

    if st.button("✅ Submit"):
        # basic validation
        if not pick_number or not pick_number.strip():
            st.warning("Nomor is required.")
        elif not valid_number(pick_number):
            st.warning("Nomor must contain digits only.")
        else:
            timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d_%H-%M-%S")
            data_payload = {
                "timestamp": timestamp,
                "pic": selected_pic,
                "database": selected_db,
                "startedpl": pick_number.strip(),
            }

            try:
                with st.spinner("Sending..."):
                    resp = requests.post(WEBHOOK_URL_DATA, json=data_payload, timeout=20)
                if resp.status_code in (200, 201):
                    st.success("🎉 Submission completed successfully!")
                else:
                    st.error(f"❌ Data logging failed: {resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(f"❌ Network/error sending data: {e}")
