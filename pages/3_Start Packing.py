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
    """
    Return Pick List numbers for the selected DB where Start Packing is blank.
    Robust for mixed-type columns (preserves text like 'DMI-Manual-1').
    """
    # Work on a copy to avoid side-effects
    df = df.copy()

    # Normalize column names
    df.columns = df.columns.str.strip()

    required = {"Database", "Pick List NO.", "Start Packing"}
    if not required.issubset(df.columns):
        raise ValueError(f"Sheet missing required columns: {', '.join(required)}")

    # Normalize Database column for safe comparison
    df["Database"] = df["Database"].astype(str).str.strip()

    # Handle Start Packing: keep NaN as NaN, but prepare string comparisons safely
    # First, don't coerce to string permanently because that turns NaN into 'nan' strings
    # We'll create a helper column for stripped Start Packing for comparisons
    start_packing_raw = df["Start Packing"]
    # Create a cleaned column where empty-like values become empty string
    start_packing_clean = start_packing_raw.where(start_packing_raw.notna(), None)
    start_packing_clean = start_packing_clean.astype(str).str.strip().replace({"None": ""})
    df["_StartPackingClean"] = start_packing_clean

    # Filter rows where Database matches and Start Packing is blank
    filtered = df[
        (df["Database"] == selected_db)
        & ((df["_StartPackingClean"].isna()) | (df["_StartPackingClean"].astype(str).str.strip() == ""))
    ].copy()

    # Convert Pick List NO. robustly to string while preserving text values
    picks_series = (
        filtered["Pick List NO."]
        .fillna("")           # replace NaN with empty string temporarily
        .astype(str)          # force all types to str
        .str.strip()          # trim whitespace
        .replace({"": None})  # empty -> None so we can drop them
    )

    picks = picks_series.dropna().unique().tolist()

    # Sort: numeric-only strings sort by numeric value first, then non-numeric lexicographically
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
        available_picks = []

    # --- Optional debug expander: uncomment to inspect filtered rows live ---
    # Helpful when you want to verify why certain pick lists are/are not included.
    # -------------------------------------------------------------------------
    # with st.expander("🔎 Debug: show filtered rows for selected DB"):
    #     try:
    #         df_tmp = df.copy()
    #         df_tmp.columns = df_tmp.columns.str.strip()
    #         df_tmp["_StartPackingClean"] = df_tmp["Start Packing"].where(df_tmp["Start Packing"].notna(), None)
    #         df_tmp["_StartPackingClean"] = df_tmp["_StartPackingClean"].astype(str).str.strip().replace({"None": ""})
    #         debug_filtered = df_tmp[
    #             (df_tmp["Database"].astype(str).str.strip() == selected_db)
    #             & ((df_tmp["_StartPackingClean"].isna()) | (df_tmp["_StartPackingClean"].astype(str).str.strip() == ""))
    #         ]
    #         st.write(f"Filtered row count: {len(debug_filtered)}")
    #         st.dataframe(debug_filtered.head(500))
    #     except Exception as ee:
    #         st.write("Debug load error:", ee)
    # -------------------------------------------------------------------------

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
