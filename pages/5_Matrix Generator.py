import streamlit as st
import pandas as pd

# ----------------------
# Configuration
# ----------------------
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
WORKSHEET_NAME = "List Finish Packing"
RANGE = "J:O"  # ignored in this method, since we'll import full sheet

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
# App
# ----------------------
st.set_page_config(page_title="Finish Packing — Shipping Input", layout="wide")
st.title("Finish Packing — Shipping Input")

# Load data
@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv(CSV_URL)
    return df

with st.spinner("Loading Google Sheet..."):
    df = load_data()

if df.empty:
    st.error("Failed to load data — check if the sheet is public and has visible headers.")
    st.stop()

expected_cols = ["DB", "Pick List", "Timestamp", "PIC", "Urgency", "Vessel"]
for col in expected_cols:
    if col not in df.columns:
        st.warning(f"Column '{col}' missing in sheet!")

# --- UI ---
st.sidebar.header("Operator")
selected_pic = st.sidebar.selectbox("Select Admin PIC", ADMIN_PICS)

st.header("Filters & Inputs")

col1, col2 = st.columns(2)

with col1:
    selected_db = st.selectbox("DB", ["-- Select DB --"] + DB_LIST)

    vessel_options = []
    if selected_db and selected_db != "-- Select DB --":
        vessel_options = sorted(df.loc[df["DB"] == selected_db, "Vessel"].dropna().unique().tolist())

    selected_vessel = st.selectbox("Vessel", ["-- Select Vessel --"] + vessel_options)

with col2:
    picklist_options = []
    if selected_vessel and selected_vessel != "-- Select Vessel --":
        cond = (df["Vessel"] == selected_vessel)
        if selected_db and selected_db != "-- Select DB --":
            cond &= (df["DB"] == selected_db)
        picklist_options = sorted(df.loc[cond, "Pick List"].dropna().unique().tolist())

    selected_picklist = st.selectbox("Pick List", ["-- Select Pick List --"] + picklist_options)
    tujuan = st.text_input("Tujuan (Destination)")
    moda = st.selectbox("Moda Pengiriman", ["-- Select Moda --"] + MODA_OPTIONS)

st.divider()
st.subheader("Selection Summary")
st.write({
    "Admin PIC": selected_pic,
    "DB": selected_db,
    "Vessel": selected_vessel,
    "Pick List": selected_picklist,
    "Tujuan": tujuan,
    "Moda Pengiriman": moda,
})

if st.button("Proceed / Save (placeholder)"):
    st.success("Selections captured. (No write-back yet)")

with st.expander("Preview Loaded Data"):
    st.dataframe(df.head(30))
