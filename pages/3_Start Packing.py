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
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))

def get_available_picks(df: pd.DataFrame, selected_db: str) -> list[str]:
    """
    Return Pick List numbers for the selected DB where Start Packing is blank.
    This version forces everything to string *after* filtering and removes
    empty-like tokens so textual IDs (e.g. 'DMI-Manual-1') are preserved.
    """
    df = df.copy()
    df.columns = df.columns.str.strip()

    required = {"Database", "Pick List NO.", "Start Packing"}
    if not required.issubset(df.columns):
        raise ValueError(f"Sheet missing required columns: {', '.join(required)}")

    # Normalize Database for matching
    df["Database"] = df["Database"].astype(str).str.strip()

    # Prepare a StartPacking cleaned column:
    # Keep NaN as NaN, but also treat 'nan', 'None', and empty strings as blank
    start_raw = df["Start Packing"]
    # Convert real NaN to empty string marker, then strip any whitespace
    start_as_str = start_raw.fillna("").astype(str).str.strip()
    # Normalize tokens that represent emptiness
    start_as_str = start_as_str.replace({"nan": "", "None": "", "NaN": ""})
    df["_StartPackingClean"] = start_as_str

    # Filter rows where Database matches and Start Packing is blank (empty string after cleaning)
    filtered = df[(df["Database"] == selected_db) & (df["_StartPackingClean"] == "")].copy()

    # FORCE pick list values to strings (this preserves textual values like 'DMI-Manual-1')
    picks_series = filtered["Pick List NO."].fillna("").astype(str).str.strip()

    # Remove empty-like tokens that may have been introduced by astype(str)
    picks_series = picks_series.replace({"": None, "nan": None, "None": None, "NaN": None})

    picks = picks_series.dropna().unique().tolist()

    # Sorting: preserve numeric order for purely-digit strings, otherwise lexicographic
    def sort_key(x):
        if x.isdigit():
            return (0, int(x))
        return (1, x.lower())

    return sorted(picks, key=sort_key)

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
        df = pd.DataFrame()  # fallback so debug block doesn't crash
        available_picks = []

    # --- DEBUG: show exactly what was loaded and what rows matched the filter
    # Keep this visible while debugging. Remove or comment out when done.
    with st.expander("🔎 Debug: raw sheet preview & matched rows (leave open while testing)"):
        try:
            st.subheader("Raw sheet head (first 50 rows)")
            st.dataframe(df.head(50))

            st.subheader("Column dtypes")
            st.write(df.dtypes.astype(str))

            # Show all rows where Database matches the selected DB (before our Start Packing filter)
            st.subheader(f"All rows with Database == '{selected_db}' (before Start Packing check)")
            db_rows = df[df["Database"].astype(str).str.strip() == selected_db]
            st.write(f"Count: {len(db_rows)}")
            st.dataframe(db_rows.head(200))

            # Show rows that survived our Start Packing blank check
            st.subheader("Rows where Start Packing considered BLANK (should be included)")
            start_raw = df["Start Packing"]
            start_as_str = start_raw.fillna("").astype(str).str.strip().replace({"nan": "", "None": "", "NaN": ""})
            df["_StartPackingClean"] = start_as_str
            matched = df[(df["Database"].astype(str).str.strip() == selected_db) & (df["_StartPackingClean"] == "")]
            st.write(f"Matched count: {len(matched)}")
            st.dataframe(matched.head(500))

            # Show distinct Pick List NO. values found among matched rows
            st.subheader("Distinct Pick List NO. values among matched rows")
            distinct = (
                matched["Pick List NO."].fillna("").astype(str).str.strip().replace({"": None, "nan": None, "None": None})
            )
            st.write(distinct.dropna().unique().tolist())
        except Exception as debug_e:
            st.write("Debug error:", debug_e)

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
