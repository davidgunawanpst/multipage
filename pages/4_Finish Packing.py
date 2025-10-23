import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import base64
from auth import check_password

# --- WEBHOOK URLs ---
WEBHOOK_URL_PHOTO = "https://script.google.com/macros/s/AKfycbysaJpVEdtQpiRuHJVgkheLw3sO4O-FC3XOW8SkxlBFjlE-9EP_fiqIhfVOCI0Gee_l/exec"  # ← replace with real photo webhook
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbysaJpVEdtQpiRuHJVgkheLw3sO4O-FC3XOW8SkxlBFjlE-9EP_fiqIhfVOCI0Gee_l/exec"

# --- PIC List ---
pic_list = [
    "Rikie Dwi Permana",
    "Idha Akhmad Sucahyo",
    "Rian Dinata",
    "Harimurti Krisandki",
    "Muchamad Mustofa",
    "Yogie Arie Wibowo"
]

if check_password():
    st.set_page_config(page_title="Finish Packing", layout="wide")
    st.title("Finish Packing")

    selected_pic = st.selectbox("PIC :", pic_list)
    db_list = ["DMI", "PBN", "PKS", "PMT", "PSS", "PSM", "PST"]
    selected_db = st.selectbox("Database:", db_list)
    pick_number = st.text_input("Nomor (numbers only):", placeholder="e.g. 12345")

    # --- Peti ---
    jumlah_peti = st.number_input("Jumlah Peti", min_value=0, step=1)
    peti_details = []
    for i in range(jumlah_peti):
        st.markdown(f"**Detail Peti #{i+1}**")
        berat = st.text_input(f"Berat Peti #{i+1} (Kg)")
        panjang = st.text_input(f"Panjang Peti #{i+1} (meter)")
        lebar = st.text_input(f"Lebar Peti #{i+1} (meter)")
        tinggi = st.text_input(f"Tinggi Peti #{i+1} (meter)")
        peti_details.append({"berat": berat, "panjang": panjang, "lebar": lebar, "tinggi": tinggi})

    # --- Dus ---
    jumlah_dus = st.number_input("Jumlah Dus", min_value=0, step=1)
    dus_details = []
    for i in range(jumlah_dus):
        st.markdown(f"**Detail Dus #{i+1}**")
        berat = st.text_input(f"Berat Dus #{i+1} (Kg)")
        panjang = st.text_input(f"Panjang Dus #{i+1} (meter)")
        lebar = st.text_input(f"Lebar Dus #{i+1} (meter)")
        tinggi = st.text_input(f"Tinggi Dus #{i+1} (meter)")
        dus_details.append({"berat": berat, "panjang": panjang, "lebar": lebar, "tinggi": tinggi})

    # --- Plastik ---
    jumlah_plastik = st.number_input("Jumlah Plastik", min_value=0, step=1)
    plastik_details = []
    for i in range(jumlah_plastik):
        st.markdown(f"**Detail Plastik #{i+1}**")
        berat = st.text_input(f"Berat Plastik #{i+1} (Kg)")
        panjang = st.text_input(f"Panjang Plastik #{i+1} (meter)")
        lebar = st.text_input(f"Lebar Plastik #{i+1} (meter)")
        tinggi = st.text_input(f"Tinggi Plastik #{i+1} (meter)")
        plastik_details.append({"berat": berat, "panjang": panjang, "lebar": lebar, "tinggi": tinggi})

    jumlah_peti = int(jumlah_peti)
    jumlah_dus = int(jumlah_dus)
    jumlah_plastik = int(jumlah_plastik)

    # --- Upload Proof Photos ---
    uploaded_files = st.file_uploader("Upload photos (unlimited):", accept_multiple_files=True, type=["jpg", "jpeg", "png"])

    # --- Submit Button ---
    if st.button("✅ Submit"):
        if not selected_pic.strip():
            st.warning("Please fill in Nama PIC.")
        elif not selected_db.strip():
            st.warning("Please fill in Database.")
        elif not pick_number:
            st.warning("Please input Pick List Number.")
        elif not uploaded_files:
            st.warning("Please upload at least one photo.")
        else:
            timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d_%H-%M-%S")
            folder_name = f"Outbound_{selected_db}_{pick_number}"

            # Step 1: Upload Photos
            photo_payload = {
                "folder_name": folder_name,
                "images": [
                    {"filename": file.name, "content": base64.b64encode(file.read()).decode("utf-8")}
                    for file in uploaded_files
                ]
            }

            drive_folder_url = "UPLOAD_FAILED"
            photo_success = False

            try:
                photo_response = requests.post(WEBHOOK_URL_PHOTO, json=photo_payload, timeout=30)
                if photo_response.status_code == 200:
                    json_resp = photo_response.json()
                    drive_folder_url = json_resp.get("folderUrl", "UPLOAD_FAILED")
                    st.success("✅ Photos uploaded successfully.")
                    st.markdown(f"[📂 View uploaded folder]({drive_folder_url})")
                    photo_success = True
                else:
                    st.error(f"❌ Photo upload failed: {photo_response.status_code} - {photo_response.text}")
            except Exception as e:
                st.error(f"❌ Photo upload error: {e}")

            # Step 2: Send Metadata
            data_payload = {
                "timestamp": timestamp,   # ✅ added timestamp for Google Sheet record
                "PIC": selected_pic,
                "database": selected_db,
                "finishpl": pick_number,
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

            # Final Status
            if photo_success and data_success:
                st.success("🎉 Submission completed successfully!")
            elif not photo_success and not data_success:
                st.error("🚨 Submission failed for both photo and data.")
            elif not photo_success:
                st.warning("⚠️ Data logged, but photo upload failed.")
            elif not data_success:
                st.warning("⚠️ Photos uploaded, but data logging failed.")
