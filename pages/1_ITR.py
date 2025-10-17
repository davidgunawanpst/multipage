import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import base64

# --- WEBHOOK URLs ---
WEBHOOK_URL_PHOTO = "[INSERT WEBHOOK URL]"
WEBHOOK_URL_DATA = "[INSERT WEBHOOK URL]"

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
    "DMI",
    "PBN",
    "PKS",
    "PMT",
    "PSS",
    "PSM",
    "PST"
]

# --- UI ---
import streamlit as st
from auth import check_password

if check_password():
        st.set_page_config(page_title="Manual Receive", layout="wide")
        st.title("Manual Receive")
        
        selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
        selected_db = st.selectbox("Database:", db_list)
        no_itr = st.text_input("Nomor ITR (required):")
        
        # --- Submit Button ---
        if st.button("✅ Submit"):
            if not selected_receive_type:
                st.warning("Please select a type of receive.")
            elif not remarks.strip():
                st.warning("Remarks field is required. Please enter remarks.")
            else:
                timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d_%H-%M-%S")
                # --- Send Metadata ---
                data_payload = {
                    "timestamp": timestamp,
                    "pic": selected_pic,
                    "database": selected_db,
                    "nomor_itr": no_itr,
                }
        
                data_success = False
                try:
                    data_response = requests.post(WEBHOOK_URL_DATA, json=data_payload)
                    if data_response.status_code == 200:
                        st.success("✅ Data logged successfully.")
                        data_success = True
                    else:
                        st.error(f"❌ Data logging failed: {data_response.status_code} - {data_response.text}")
                except Exception as e:
                    st.error(f"❌ Logging error: {e}")
        
                # --- Final Status ---
                if photo_success:
                    st.success("🎉 Submission completed successfully!")
                elif not data_success:
                    st.warning("⚠️ Data logging failed.")
