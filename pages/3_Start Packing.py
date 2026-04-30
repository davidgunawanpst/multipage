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
SHEET_ID = st.secrets["PACKING_SHEET_ID"]
SHEET_NAME = "List All Packing"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

# --- Your webhook URL ---
WEBHOOK_URL_DATA = st.secrets["PACKING_WEBHOOK"]

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

# --- SHARED HTTP SESSION ---
@st.cache_resource
def get_http_session() -> requests.Session:
    return requests.Session()

# --- Functions ---
def load_sheet_csv(url: str) -> pd.DataFrame:
    """Load the Google Sheet (published CSV) into a pandas DataFrame."""
    session = get_http_session()
    resp = session.get(url, timeout=20)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))

def extract_from_unique_code(unique_code_value: str) -> str | None:
    if unique_code_value is None:
        return None
    s = str(unique_code_value).strip()
    if s == "":
        return None
    parts = [p.strip() for p in s.split("|") if p and p.strip() != ""]
    if not parts:
        return None
    return parts[-1]

def get_available_picks(df: pd.DataFrame, selected_db: str) -> list[str]:
    df = df.copy()
    df.columns = df.columns.str.strip()

    required = {"Database", "Pick List NO.", "Actual Start Packing"}
    if not required.issubset(df.columns):
        raise ValueError(f"Sheet missing required columns: {', '.join(required)}")

    df["Database"] = df["Database"].astype(str).str.strip()

    start_as_str = (
        df["Actual Start Packing"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace({"nan": "", "None": "", "NaN": ""})
    )
    df["_StartPackingClean"] = start_as_str

    filtered = df[
        (df["Database"] == selected_db)
        & (df["_StartPackingClean"] == "")
    ].copy()

    picks = []
    for _, row in filtered.iterrows():
        raw_pl = row.get("Pick List NO.", None)
        pl_str = ""

        if pd.notna(raw_pl):
            if isinstance(raw_pl, (float, int)) and raw_pl == int(raw_pl):
                pl_str = str(int(raw_pl))
            else:
                pl_str = str(raw_pl).strip()

        if pl_str.lower() in {"", "nan", "none"}:
            pl_str = ""

        if pl_str:
            candidate = pl_str
        else:
            unique_code_val = row.get("Unique Code", None)
            candidate = extract_from_unique_code(unique_code_val)

        if candidate:
            picks.append(str(candidate).strip())

    seen, final = set(), []
    for p in picks:
        if p not in seen:
            seen.add(p)
            final.append(p)

    digits = [x for x in final if x.isdigit()]
    nondigits = [x for x in final if not x.isdigit()]
    return sorted(digits, key=lambda s: int(s)) + nondigits

# --- Main app ---
if check_password():
    st.title("📦 Packing Start — Pick List")

    selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
    selected_db = st.selectbox("Database:", db_list)

    try:
        with st.spinner("Loading pick list data..."):
            df = load_sheet_csv(CSV_URL)
            available_picks = get_available_picks(df, selected_db)
    except Exception as e:
        st.error(f"❌ Failed to load Google Sheet: {e}")
        df = pd.DataFrame()
        available_picks = []

    with st.expander("🔎 Debug: raw sheet preview & matched rows (leave open while testing)"):
        try:
            st.subheader("Raw sheet head (first 50 rows)")
            st.dataframe(df.head(50))

            st.subheader("Column dtypes")
            st.write(df.dtypes.astype(str))

            st.subheader(f"All rows with Database == '{selected_db}'")
            db_rows = df[df["Database"].astype(str).str.strip() == selected_db]
            st.write(f"Count: {len(db_rows)}")
            st.dataframe(db_rows.head(200))
        except Exception as debug_e:
            st.write("Debug error:", debug_e)

    if not available_picks:
        st.warning("No available Pick Lists found for this database.")
        pick_number = st.selectbox("Pick List Number:", ["— none available —"])
    else:
        pick_number = st.selectbox("Pick List Number:", available_picks)

    if st.button("✅ Submit"):
        if not available_picks or pick_number == "— none available —":
            st.warning("Please select a valid Pick List number.")
        else:
            input_date_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d/%m/%Y")

            data_payload = {
                "input_date": input_date_str,
                "pic": selected_pic,
                "database": selected_db,
                "pl_released": pick_number,
            }

            try:
                with st.spinner("Sending data..."):
                    session = get_http_session()
                    resp = session.post(
                        WEBHOOK_URL_DATA,
                        json=data_payload,
                        timeout=20
                    )

                if resp.status_code in (200, 201):
                    st.success("🎉 Submission completed successfully!")
                    st.json(data_payload)
                else:
                    st.error(f"❌ Failed to send: {resp.status_code} - {resp.text}")

            except Exception as e:
                st.error(f"❌ Network/error sending data: {e}")
