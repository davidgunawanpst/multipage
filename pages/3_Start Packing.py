import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from io import StringIO
from auth import check_password  # keep your auth

# --- Streamlit page setup ---
st.set_page_config(page_title="Packing Start", layout="wide")

# --- Google Sheet details ---
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
SHEET_NAME = "List All Packing"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

# --- Your webhook URL ---
WEBHOOK_URL_DATA = "https://script.google.com/macros/s/AKfycbwFSn6IwvFz_mIonmY5eIZqLK73QYytJHCad4tkua92QZcQbQEOCOpEeBBSeUTR-Wmqnw/exec"

# --- Static lists ---
pic_list = [
    "Rikie Dwi Permana",
    "Idha Akhmad Sucahyo",
    "Rian Dinata",
    "Harimurti Krisandki",
    "Muchamad Mustofa",
    "Yogie Arie Wibowo",
]
db_list = ["DMI", "PBN", "PKS", "PMT", "PSS", "PSM", "PST"]

# --- Functions ---
def load_sheet_csv(url: str) -> pd.DataFrame:
    """Load the Google Sheet (published CSV) into a pandas DataFrame."""
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))

def get_available_picks(df: pd.DataFrame, selected_db: str) -> list[str]:
    """Return Pick List numbers for the selected DB where Start Packing is blank."""
    df.columns = df.columns.str.strip()

    if not {"Database", "Pick List NO.", "Start Packing"}.issubset(df.columns):
        raise ValueError("Sheet missing required columns: Database, Pick List NO., Start Packing")

    filtered = df[
        (df["Database"].astype(str).str.strip() == selected_db)
        & (df["Start Packing"].isna() | (df["Start Packing"].astype(str).str.strip() == ""))
    ]

    # --- Convert numbers like 11111.0 → '11111' ---
    picks = (
        filtered["Pick List NO."]
        .dropna()
        .apply(lambda x: str(int(x)) if isinstance(x, (float, int)) and x == int(x) else str(x))
        .str.strip()
        .unique()
        .tolist()
    )
    return sorted(picks)

# --- Main app ---
if check_password():
    st.title("📦 Packing Start — Pick List")

    selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
    selected_db = st.selectbox("Database:", db_list)

    # Load the sheet and populate pick list dropdown dynamically
    try:
        with st.spinner("Loading pick list data..."):
            df = load_sheet_csv(CSV_URL)
            available_picks = get_available_picks(df, selected_db)
    except Exception as e:
        st.error(f"❌ Failed to load Google Sheet: {e}")
        available_picks = []

    if not available_picks:
        st.warning("No available Pick Lists found for this database.")
        pick_number = st.selectbox("Pick List Number:", ["— none available —"])
    else:
        pick_number = st.selectbox("Pick List Number:", available_picks)

    # Submit button
    if st.button("✅ Submit"):
        if not available_picks or pick_number == "— none available —":
            st.warning("Please select a valid Pick List number.")
        else:
            # ✅ Format date as DD/MM/YYYY (Jakarta time)
            input_date_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")

            # --- Payload ---
            data_payload = {
                "input_date": input_date_str,  # use formatted date
                "pic": selected_pic,
                "database": selected_db,
                "pl_released": pick_number,
            }

            try:
                with st.spinner("Sending data..."):
                    resp = requests.post(WEBHOOK_URL_DATA, json=data_payload, timeout=20)
                if resp.status_code in (200, 201):
                    st.success("🎉 Submission completed successfully!")
                    st.json(data_payload)
                else:
                    st.error(f"❌ Failed to send: {resp.status_code} - {resp.text}")
            except Exception as e:
                st.error(f"❌ Network/error sending data: {e}")
