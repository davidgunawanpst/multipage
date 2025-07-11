import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import base64
from collections import Counter  # NEW

# --- CONFIGURE GOOGLE SHEET SOURCE ---
SHEET_ID = "1viV03CJxPsK42zZyKI6ZfaXlLR62IbC0O3Lbi_hfGRo"
SHEET_NAME = "Sheet2"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

# --- WEBHOOK URLs ---
WEBHOOK_URL_PHOTO = "https://script.google.com/macros/s/AKfycbzU8ymaN7CaQMevzbkVHIV0Tbl2jNkg4HGm3JzckFqFf_YQZXKs0Z_SJ-09XqkzHFi-/exec"
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbzU8ymaN7CaQMevzbkVHIV0Tbl2jNkg4HGm3JzckFqFf_YQZXKs0Z_SJ-09XqkzHFi-/exec"

# --- Load PO Data from Google Sheet ---
@st.cache_data
def load_po_data():
    df = pd.read_csv(CSV_URL)
    po_dict = {}
    for _, row in df.iterrows():
        db = row['Nama Perusahaan']
        po = str(row['PO Number'])
        item = row['Item Name Complete']
        if db not in po_dict:
            po_dict[db] = {}
        if po not in po_dict[db]:
            po_dict[db][po] = []
        po_dict[db][po].append(item)
    return df, po_dict

# --- Fixed PIC Dropdown ---
pic_list = [
    "Rikie Dwi Permana",
    "Idha Akhmad Sucahyo",
    "Rian Dinata",
    "Harimurti Krisandki",
    "Muchamad Mustofa",
    "Yogie Arie Wibowo"
]

# --- UI ---
st.set_page_config(page_title="Inbound Monitoring", layout="wide")
st.title("Inbound Monitoring Form")

df_master, database_data = load_po_data()

selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
selected_db = st.selectbox("Select Database:", list(database_data.keys()))
selected_po = st.selectbox("Select PO Number:", list(database_data[selected_db].keys()))

# --- Lookup PO PIC and Vendor ---
filtered_df = df_master[
    (df_master['Nama Perusahaan'] == selected_db) &
    (df_master['PO Number'].astype(str) == selected_po)
]
selected_po_pic = filtered_df['User Created PO'].iloc[0] if not filtered_df.empty else "-"
po_vendor = filtered_df['Vendor'].iloc[0] if not filtered_df.empty else "-"
st.markdown(f"**📌 PIC PO (From Source):** {selected_po_pic}")
st.markdown(f"**🏢 Vendor:** {po_vendor}")

# --- Get Vessel Options ---
vessel_options = sorted(filtered_df['Cost Center Nama Kapal'].dropna().unique())

# --- Item, Quantity, and Vessel Input ---
raw_item_list = filtered_df['Item Name Complete'].dropna().tolist()
item_counter = Counter()
item_options = []
item_map = {}  # unique label → real item name

for item in raw_item_list:
    item_counter[item] += 1
    if item_counter[item] > 1:
        label = f"{item} #{item_counter[item]}"
    else:
        label = item
    item_options.append(label)
    item_map[label] = item

selected_labels = st.multiselect("Select items received:", item_options)

entry_data = {}
for label in selected_labels:
    real_item = item_map[label]
    st.markdown(f"### Entry for: `{real_item}`")

    item_row = filtered_df[filtered_df['Item Name Complete'] == real_item]
    if not item_row.empty:
        max_qty = int(item_row['Quantity PO'].iloc[0])
    else:
        max_qty = None

    col1, col2 = st.columns(2)
    with col1:
        if max_qty is not None:
            qty = st.number_input(
                f"Quantity for `{label}`",
                min_value=1,
                max_value=max_qty,
                step=1,
                key=f"qty_{label}"
            )
        else:
            st.warning(f"⚠️ Max quantity for `{real_item}` not found in PO data.")
            qty = st.number_input(
                f"Quantity for `{label}`",
                min_value=1,
                step=1,
                key=f"qty_{label}"
            )
    with col2:
        vessel = st.selectbox(f"Vessel for `{label}`", vessel_options, key=f"vessel_{label}")

    entry_data[label] = {
        "real_item": real_item,
        "quantity": qty,
        "vessel": vessel
    }

# --- Photo Upload ---
uploaded_files = st.file_uploader("Upload photos (unlimited):", accept_multiple_files=True, type=["jpg", "jpeg", "png"])

# --- Submission ---
if st.button("Submit"):
    if not selected_labels or all(values["quantity"] == 0 for values in entry_data.values()):
        st.error("Please select items and enter a non-zero quantity for at least one.")
    else:
        timestamp = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%Y-%m-%d_%H-%M-%S")
        folder_name = f"{selected_db}_{selected_po}_{timestamp}"

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
                try:
                    json_resp = photo_response.json()
                    drive_folder_url = json_resp.get("folderUrl", "UPLOAD_FAILED")
                    st.success("✅ Photos uploaded successfully.")
                    st.markdown(f"[📂 View uploaded folder]({drive_folder_url})")
                    photo_success = True
                except Exception as e:
                    st.error(f"❌ Failed to parse photo upload response JSON: {e}")
            else:
                st.error(f"❌ Photo upload failed: {photo_response.status_code} - {photo_response.text}")
        except Exception as e:
            st.error(f"❌ Photo upload error: {e}")

        # Step 2: Send Metadata
        entries = []
        for label, values in entry_data.items():
            if values["quantity"] > 0:
                entries.append({
                    "timestamp": timestamp,
                    "database": selected_db,
                    "po_number": selected_po,
                    "pic": selected_pic,
                    "po_pic": selected_po_pic,
                    "vendor": po_vendor,
                    "item": values["real_item"],
                    "quantity": values["quantity"],
                    "vessel": values["vessel"]
                })

        data_payload = {
            "timestamp": timestamp,
            "database": selected_db,
            "po_number": selected_po,
            "pic": selected_pic,
            "po_pic": selected_po_pic,
            "vendor": po_vendor,
            "drive_folder_link": drive_folder_url,
            "items": entries
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

        if photo_success and data_success:
            st.success("🎉 Submission completed successfully!")
        elif not photo_success and not data_success:
            st.error("🚨 Submission failed for both photo upload and data logging.")
        elif not photo_success:
            st.warning("⚠️ Data saved, but photo upload failed.")
        elif not data_success:
            st.warning("⚠️ Photos uploaded, but data logging failed.")
