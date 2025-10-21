import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import base64

# --- CONFIGURE GOOGLE SHEET SOURCE ---
SHEET_ID = "1viV03CJxPsK42zZyKI6ZfaXlLR62IbC0O3Lbi_hfGRo"
SHEET_NAME = "PL"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

# --- WEBHOOK URLs ---
WEBHOOK_URL_PHOTO = "https://script.google.com/macros/s/AKfycbx8XeDj6cqfVuxGuHknaFq8aO9Ze-xvswMSBjsieFi5RobfixcvLmtKITFiN3VImNonBA/exec"
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbx8XeDj6cqfVuxGuHknaFq8aO9Ze-xvswMSBjsieFi5RobfixcvLmtKITFiN3VImNonBA/exec"

# --- Load data ---
@st.cache_data
def load_packing_data():
    df = pd.read_csv(CSV_URL)
    df.columns = df.columns.str.strip()
    return df

# --- Static PIC Dropdown ---
pic_list = [
    "Rikie Dwi Permana",
    "Idha Akhmad Sucahyo",
    "Rian Dinata",
    "Harimurti Krisandki",
    "Muchamad Mustofa",
    "Yogie Arie Wibowo"
]

# --- UI ---
import streamlit as st
from auth import check_password

if check_password():
        st.set_page_config(page_title="Packing", layout="wide")
        st.title("📦 Packing Module")
        
        df = load_packing_data()
        
        # --- Check required columns ---
        if "Nama Perusahaan" not in df.columns or "Pick Number" not in df.columns:
            st.error("❌ Required columns not found in the Google Sheet!")
            st.stop()
        
        # --- Dropdowns ---
        selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
        
        db_options = ["DMI","PKS","PBN","PMT","PSM","PSS","PST"]
        selected_db = st.selectbox("Database (Nama Perusahaan):", db_options)
        
        selected_pl = st.text_input("Pick List Number:")
        
        # --- Upload Proof Photos ---
        uploaded_files = st.file_uploader("Upload photos (unlimited):", accept_multiple_files=True, type=["jpg", "jpeg", "png"])
        
        # --- Submit Button ---
        if st.button("✅ Packed"):
            if not selected_pl:
                st.warning("Please select a Pick List Number.")
            elif not uploaded_files:
                st.warning("Please upload at least one photo.")
            else:
                timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d_%H-%M-%S")
                folder_name = f"Packing_{selected_db}_{selected_pl}_{timestamp}"
        
                # --- Step 1: Upload Photos ---
                photo_payload = {
                    "folder_name": folder_name,
                    "images": [
                        {
                            "filename": file.name,
                            "content": base64.b64encode(file.read()).decode("utf-8")
                        }
                        for file in uploaded_files
                    ]
                }
        
                drive_folder_url = "UPLOAD_FAILED"
                photo_success = False
        
                try:
                    photo_response = requests.post(WEBHOOK_URL_PHOTO, json=photo_payload)
                    if photo_response.status_code == 200:
                        try:
                            json_resp = photo_response.json()
                            drive_folder_url = json_resp.get("folderUrl", "UPLOAD_FAILED")
                            st.success("✅ Photos uploaded successfully.")
                            st.markdown(f"[📂 View uploaded folder]({drive_folder_url})")
                            photo_success = True
                        except Exception as e:
                            st.error(f"❌ Failed to parse photo upload response: {e}")
                    else:
                        st.error(f"❌ Photo upload failed: {photo_response.status_code} - {photo_response.text}")
                except Exception as e:
                    st.error(f"❌ Photo upload error: {e}")
        
                # --- Step 2: Send Metadata ---
                data_payload = {
                    "timestamp": timestamp,
                    "database": selected_db,
                    "pic": selected_pic,
                    "pick_list": str(selected_pl),
                    "done_packing": "Yes",
                    "drive_folder_link": drive_folder_url
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
                if photo_success and data_success:
                    st.success("🎉 Packing submission completed successfully!")
                elif not photo_success and not data_success:
                    st.error("🚨 Submission failed for both photo and data.")
                elif not photo_success:
                    st.warning("⚠️ Data logged, but photo upload failed.")
                elif not data_success:
                    st.warning("⚠️ Photos uploaded, but data logging failed.")
