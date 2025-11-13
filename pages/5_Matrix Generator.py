import streamlit as st
import pandas as pd
from urllib.parse import quote_plus

# ----------------------
# Configuration
# ----------------------
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
WORKSHEET_NAME = "List%20Finish%20Packing"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={WORKSHEET_NAME}"

ADMIN_PICS = [
    "Abim Priambada",
    "Maftuh Ikhsan",
    "Rifka Fahrul Musthofa",
    "Rudi Haryanto",
]

DB_LIST = ["DMI", "PBN", "PKS", "PMT", "PSM", "PSS", "PST"]

MODA_OPTIONS = [
    "Sea Freight",
    "Air Freight",
    "Land Freight",
    "Handcarry",
]

# ----------------------
# Helpers
# ----------------------
@st.cache_data(ttl=300)
def load_data(csv_url: str) -> pd.DataFrame:
    df = pd.read_csv(csv_url)
    return df

def fmt_picklist_value(v):
    """
    Format Pick List value to remove trailing .0 when it represents an integer,
    while preserving non-numeric strings exactly.
    """
    # handle NaN
    if pd.isna(v):
        return ""
    # If already numeric (float/int), convert accordingly
    if isinstance(v, (int,)):
        return str(v)
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        else:
            # keep float representation but trim unnecessary trailing zeros
            return str(v).rstrip('0').rstrip('.') if '.' in str(v) else str(v)
    # if string, try to interpret as a float like "123.0" -> "123"
    s = str(v).strip()
    # typical case from CSV: numbers may be read as strings "123.0"
    try:
        fv = float(s)
        if fv.is_integer():
            return str(int(fv))
        else:
            return str(fv).rstrip('0').rstrip('.') if '.' in str(fv) else str(fv)
    except Exception:
        # not a float -> return original string
        return s

# ----------------------
# App
# ----------------------
st.set_page_config(page_title="Finish Packing — Shipping Input", layout="wide")
st.title("Finish Packing — Shipping Input")

with st.spinner("Loading Google Sheet..."):
    df = load_data(CSV_URL)

if df.empty:
    st.error("Failed to load data — check if the sheet is public and has visible headers.")
    st.stop()

expected_cols = ["DB", "Pick List", "Timestamp", "PIC", "Urgency", "Vessel"]
for col in expected_cols:
    if col not in df.columns:
        st.warning(f"Column '{col}' missing in sheet!")

# Clean / format Pick List column so UI shows no trailing .0
if "Pick List" in df.columns:
    df["Pick List"] = df["Pick List"].apply(fmt_picklist_value)

# --- UI ---
st.sidebar.header("Operator")
selected_pic = st.sidebar.selectbox("Select Admin PIC", ADMIN_PICS)

st.header("Filters & Inputs")

col1, col2 = st.columns(2)

with col1:
    selected_db = st.selectbox("DB", ["-- Select DB --"] + DB_LIST)

    vessel_options = []
    if selected_db and selected_db != "-- Select DB --" and "DB" in df.columns:
        vessel_options = sorted(df.loc[df["DB"] == selected_db, "Vessel"].dropna().unique().tolist())

    selected_vessel = st.selectbox("Vessel", ["-- Select Vessel --"] + vessel_options)

with col2:
    picklist_options = []
    if selected_vessel and selected_vessel != "-- Select Vessel --" and "Vessel" in df.columns:
        cond = df["Vessel"] == selected_vessel
        if selected_db and selected_db != "-- Select DB --" and "DB" in df.columns:
            cond &= (df["DB"] == selected_db)
        if "Pick List" in df.columns:
            # unique, non-empty
            picklist_options = sorted([p for p in df.loc[cond, "Pick List"].dropna().unique().tolist() if str(p).strip() != ""])

    # allow multiple pick lists selection
    selected_picklists = st.multiselect("Pick List (select one or more)", options=picklist_options)

    tujuan = st.text_input("Tujuan (Destination)")
    moda = st.selectbox("Moda Pengiriman", ["-- Select Moda --"] + MODA_OPTIONS)

st.divider()
st.subheader("Selection Summary")
st.write({
    "Admin PIC": selected_pic,
    "DB": selected_db,
    "Vessel": selected_vessel,
    "Pick List(s)": selected_picklists,
    "Tujuan": tujuan,
    "Moda Pengiriman": moda,
})

if st.button("Proceed / Save (placeholder)"):
    st.success("Selections captured. (No write-back yet)")

with st.expander("Preview Loaded Data"):
    st.dataframe(df.head(30))
