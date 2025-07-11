import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import base64

# --- CONFIGURE GOOGLE SHEET SOURCE ---
SHEET_ID = "1viV03CJxPsK42zZyKI6ZfaXlLR62IbC0O3Lbi_hfGRo"
SHEET_NAME = "Sheet4"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

# --- WEBHOOK URLs ---
WEBHOOK_URL_PHOTO = "https://script.google.com/macros/s/AKfycbwRiqR7TaqV1-odJHI1cTlTIOS576QzscF4ADoSJkq0WK7TIwLHbja9hlvc5NDrbUy41A/exec"
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbwRiqR7TaqV1-odJHI1cTlTIOS576QzscF4ADoSJkq0WK7TIwLHbja9hlvc5NDrbUy41A/exec"

# --- Load data ---
@st.cache_data
def load_packing_data():
    df = pd.read_csv(CSV_URL)
    df.columns = df.columns.str.strip()
    return df

# --- UI ---
st.set_page_config(page_title="Outbound", layout="wide")
st.title("Outbound")

df = load_packing_data()

# --- Dropdowns & inputs ---
nama_ekspedisi = st.text_input("Nama Ekspedisi")
tujuan = st.text_input("Tujuan")
nomor_matrix = st.text_input("Nomor Matrix")
nomor_po = st.text_input("Nomor PO")

db_options = sorted(df["Nama Perusahaan"].dropna().astype(str).str.strip().unique())
selected_db = st.selectbox("Database (Nama Perusahaan):", db_options)

# Filter PL numbers based on selected_db
filtered_df = df[df["Nama Perusahaan"] == selected_db]
pl_list = sorted(filtered_df["Pick Number"].dropna().unique())

selected_pl = st.multiselect("Nomor Pick List:", pl_list)
selected_pl = [str(pl) for pl in selected_pl]

# --- Peti ---
jumlah_peti = st.number_input("Jumlah Peti", min_value=0, step=1)
peti_details = []
for i in range(jumlah_peti):
    st.markdown(f"**Detail Peti #{i+1}**")
    berat = st.text_input(f"Berat Peti #{i+1} (Kg)")
    dimensi = st.text_input(f"Dimensi Peti #{i+1} (CBM)")
    peti_details.append({"berat": berat, "dimensi": dimensi})

# --- Dus ---
jumlah_dus = st.number_input("Jumlah Dus", min_value=0, step=1)
dus_details = []
for i in range(jumlah_dus):
    st.markdown(f"**Detail Dus #{i+1}**")
    berat = st.text_input(f"Berat Dus #{i+1} (Kg)")
    dimensi = st.text_input(f"Dimensi Dus #{i+1} (CBM)")
    dus_details.append({"berat": berat, "dimensi": dimensi})

# --- Plastik ---
jumlah_plastik = st.number_input("Jumlah Plastik", min_value=0, step=1)
plastik_details = []
for i in range(jumlah_plastik):
    st.markdown(f"**Detail Plastik #{i+1}**")
    berat = st.text_input(f"Berat Plastik #{i+1} (Kg)")
    dimensi = st.text_input(f"Dimensi Plastik #{i+1} (CBM)")
    plastik_details.append({"berat": berat, "dimensi": dimensi})
jumlah_peti = int(jumlah_peti)
jumlah_dus = int(jumlah_dus)
jumlah_plastik = int(jumlah_plastik)
# --- Upload Proof Photos ---
uploaded_files = st.file_uploader("Upload photos (unlimited):", accept_multiple_files=True, type=["jpg", "jpeg", "png"])

# --- Submit Button ---
if st.button("✅ Submit"):
    if not nama_ekspedisi.strip():
        st.warning("Please fill in Nama Ekspedisi.")
    elif not tujuan.strip():
        st.warning("Please fill in Tujuan.")
    elif not nomor_matrix.strip():
        st.warning("Please fill in Nomor Matrix")
    elif not selected_pl:
        st.warning("Please select at least one Pick List Number.")
    elif not uploaded_files:
        st.warning("Please upload at least one photo.")
    else:
        timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d_%H-%M-%S")
        folder_name = f"Outbound_{selected_db}_{selected_pl}"

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
            photo_response = requests.post(WEBHOOK_URL_PHOTO, json=photo_payload)
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
            "timestamp": timestamp,
            "database": selected_db,
            "nama_ekspedisi": nama_ekspedisi,
            "tujuan": tujuan,
            "nomor_matrix": nomor_matrix,
            "nomor_po": nomor_po,
            "nomor_pick_list": selected_pl,
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
            data_response = requests.post(WEBHOOK_URL_DATA, json=data_payload)
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
