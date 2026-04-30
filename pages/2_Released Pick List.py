import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from io import StringIO
from auth import check_password  # your auth module
import base64

# --- PAGE CONFIG ---
st.set_page_config(page_title="Released Pick List", layout="wide")

# --- WEBHOOK URL ---
WEBHOOK_URL_DATA = st.secrets["WEBHOOK_URL"]

# --- GOOGLE SHEETS ---
VESSEL_SHEET_ID = st.secrets["VESSEL_SHEET_ID"]
VESSEL_SHEET_NAME = "Vessel Name"
VESSEL_CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{VESSEL_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={VESSEL_SHEET_NAME}"
)

MANUAL_PICKLIST_SHEET_NAME = "Manual Pick List"
MANUAL_PICKLIST_CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{VESSEL_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={MANUAL_PICKLIST_SHEET_NAME}"
)

# --- STATIC LISTS ---
pic_list = [
    "Abim Priambada",
    "Maftuh Ikhsan",
    "Dadi Mulyanto",
    "Rudi Haryanto",
]
db_list = ["DMI", "PBN", "PKS", "PMT", "PSS", "PSM", "PST"]

# --- SHARED HTTP SESSION ---
@st.cache_resource
def get_http_session() -> requests.Session:
    return requests.Session()

# --- HELPERS ---
@st.cache_data(ttl=600)
def load_csv(url: str) -> pd.DataFrame:
    """Generic CSV loader with safe fallback."""
    try:
        session = get_http_session()
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Failed to load sheet: {e}")
        return pd.DataFrame()

def valid_number(value: str) -> bool:
    if not value:
        return False
    return value.strip().isdigit()

def add_working_days(start: date, add_days: int) -> date:
    if add_days <= 0:
        return start
    current = start
    days_added = 0
    while days_added < add_days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days_added += 1
    return current

# --- APP ---
if check_password():
    st.title("Released Pick List")

    selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
    selected_db = st.selectbox("Database:", db_list)
    release_type = st.radio("Release Type:", ["Normal", "Manual"])
    urgent = st.radio("Urgent?", ["Normal", "Urgent"])

    # --- Load Vessel Data ---
    df_vessel = load_csv(VESSEL_CSV_URL)
    vessels_for_db = (
        df_vessel[df_vessel["DB"].astype(str).str.strip() == selected_db]
        if not df_vessel.empty
        else pd.DataFrame()
    )
    vessel_options = (
        sorted(vessels_for_db["Vessel Name"].dropna().astype(str).unique().tolist())
        if "Vessel Name" in vessels_for_db.columns
        else []
    )

    if not vessel_options:
        vessel_name = st.text_input("Vessel Name (no entry in sheet, type manually):")
    else:
        vessel_name = st.selectbox("Vessel Name:", vessel_options)

    # --- Requirement date logic ---
    now_jkt = datetime.now(ZoneInfo("Asia/Jakarta"))
    today_jkt = now_jkt.date()

    if urgent == "Urgent":
        requirement_date = today_jkt
    else:
        start_day = today_jkt + timedelta(days=1) if now_jkt.hour >= 16 else today_jkt
        requirement_date = add_working_days(start_day, 3)

    st.info(f"Requirement Date (computed): **{requirement_date.strftime('%d/%m/%Y')}**")

    # --- Normal Flow ---
    if release_type == "Normal":
        pick_number = st.text_input("Nomor PL (numbers only):", placeholder="e.g. 12345")

    # --- Manual Flow ---
    else:
        st.info("Manual mode active. Pick List number will be generated automatically.")
        df_manual = load_csv(MANUAL_PICKLIST_CSV_URL)
        next_number = 1
        if not df_manual.empty and "Nomor" in df_manual.columns:
            try:
                existing_numbers = pd.to_numeric(df_manual["Nomor"], errors="coerce").dropna()
                if not existing_numbers.empty:
                    next_number = int(existing_numbers.max()) + 1
            except Exception:
                pass

        kode_picklist_manual = f"{selected_db}-Manual-{next_number}"
        st.write(f"🧾 **Generated Pick List Code:** {kode_picklist_manual}")
        remarks = st.text_input("Remarks (e.g. Vendor - Barang):")

    # --- PDF Upload ---
    uploaded_pdf = st.file_uploader(
        "Attach Picklist PDF (required)",
        type=["pdf"],
        accept_multiple_files=False
    )

    pdf_base64 = None
    if uploaded_pdf is not None:
        pdf_bytes = uploaded_pdf.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
        st.success("📄 PDF attached ✔️")

    # --- Submit Button ---
    if st.button("✅ Submit"):
        input_date_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")
        req_date_str = requirement_date.strftime("%d/%m/%Y")

        if not uploaded_pdf:
            st.warning("Please upload a PDF file.")
        elif not vessel_name or not vessel_name.strip():
            st.warning("Please select or enter a Vessel Name.")
        elif release_type == "Normal" and not valid_number(pick_number):
            st.warning("Nomor PL must contain digits only.")
        elif release_type == "Manual" and not remarks.strip():
            st.warning("Please fill in Remarks (Vendor - Barang).")
        else:
            filename = (
                f"PL-{selected_db}-{pick_number.strip()}.pdf"
                if release_type == "Normal"
                else f"PL-{selected_db}-{next_number}.pdf"
            )

            if release_type == "Normal":
                data_payload = {
                    "release_type": "Normal",
                    "database": selected_db,
                    "nomor_pl": pick_number.strip(),
                    "vessel_name": vessel_name.strip(),
                    "pic": selected_pic,
                    "input_date": input_date_str,
                    "requirement_date": req_date_str,
                    "urgent_status": urgent,
                    "pdf": pdf_base64,
                    "filename": filename,
                }
            else:
                data_payload = {
                    "release_type": "Manual",
                    "database": selected_db,
                    "pic": selected_pic,
                    "nomor": next_number,
                    "kode_picklist_manual": kode_picklist_manual,
                    "vessel_name": vessel_name.strip(),
                    "remarks": remarks.strip(),
                    "input_date": input_date_str,
                    "requirement_date": req_date_str,
                    "urgent_status": urgent,
                    "pdf": pdf_base64,
                    "filename": filename,
                }

            try:
                with st.spinner("Sending data to server..."):
                    session = get_http_session()
                    resp = session.post(
                        WEBHOOK_URL_DATA,
                        json=data_payload,
                        timeout=40
                    )

                if resp.status_code in (200, 201):
                    st.success("🎉 Submission completed successfully!")
                    st.json(data_payload)
                else:
                    st.error(f"❌ Data logging failed: {resp.status_code} - {resp.text}")

            except Exception as e:
                st.error(f"❌ Network/error sending data: {e}")
