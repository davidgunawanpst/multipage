import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import base64

# --- WEBHOOK URLs ---
WEBHOOK_URL_PHOTO = "https://script.google.com/macros/s/AKfycbyU0Es-af_eXySSnP8njnNUBa6rePHZRYqzMG4kauYrpWNhStowLxs0E0mubY6C4np-cw/exec"
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbyU0Es-af_eXySSnP8njnNUBa6rePHZRYqzMG4kauYrpWNhStowLxs0E0mubY6C4np-cw/exec"

# --- Static lists ---
pic_list = [
    "Rikie Dwi Permana",
    "Idha Akhmad Sucahyo",
    "Rian Dinata",
    "Harimurti Krisandki",
    "Muchamad Mustofa",
    "Yogie Arie Wibowo"
]

receive_types = ["Turunan Kapal", "Servis", "Receive no PO"]

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
st.set_page_config(page_title="Manual Receive", layout="wide")
st.title("Manual Receive")

selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
selected_receive_type = st.selectbox("Type of Receive:", receive_types)
selected_db = st.selectbox("Database:", db_list)
remarks = st.text_input("Remarks (required):")

uploaded_files = st.file_uploader("Upload photos (unlimited):", accept_multiple_files=True, type=["jpg", "jpeg", "png"])

# --- Submit Button ---
if st.button("✅ Submit"):
    if not selected_receive_type:
        st.warning("Please select a type of receive.")
    elif not remarks.strip():
        st.warning("Remarks field is required. Please enter remarks.")
    elif not uploaded_files:
        st.warning("Please upload at least one photo.")
    else:
        timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d_%H-%M-%S")
        folder_name = f"Receive_{selected_receive_type}_{selected_db}_{timestamp}"

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
            "pic": selected_pic,
            "receive_type": selected_receive_type,
            "database": selected_db,
            "remarks": remarks,
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
            st.success("🎉 Submission completed successfully!")
        elif not photo_success and not data_success:
            st.error("🚨 Submission failed for both photo and data.")
        elif not photo_success:
            st.warning("⚠️ Data logged, but photo upload failed.")
        elif not data_success:
            st.warning("⚠️ Photos uploaded, but data logging failed.")
