import streamlit as st
import requests
import pandas as pd
from io import StringIO
from urllib.parse import quote_plus
from datetime import datetime

# ----------------------
# Configuration (public sheets)
# ----------------------
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
WORKSHEET_NAME = "List Finish Packing"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote_plus(WORKSHEET_NAME)}"

# Matrix numbering sheet
MATRIX_SHEET_ID = "1d9nYJEqus6B4f_W1OrRYYo3mZuYbh9lRkSM7-ywNsCk"
MATRIX_SHEET_NAME = "PENOMORAN-MATRIX"
MATRIX_CSV_URL = f"https://docs.google.com/spreadsheets/d/{MATRIX_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote_plus(MATRIX_SHEET_NAME)}"

ADMIN_PICS = [
    "Abim Priambada",
    "Maftuh Ikhsan",
    "Fahrul",
    "Rudi Haryanto",
]

DB_LIST = ["DMI", "PBN", "PKS", "PMT", "PSM", "PSS", "PST"]

MODA_OPTIONS = ["Sea Freight", "Air Freight", "Land Freight", "Handcarry"]

ACTIVITY_OPTIONS = ["APDP", "Petty Cash", "Delivery", "Scraps"]

PIC_SHORTNAME = {
    "Abim Priambada": "ABIM",
    "Maftuh Ikhsan": "MAFTUH",
    "Fahrul": "FAHRUL",
    "Rudi Haryanto": "RUDI",
}

EXPECTED_COLS = ["DB", "Pick List", "Timestamp", "PIC", "Urgency", "Vessel", "Concat"]

SEQ_WIDTH = 3  # fixed padding of running number

# ----------------------
# Utility functions
# ----------------------
@st.cache_data(ttl=300)
def load_sheet_csv(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text), dtype=object)

def _clean_candidate_value(val):
    """Clean float values like 3008.0 -> '3008' and preserve strings."""
    if pd.isna(val):
        return None
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    s = str(val).strip()
    if s.lower() in {"nan", "none", ""}:
        return None
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
        return s.rstrip("0").rstrip(".")
    except:
        return s

def _extract_from_concat(concat_val):
    if pd.isna(concat_val):
        return None
    s = str(concat_val).strip()
    if not s:
        return None
    parts = [p.strip() for p in s.split("|") if p.strip()]
    if not parts:
        return None
    return _clean_candidate_value(parts[-1])

def get_vessels_for_db(df, selected_db):
    if "DB" not in df.columns or "Vessel" not in df.columns:
        return []
    subset = df[df["DB"].astype(str).str.strip() == selected_db]
    vessels = subset["Vessel"].dropna().astype(str).str.strip().unique().tolist()
    return sorted([v for v in vessels if v])

def get_picklists_for_vessel_using_concat(df, selected_db, selected_vessel):
    if not {"DB", "Vessel"}.issubset(df.columns):
        return []
    cond = (df["DB"].astype(str).str.strip() == selected_db) & \
           (df["Vessel"].astype(str).str.strip() == selected_vessel)
    rows = df.loc[cond]

    picks = []
    for _, r in rows.iterrows():
        candidate = _clean_candidate_value(r.get("Pick List"))
        if not candidate:
            candidate = _extract_from_concat(r.get("Concat"))
        if not candidate:
            candidate = _clean_candidate_value(r.get("Pick List NO."))
        if candidate:
            picks.append(str(candidate).strip())

    # preserve order
    seen = set()
    ordered = []
    for p in picks:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    numeric = [x for x in ordered if x.isdigit()]
    non_numeric = [x for x in ordered if not x.isdigit()]

    return sorted(numeric, key=lambda s: int(s)) + non_numeric

def aggregate_picklists_for_vessels(df, selected_db, selected_vessels):
    picks = []
    for v in selected_vessels or []:
        picks.extend(get_picklists_for_vessel_using_concat(df, selected_db, v))

    seen = set()
    ordered = []
    for p in picks:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    numeric = [x for x in ordered if x.isdigit()]
    non_numeric = [x for x in ordered if not x.isdigit()]
    return sorted(numeric, key=lambda s: int(s)) + non_numeric

# ----------------------
# STRICT EXACT COUNTIF PIC LOGIC
# ----------------------
_ROMAN = {1:"I",2:"II",3:"III",4:"IV",5:"V",6:"VI",7:"VII",8:"VIII",9:"IX",10:"X",11:"XI",12:"XII"}

def next_matrix_number_countif(df_matrix, pic, db, activity, use_date=None):
    """
    STRICT EXACT MATCH (trim only):
    count rows where strip(PIC_sheet) == strip(selected_pic)
    """

    if use_date is None:
        use_date = datetime.now()

    # detect PIC column
    pic_col = None
    for c in df_matrix.columns:
        if c.strip().lower() == "pic":
            pic_col = c
            break

    if pic_col is None:
        count_for_pic = 0
    else:
        # strict exact trim-only comparison
        target = str(pic).strip()
        series = df_matrix[pic_col].astype(str).apply(lambda x: str(x).strip())
        count_for_pic = (series == target).sum()

    seq = str(count_for_pic + 1).zfill(SEQ_WIDTH)

    month_rom = _ROMAN.get(use_date.month, str(use_date.month))
    year = use_date.year
    token = "DEL" if activity.strip().lower() == "delivery" else "OTHER"

    pic_short = PIC_SHORTNAME.get(pic, pic.replace(" ", ""))

    db_up = db.strip().upper()

    return f"MATRIX - {seq}-{token}-{pic_short}-{db_up}-{month_rom}-{year}"

# ----------------------
# App UI
# ----------------------
st.set_page_config(page_title="Matrix Generator (Pick Lists)", layout="wide")
st.title("Matrix Generator — Pick Lists & Numbering")

with st.spinner("Loading sheets..."):
    df_main = load_sheet_csv(CSV_URL)
    df_matrix = load_sheet_csv(MATRIX_CSV_URL)

# map expected columns
cols_map = {}
for c in df_main.columns:
    for exp in EXPECTED_COLS:
        if c.strip().lower() == exp.lower():
            cols_map[exp] = c

df = df_main.rename(columns={v: k for k, v in cols_map.items()})

for col in EXPECTED_COLS:
    if col in df.columns:
        df[col] = df[col].astype(object)

selected_pic = st.selectbox("Select Admin PIC", ADMIN_PICS)
selected_db = st.selectbox("DB", ["-- Select DB --"] + DB_LIST)
selected_activity = st.selectbox("Activity", ACTIVITY_OPTIONS)

vessel_options = get_vessels_for_db(df, selected_db) if selected_db not in ("", "-- Select DB --") else []
selected_vessels = st.multiselect("Vessel (choose one or more)", vessel_options)

picklist_options = []
if selected_db not in ("", "-- Select DB --") and selected_vessels:
    picklist_options = aggregate_picklists_for_vessels(df, selected_db, selected_vessels)

selected_picklists = st.multiselect("Pick List (choose one or more)", picklist_options)

tujuan = st.text_input("Tujuan")
moda = st.selectbox("Moda Pengiriman", ["-- Select Moda --"] + MODA_OPTIONS)

st.divider()
st.subheader("Selection Summary")
st.write({
    "Admin PIC": selected_pic,
    "DB": selected_db,
    "Activity": selected_activity,
    "Vessel(s)": selected_vessels,
    "Pick List(s)": selected_picklists,
    "Tujuan": tujuan,
    "Moda Pengiriman": moda,
})

# MATRIX GENERATOR
st.markdown("### Matrix number")
with st.expander("Generate next NOMOR MATRIX"):
    chosen_date = st.date_input("Matrix Date", datetime.now().date())
    if st.button("Generate Matrix Number"):
        number = next_matrix_number_countif(
            df_matrix,
            pic=selected_pic,
            db=selected_db if selected_db not in ("", "-- Select DB --") else "UNKNOWN",
            activity=selected_activity,
            use_date=datetime.combine(chosen_date, datetime.min.time())
        )
        st.success("Generated: " + number)
        st.code(number)

# VALIDATION / PLACEHOLDER
if st.button("Proceed / Save (placeholder)"):
    errors = []
    if selected_db in ("", "-- Select DB --"):
        errors.append("Select DB.")
    if not selected_vessels:
        errors.append("Select at least one Vessel.")
    if not selected_picklists:
        errors.append("Select at least one Pick List.")
    if not tujuan:
        errors.append("Enter Tujuan.")
    if moda in ("", "-- Select Moda --"):
        errors.append("Select Moda Pengiriman.")
    if errors:
        st.error("Validation failed:\n- " + "\n- ".join(errors))
    else:
        st.success("Selections captured.")
        st.json({
            "admin_pic": selected_pic,
            "db": selected_db,
            "activity": selected_activity,
            "vessels": selected_vessels,
            "picklists": selected_picklists,
            "tujuan": tujuan,
            "moda": moda,
        })

with st.expander("Preview loaded data (A:G if available)"):
    preview_cols = [c for c in EXPECTED_COLS if c in df.columns]
    st.dataframe(df[preview_cols].head(200))
