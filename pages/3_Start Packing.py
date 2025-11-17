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

def extract_from_unique_code(unique_code_value: str) -> str | None:
    """
    Given a Unique Code like 'DMI|DMI-Manual-1' or 'DMI|3005', return the
    likely pick identifier (last non-empty segment). Returns None if nothing found.
    """
    if unique_code_value is None:
        return None
    s = str(unique_code_value).strip()
    if s == "":
        return None
    # split on '|' (or other separators if you want) and take last non-empty piece
    parts = [p.strip() for p in s.split("|") if p and p.strip() != ""]
    if not parts:
        return None
    return parts[-1]

def get_available_picks(df: pd.DataFrame, selected_db: str) -> list[str]:
    """
    Return Pick List numbers for the selected DB where Start Packing is blank.
    If 'Pick List NO.' is empty, try extracting an ID from 'Unique Code'.
    Preserves text IDs (e.g. 'DMI-Manual-1') and cleans floats like 3008.0 → '3008'.
    """
    df = df.copy()
    df.columns = df.columns.str.strip()

    required = {"Database", "Pick List NO.", "Start Packing"}
    if not required.issubset(df.columns):
        raise ValueError(f"Sheet missing required columns: {', '.join(required)}")

    df["Database"] = df["Database"].astype(str).str.strip()

    start_as_str = df["Start Packing"].fillna("").astype(str).str.strip().replace({"nan": "", "None": "", "NaN": ""})
    df["_StartPackingClean"] = start_as_str

    filtered = df[(df["Database"] == selected_db) & (df["_StartPackingClean"] == "")].copy()

    picks = []
    for _, row in filtered.iterrows():
        raw_pl = row.get("Pick List NO.", None)
        pl_str = ""

        # handle direct value
        if pd.notna(raw_pl):
            if isinstance(raw_pl, (float, int)) and raw_pl == int(raw_pl):
                pl_str = str(int(raw_pl))  # clean numeric like 3008.0 → 3008
            else:
                pl_str = str(raw_pl).strip()

        if pl_str.lower() in {"", "nan", "none"}:
            pl_str = ""

        if pl_str != "":
            candidate = pl_str
        else:
            # fallback to Unique Code
            unique_code_val = row.get("Unique Code", None)
            candidate = extract_from_unique_code(unique_code_val)

        if candidate and str(candidate).strip() != "":
            picks.append(str(candidate).strip())

    # unique order preserving
    seen, final = set(), []
    for p in picks:
        if p not in seen:
            seen.add(p)
            final.append(p)

    # sort digits numerically, then non-digits
    digits = [x for x in final if x.isdigit()]
    nondigits = [x for x in final if not x.isdigit()]
    digits_sorted = sorted(digits, key=lambda s: int(s))
    return digits_sorted + nondigits

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
        df = pd.DataFrame()
        available_picks = []

    # --- DEBUG: show exactly what was loaded and what rows matched the filter
    with st.expander("🔎 Debug: raw sheet preview & matched rows (leave open while testing)"):
        try:
            st.subheader("Raw sheet head (first 50 rows)")
            st.dataframe(df.head(50))

            st.subheader("Column dtypes")
            st.write(df.dtypes.astype(str))

            st.subheader(f"All rows with Database == '{selected_db}' (before Start Packing check)")
            db_rows = df[df["Database"].astype(str).str.strip() == selected_db]
            st.write(f"Count: {len(db_rows)}")
            st.dataframe(db_rows.head(200))

            st.subheader("Rows where Start Packing considered BLANK (should be included)")
            start_raw = df["Actual Start Packing"]
            start_as_str = start_raw.fillna("").astype(str).str.strip().replace({"nan": "", "None": "", "NaN": ""})
            df["_StartPackingClean"] = start_as_str
            matched = df[(df["Database"].astype(str).str.strip() == selected_db) & (df["_StartPackingClean"] == "")]
            st.write(f"Matched count: {len(matched)}")
            st.dataframe(matched.head(500))

            st.subheader("Distinct Pick IDs derived from matched rows (Pick List NO. preferred, Unique Code fallback)")
            derived = []
            for idx, row in matched.iterrows():
                raw_pl = row.get("Pick List NO.", None)
                pl_str = ""
                if pd.notna(raw_pl):
                    pl_str = str(raw_pl).strip()
                if pl_str.lower() in {"", "nan", "none", "nan.0"}:
                    pl_str = ""
                if pl_str != "":
                    derived.append(pl_str)
                else:
                    unique_code_val = row.get("Unique Code", None) if "Unique Code" in row.index else None
                    cand = extract_from_unique_code(unique_code_val)
                    if cand:
                        derived.append(cand)
            st.write(pd.Series(derived).dropna().unique().tolist())
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
