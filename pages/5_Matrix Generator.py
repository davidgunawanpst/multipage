import streamlit as st
import pandas as pd
import requests
from io import StringIO
from urllib.parse import quote_plus

# ----------------------
# Configuration
# ----------------------
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
WORKSHEET_NAME = "List Finish Packing"  # tab name (not encoded here)
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote_plus(WORKSHEET_NAME)}"

# fixed lists
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

# expected columns in the J:O block
EXPECTED_COLS = ["DB", "Pick List", "Timestamp", "PIC", "Urgency", "Vessel"]

# ----------------------
# Helpers
# ----------------------
@st.cache_data(ttl=300)
def load_sheet_csv(url: str) -> pd.DataFrame:
    """Load the Google Sheet (published CSV) into a pandas DataFrame."""
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    # read entire sheet CSV then we'll subset to needed columns if present
    df_all = pd.read_csv(StringIO(resp.text), dtype=object)
    return df_all

def fmt_picklist_value(raw_pl) -> str | None:
    """
    Convert a raw Pick List value to a clean string:
      - numeric floats that are integer-like (3008.0) => '3008'
      - integers => '123'
      - strings like '3008.0' => '3008'
      - preserve non-numeric strings (e.g. 'DMI-Manual-1')
    Return None if value is empty/NaN.
    """
    if pd.isna(raw_pl):
        return None
    # numeric types
    if isinstance(raw_pl, int):
        return str(raw_pl)
    if isinstance(raw_pl, float):
        if raw_pl.is_integer():
            return str(int(raw_pl))
        s = repr(raw_pl)
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s
    s_val = str(raw_pl).strip()
    if s_val.lower() in {"", "nan", "none"}:
        return None
    # try parse floats in strings like "3008.0"
    try:
        fv = float(s_val)
        if fv.is_integer():
            return str(int(fv))
        s = str(fv)
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s
    except Exception:
        return s_val

def get_vessels_for_db(df: pd.DataFrame, selected_db: str) -> list[str]:
    """Return sorted unique Vessel values for a DB (preserve strings)."""
    if "DB" not in df.columns or "Vessel" not in df.columns:
        return []
    subset = df[df["DB"].astype(str).str.strip() == selected_db]
    vessels = subset["Vessel"].dropna().astype(str).str.strip().unique().tolist()
    # remove empty strings
    vessels = [v for v in vessels if v != ""]
    return sorted(vessels)

def get_picklists_for_vessel(df: pd.DataFrame, selected_db: str, selected_vessel: str) -> list[str]:
    """
    Return pick list identifiers (cleaned) for rows matching DB & Vessel.
    Includes numeric and string pick lists, preserves order and uniqueness.
    """
    if not {"DB", "Vessel", "Pick List"}.issubset(df.columns):
        return []

    cond = (df["DB"].astype(str).str.strip() == selected_db) & (df["Vessel"].astype(str).str.strip() == selected_vessel)
    rows = df.loc[cond, :]

    picks_raw = []
    for _, r in rows.iterrows():
        raw_pl = r.get("Pick List", None)
        clean = fmt_picklist_value(raw_pl)
        if clean:
            picks_raw.append(clean)
        else:
            # if Pick List empty but there may be other identifiers in other columns (not required here),
            # skip for now since user asked to use Pick List column primarily
            continue

    # preserve order & uniqueness
    seen = set()
    final = []
    for p in picks_raw:
        if p not in seen:
            seen.add(p)
            final.append(p)

    # sort numeric-only picks numerically while keeping non-numeric in original relative order
    numeric = [x for x in final if x.isdigit()]
    non_numeric = [x for x in final if not x.isdigit()]
    numeric_sorted = sorted(numeric, key=lambda s: int(s))

    return numeric_sorted + non_numeric

# ----------------------
# App UI
# ----------------------
st.set_page_config(page_title="List Finish Packing — Selection", layout="wide")
st.title("List Finish Packing — Selection")

# Sidebar: Admin PIC
selected_pic = st.sidebar.selectbox("Select Admin PIC", ADMIN_PICS)

# Load sheet
with st.spinner("Loading Google Sheet (J:O)..."):
    try:
        df_all = load_sheet_csv(CSV_URL)
    except Exception as e:
        st.error(f"Failed to load sheet CSV: {e}")
        st.stop()

# Try to subset to expected columns if present
# (sheet CSV may contain many columns; we only need the J:O named ones)
# Do a case-insensitive match of expected columns to available columns.
cols_map = {}
for c in df_all.columns:
    for exp in EXPECTED_COLS:
        if c.strip().lower() == exp.lower():
            cols_map[exp] = c

# If mapping incomplete, warn but continue with whatever is available
missing = [e for e in EXPECTED_COLS if e not in cols_map]
if missing:
    st.warning(f"Warning: expected columns not all found in sheet CSV: {missing}. Detected columns: {list(df_all.columns)}")

# Build normalized df with canonical column names where possible
df = df_all.rename(columns={v: k for k, v in cols_map.items()})

# Ensure columns we reference exist as string type to avoid dtype surprises
for col in ["DB", "Pick List", "Vessel", "PIC", "Timestamp", "Urgency"]:
    if col in df.columns:
        df[col] = df[col].astype(object)

# DB selection
selected_db = st.selectbox("DB", ["-- Select DB --"] + DB_LIST)

# Vessel selection depends on DB
vessel_options = []
selected_vessel = "-- Select Vessel --"
if selected_db and selected_db != "-- Select DB --":
    vessel_options = get_vessels_for_db(df, selected_db)
    selected_vessel = st.selectbox("Vessel", ["-- Select Vessel --"] + vessel_options)
else:
    selected_vessel = st.selectbox("Vessel", ["-- Select Vessel --"])

# Pick List multiselect depends on Vessel (and DB)
picklist_options = []
if selected_vessel and selected_vessel != "-- Select Vessel --" and selected_db and selected_db != "-- Select DB --":
    picklist_options = get_picklists_for_vessel(df, selected_db, selected_vessel)

selected_picklists = st.multiselect("Pick List (choose one or more)", options=picklist_options)

# Tujuan input
tujuan = st.text_input("Tujuan")

# Moda Pengiriman
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

# Placeholder action button
if st.button("Proceed / Save (placeholder)"):
    # basic validation
    errors = []
    if selected_db in ("", "-- Select DB --"):
        errors.append("Please select DB.")
    if selected_vessel in ("", "-- Select Vessel --"):
        errors.append("Please select Vessel.")
    if not selected_picklists:
        errors.append("Please select at least one Pick List.")
    if not tujuan:
        errors.append("Please enter Tujuan.")
    if moda in ("", "-- Select Moda --"):
        errors.append("Please select Moda Pengiriman.")

    if errors:
        st.error("Validation failed:\n- " + "\n- ".join(errors))
    else:
        st.success("Selections captured. (No write-back implemented in this version)")
        st.json({
            "admin_pic": selected_pic,
            "db": selected_db,
            "vessel": selected_vessel,
            "picklists": selected_picklists,
            "tujuan": tujuan,
            "moda": moda,
        })

# Preview loaded rows (J:O related columns)
with st.expander("Preview loaded data (relevant columns)"):
    preview_cols = [c for c in EXPECTED_COLS if c in df.columns]
    if preview_cols:
        st.dataframe(df[preview_cols].head(200))
    else:
        st.write("No expected columns found to preview.")
