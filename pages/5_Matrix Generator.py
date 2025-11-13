import streamlit as st
import requests
import pandas as pd
from io import StringIO
from urllib.parse import quote_plus

# Optional auth import — if you don't have it, comment out the two lines that use check_password.
try:
    from auth import check_password
    USE_AUTH = True
except Exception:
    USE_AUTH = False
    check_password = lambda: True  # dummy

# ----------------------
# Configuration
# ----------------------
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
WORKSHEET_NAME = "List Finish Packing"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote_plus(WORKSHEET_NAME)}"

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

# Expected columns we care about (A:G area); 'Concat' is present in your sheet screenshots
EXPECTED_COLS = ["DB", "Pick List", "Timestamp", "PIC", "Urgency", "Vessel", "Concat"]

# ----------------------
# Helpers
# ----------------------
@st.cache_data(ttl=300)
def load_sheet_csv(url: str) -> pd.DataFrame:
    """Fetch published CSV and return DataFrame (all columns)."""
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    df = pd.read_csv(StringIO(resp.text), dtype=object)
    return df


def clean_candidate_value(val):
    """
    Normalize a candidate pick-list value:
     - If numeric float or string representing integer (e.g. '3008.0') -> '3008'
     - If integer -> '123'
     - If alphanumeric -> keep trimmed string (e.g. 'DMI-Manual-1')
     - Return None for empty-like values
    """
    if pd.isna(val):
        return None
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        s = repr(val)
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s
    s = str(val).strip()
    if s == "" or s.lower() in {"nan", "none"}:
        return None
    # try parse string number like '3008.0'
    try:
        fv = float(s)
        if fv.is_integer():
            return str(int(fv))
        s2 = str(fv)
        if "." in s2:
            s2 = s2.rstrip("0").rstrip(".")
        return s2
    except Exception:
        return s


def extract_from_concat(concat_val):
    """
    Concat appears as 'DB|Pick' like 'DMI|3015' or 'PKS|PKS-Manual-1'.
    Return the last segment after '|' cleaned, or None.
    """
    if pd.isna(concat_val):
        return None
    s = str(concat_val).strip()
    if s == "":
        return None
    parts = [p.strip() for p in s.split("|") if p and p.strip() != ""]
    if not parts:
        return None
    # take last part and clean it
    return clean_candidate_value(parts[-1])


def get_vessels_for_db(df: pd.DataFrame, selected_db: str) -> list:
    """Return sorted unique Vessel values for a DB (trimmed strings)."""
    if "DB" not in df.columns or "Vessel" not in df.columns:
        return []
    subset = df[df["DB"].astype(str).str.strip() == selected_db]
    vessels = subset["Vessel"].dropna().astype(str).str.strip().unique().tolist()
    vessels = [v for v in vessels if v != ""]
    return sorted(vessels)


def get_picklists_for_vessel_using_concat(df: pd.DataFrame, selected_db: str, selected_vessel: str) -> list:
    """
    Build pick list options for a selected DB+Vessel using:
      1) 'Pick List' column (cleaned)
      2) fallback to 'Concat' column (extract last segment after '|')
      3) fallback to 'Pick List NO.' if present
    Preserves order & uniqueness; numeric-only picks are sorted numerically first,
    then non-numeric picks kept in their first-seen order.
    """
    if not {"DB", "Vessel"}.issubset(df.columns):
        return []

    cond = (df["DB"].astype(str).str.strip() == selected_db) & (df["Vessel"].astype(str).str.strip() == selected_vessel)
    rows = df.loc[cond, :]

    picks_raw = []
    for _, r in rows.iterrows():
        candidate = None
        if "Pick List" in r.index:
            candidate = clean_candidate_value(r.get("Pick List", None))
        if (candidate is None or str(candidate).strip() == "") and "Concat" in r.index:
            candidate = extract_from_concat(r.get("Concat", None))
        if (candidate is None or str(candidate).strip() == "") and "Pick List NO." in r.index:
            candidate = clean_candidate_value(r.get("Pick List NO.", None))

        if candidate and str(candidate).strip() != "":
            picks_raw.append(str(candidate).strip())

    # preserve order & uniqueness
    seen = set()
    final_ordered = []
    for p in picks_raw:
        if p not in seen:
            seen.add(p)
            final_ordered.append(p)

    numeric = [x for x in final_ordered if x.isdigit()]
    non_numeric = [x for x in final_ordered if not x.isdigit()]
    numeric_sorted = sorted(numeric, key=lambda s: int(s))
    return numeric_sorted + non_numeric


def aggregate_picklists_for_vessels(df: pd.DataFrame, selected_db: str, selected_vessels: list) -> list:
    """
    Given a list of selected vessels, collect picklist options from each vessel (in the order of the vessel list),
    preserve first-seen order, then produce numeric-first sorted output.
    """
    if not selected_vessels:
        return []
    picks_seen = []
    for vessel in selected_vessels:
        picks = get_picklists_for_vessel_using_concat(df, selected_db, vessel)
        for p in picks:
            picks_seen.append(p)  # we dedupe later preserving first-seen
    # dedupe preserving order
    seen = set()
    ordered = []
    for p in picks_seen:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    # final numeric-first order: numeric sorted, then non-numeric in their preserved order
    numeric = [x for x in ordered if x.isdigit()]
    non_numeric = [x for x in ordered if not x.isdigit()]
    numeric_sorted = sorted(numeric, key=lambda s: int(s))
    return numeric_sorted + non_numeric


# ----------------------
# App UI
# ----------------------
st.set_page_config(page_title="Matrix Generator", layout="wide")
st.title("Matrix Generator")

# auth (optional)
if USE_AUTH:
    ok = check_password()
else:
    ok = True

if not ok:
    st.stop()

# MAIN PAGE: place PIC on main page (not sidebar)
selected_pic = st.selectbox("Select Admin PIC", ADMIN_PICS)

# Load sheet CSV
with st.spinner("Loading sheet..."):
    try:
        df_all = load_sheet_csv(CSV_URL)
    except Exception as e:
        st.error(f"Failed to load sheet CSV: {e}")
        st.stop()

# Map expected columns case-insensitively
cols_map = {}
for c in df_all.columns:
    for exp in EXPECTED_COLS:
        if c.strip().lower() == exp.lower():
            cols_map[exp] = c

missing = [e for e in EXPECTED_COLS if e not in cols_map]
if missing:
    st.info(f"Note: some expected columns not found: {missing}. Available cols: {list(df_all.columns)}")

# rename to canonical names where possible
df = df_all.rename(columns={v: k for k, v in cols_map.items()})

# Ensure referenced columns exist and are object-typed
for col in ["DB", "Pick List", "Vessel", "Concat", "PIC", "Timestamp", "Urgency"]:
    if col in df.columns:
        df[col] = df[col].astype(object)

# DB select
selected_db = st.selectbox("DB", ["-- Select DB --"] + DB_LIST)

# Vessel multiselect depends on DB (allow user to pick multiple vessels)
vessel_options = []
if selected_db and selected_db != "-- Select DB --":
    vessel_options = get_vessels_for_db(df, selected_db)
selected_vessels = st.multiselect("Vessel (choose one or more)", options=vessel_options)

# Build aggregated picklist options from all selected vessels
picklist_options = []
if selected_db and selected_db != "-- Select DB --" and selected_vessels:
    picklist_options = aggregate_picklists_for_vessels(df, selected_db, selected_vessels)

# Debug: show raw A:G rows for selected DB+Vessels
with st.expander("🔎 Debug: raw A:G rows for selected DB+Vessel(s)"):
    if selected_db and selected_db != "-- Select DB --" and selected_vessels:
        cond = (df["DB"].astype(str).str.strip() == selected_db) & (df["Vessel"].astype(str).str.strip().isin(selected_vessels))
        debug_rows = df.loc[cond, :]
        cols_a_to_g = [c for c in ["DB", "Pick List", "Timestamp", "PIC", "Urgency", "Vessel", "Concat"] if c in debug_rows.columns]
        if cols_a_to_g:
            st.dataframe(debug_rows[cols_a_to_g].head(200))
        else:
            st.dataframe(debug_rows.head(200))
    else:
        st.write("Select DB and at least one Vessel to preview these rows.")

# Multi-select pick lists (options derived from selected vessels)
selected_picklists = st.multiselect("Pick List (choose one or more)", options=picklist_options)

# Tujuan and Moda Pengiriman
tujuan = st.text_input("Tujuan")
moda = st.selectbox("Moda Pengiriman", ["-- Select Moda --"] + MODA_OPTIONS)

st.divider()
st.subheader("Selection Summary")
st.write({
    "Admin PIC": selected_pic,
    "DB": selected_db,
    "Vessel(s)": selected_vessels,
    "Pick List(s)": selected_picklists,
    "Tujuan": tujuan,
    "Moda Pengiriman": moda,
})

# Placeholder action button (no write-back)
if st.button("Proceed / Save (placeholder)"):
    errors = []
    if selected_db in ("", "-- Select DB --"):
        errors.append("Please select DB.")
    if not selected_vessels:
        errors.append("Please select at least one Vessel.")
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
            "vessels": selected_vessels,
            "picklists": selected_picklists,
            "tujuan": tujuan,
            "moda": moda,
        })

# Preview relevant columns
with st.expander("Preview loaded data (A:G if available)"):
    preview_cols = [c for c in ["DB", "Pick List", "Timestamp", "PIC", "Urgency", "Vessel", "Concat"] if c in df.columns]
    if preview_cols:
        st.dataframe(df[preview_cols].head(200))
    else:
        st.write("No A:G columns found to preview.")
