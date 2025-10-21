import streamlit as st
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import base64
from auth import check_password

# --- WEBHOOK URLs (same as yours) ---
WEBHOOK_URL_PHOTO = "https://script.google.com/macros/s/AKfycbx8XeDj6cqfVuxGuHknaFq8aO9Ze-xvswMSBjsieFi5RobfixcvLmtKITFiN3VImNonBA/exec"
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbx8XeDj6cqfVuxGuHknaFq8aO9Ze-xvswMSBjsieFi5RobfixcvLmtKITFiN3VImNonBA/exec"

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
if check_password():
    # Keep same page config/title behavior you had
    st.set_page_config(page_title="Packing", layout="wide")
    st.title("📦 Packing Module")

    # --- Minimal inputs only ---
    selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)

    db_options = ["DMI", "PKS", "PBN", "PMT", "PSM", "PSS", "PST"]
    selected_db = st.selectbox("Database:", db_options)

    selected_pl = st.text_input("Pick List Number:")

    # Dynamic packaging options: newline-separated list (simple and flexible)
    st.markdown("**Packaging Options** — enter one option per line (leave blank if none).")
    packaging_text = st.text_area("Packaging options (one per line):", height=140, placeholder="Box A\nBubble wrap\nPallet 1")

    # --- Upload Proof Photos (unchanged) ---
    uploaded_files = st.file_uploader("Upload photos (unlimited):", accept_multiple_files=True, type=["jpg", "jpeg", "png"])

    # --- Submit Button ---
    if st.button("✅ Packed"):
        if not selected_pl:
            st.warning("Please enter a Pick List Number.")
        elif not uploaded_files:
            st.warning("Please upload at least one photo.")
        else:
            # parse packaging options into list (trim empties)
            packaging_options = [line.strip() for line in packaging_text.splitlines() if line.strip()]

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
                photo_response = requests.post(WEBHOOK_URL_PHOTO, json=photo_payload, timeout=60)
                if photo_response.status_code == 200:
                    try:
                        json_resp = photo_response.json()
                        drive_folder_url = json_resp.get("folderUrl", "UPLOAD_FAILED")
                        st.success("✅ Photos uploaded successfully.")
                        if drive_folder_url != "UPLOAD_FAILED":
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
                "pick_list": str(selected_pl)
