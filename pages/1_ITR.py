import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from auth import check_password  # keep your auth

# Must be called before any other st.* UI calls
st.set_page_config(page_title="ITR", layout="wide")

# --- WEBHOOK URL ---
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbxvDwTeIaF99CBeZXCTx_IMgc0n_j5M3Brv_qKReSpxx7vgaS7dStLOz64RQ4eYscj-LA/exec"

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

def valid_itr(itr: str) -> bool:
    """Validates ITR format: exactly 9 digits, starts with '2'."""
    if not itr:
        return False
    itr = itr.strip()
    return len(itr) == 9 and itr.isdigit() and itr.startswith("2")

if check_password():
    st.title("ITR")

    selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
    selected_db = st.selectbox("Database:", db_list)
    no_itr = st.text_input("Nomor ITR (format: 2xxxxxxxx, 9 digits):", max_chars=9, placeholder="e.g. 200123456")

    if st.button("✅ Submit"):
        # basic validation
        if not no_itr or not no_itr.strip():
            st.warning("Nomor ITR is required.")
        elif not valid_itr(no_itr):
            st.warning("Nomor ITR must be exactly 9 digits, start with '2', and contain digits only (e.g. 2XXXXXXXX).")
        else:
            timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d_%H-%M-%S")
            data_payload = {
                "timestamp": timestamp,
                "pic": selected_pic,
                "database": selected_db,
                "nomor_itr": no_itr.strip(),
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
