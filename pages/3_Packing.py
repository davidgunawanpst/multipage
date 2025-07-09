import streamlit as st
import requests
from datetime import datetime
import base64

st.set_page_config(page_title="Packing", layout="wide")
st.title("📦 Packing Module")

# 1. PIC Name
pic_list = [
    "Rikie Dwi Permana", "Idha Akhmad Sucahyo", "Rian Dinata",
    "Harimurti Krisandki", "Muchamad Mustofa", "Yogie Arie Wibowo"
]
selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)

# 2. Database (temporary static, later populated via Apps Script if needed)
selected_db = st.selectbox("Database:", ["DMI", "PKS", "PMT", "PSM", "PSS", "PST"])

# 3. Pick List Number
pick_list = st.text_input("Pick List Number (type or paste):")

# 4. Upload Photos
uploaded_files = st.file_uploader("Upload photos (unlimited):", accept_multiple_files=True, type=["jpg", "jpeg", "png"])

# 5. Packed Button
if st.button("✅ Packed"):
    if not pick_list:
        st.warning("Please enter a Pick List Number.")
    elif not uploaded_files:
        st.warning("Please upload at least one photo.")
    else:
        # Prepare data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        images_base64 = []

        for file in uploaded_files:
            b64 = base64.b64encode(file.read()).decode()
            images_base64.append({
                "filename": file.name,
                "content": b64
            })

        payload = {
            "timestamp": timestamp,
            "database": selected_db,
            "pic": selected_pic,
            "pick_list": pick_list,
            "photos": images_base64
        }

        # Send to Apps Script Web App
        webhook_url = "https://script.google.com/macros/s/YOUR_WEBAPP_ID/exec"
        response = requests.post(webhook_url, json=payload)

        if response.status_code == 200:
            result = response.json()
            st.success("Packed data submitted successfully!")
            st.markdown(f"📁 [View uploaded folder]({result.get('drive_folder_url')})")
        else:
            st.error(f"Failed to submit data. Error: {response.text}")
