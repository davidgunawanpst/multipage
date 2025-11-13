import streamlit as st
import requests
import pandas as pd
from io import StringIO
from urllib.parse import quote_plus

# If you use auth, keep this import and the check_password() call below.
# If you don't have auth.py, remove the import and the conditional.
from auth import check_password  # keep your auth (comment out if not available)

# ----------------------
# Configuration
# ----------------------
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
WORKSHEET_NAME = "List Finish Packing"  # tab name (not encoded here)
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


def extract_from_unique_code(unique_code_value) -> str | None:
    """
    If Unique Code looks like 'DMI|DMI-Manual-1' or 'DMI|3005', return last non-empty segment.
    Otherwise return None.
    """
    if unique_code_value is None:
        return None
    s = str(unique_code_value).strip()
    if s == "":
        return None
    # split on '|' and return last non-empty part
    parts = [p.strip() for p in s.split("|") if p and p.strip() != ""]
    if not parts:
        return None
    return parts[-1]


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

    # direct numeric types
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

    # try parse strings like "3008.0" -> 3008
    try:
        fv = float(s_val)
        if fv.is_integer():
            return str(int(fv))
        s = str(fv)
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        return s
    except Exception:
        # not a float -> keep original trimmed string (preserves alphanumeric picks)
        return s_val


def get_vessels_for_db(df: pd.DataFrame, selected_db: str) -> list[str]:
    """Return sorted unique Vessel values for a DB (preserve strings)."""
    if "DB" not in df.columns or "Vessel" not in df.columns:
        return []
    subset = df[df["DB"].astype(str).str.strip() == selected_db]
    vessels = subset["Vessel"].dropna().astype(str).str.strip().unique().tolist()
    vessels = [v for v in vessels if v != ""]
    return sorted(vessels)


def get_picklists_for_vessel(df: pd.DataFrame, selected_db: str, selected_vessel: str) -> list[str]:
    """
    Return pick list identifiers for rows matching DB & Vessel.
    Will try multiple columns per-row in this order:
      1) 'Pick List'
      2) 'Pick List NO.' (if present)
      3) 'Unique Code' (extract last segment)
      4) fallback scan across other columns for a candidate
    Preserves order for non-numeric strings and sorts numeric-only picks numerically first.
    """
    if not {"DB", "Vessel"}.issubset(df.columns):
        return []

    # candidate columns to try, in order of preference
    candidate_cols_preferred = ["Pick List", "Pick List NO.", "Unique Code"]
    candidate_cols = [c for c in candidate_cols_preferred if c in df.columns]

    cond = (df["DB"].astype(str).str.strip() == selected_db) & (df["Vessel"].astype(str).str.strip() == selected_vessel)
    rows = df.loc[cond, :]

    picks_raw = []
    for _, r in rows.iterrows():
        candidate = None
        # try preferred columns
        for col in candidate_cols:
            raw_val = r.get(col, None)
            if raw_val is None or (isinstance(raw_val, float) and pd.isna(raw_val)):
                continue
            if col == "Unique Code":
                candidate = extract_from_unique_code(raw_val)
            else:
                candidate = fmt_picklist_value(raw_val)
            if candidate:
                break  # found usable value for this row

        # fallback: scan other columns for anything plausible
        if not candidate:
            for colname in r.index:
                if colname in candidate_cols:
                    continue
                raw_val = r.get(colname, None)
                if raw_val is None or (isinstance(raw_val, float) and pd.isna(raw_val)):
                    continue
                maybe = fmt_picklist_value(raw_val)
                if maybe:
                    candidate = maybe
                    break

        if candidate and str(candidate).strip() != "":
            picks_raw.append(str(candidate).strip())

    # preserve order & uniqueness
    seen = set()
    final_ordered = []
    for p in picks_raw:
        if p not in seen:
            seen.add(p)
            final_ordered.append(p)

    # separate numeric-only and non-numeric
    numeric = [x for x in final_ordered if x.isdigit()]
    non_numeric = [x for x in final_ordered if not x.isdigit()]

    # numeric sorted numerically, then non-numeric in original order
    numeric_sorted = sorted(numeric, key=lambda s: int(s))
    return numeric_sorted + non_numeric


# ----------------------
# App UI
# ----------------------
st.set_page_config(page_title="List Finish Packing — Selection", layout="wide")
st.title("List Finish Packing — Selection")

# Optionally require password/auth if you have auth.py
use_auth = True
try:
    if use_auth:
        ok = check_password()
    else:
        ok = True
except Exception:
    # If check_password not available or raises, skip auth (but warn)
    ok = True
    st.warning("Auth check skipped (auth.py/check_password not available).")

if not ok:
    st.stop()

# Sidebar: Admin PIC
selected_pic = st.sidebar.selectbox("Select Admin PIC", ADMIN_PICS)

# Load sheet (CSV)
with st.spinner("Loading Google Sheet (J:O)..."):
    try:
        df_all = load_sheet_csv(CSV_URL)
    except Exception as e:
        st.error(f"Failed to load sheet CSV: {e}")
        st.stop()

# Do a case-insensitive mapping of expected columns to what's in the CSV
cols_map = {}
for c in df_all.columns:
    for exp in EXPECTED_COLS:
        if c.strip().lower() == exp.lower():
            cols_map[exp] = c

missing = [e for e in EXPECTED_COLS if e not in cols_map]
if missing:
    st.warning(f"Warning: expected columns not all found in sheet CSV: {missing}. Detected columns: {list(df_all.columns)}")

# Build normalized df with canonical column names where possible
df = df_all.rename(columns={v: k for k, v in cols_map.items()})

# Ensure referenced columns exist and are object-typed to avoid unexpected casting
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
if selected_db and selected_db != "-- Select DB --" and selected_vessel and selected_vessel != "-- Select Vessel --":
    picklist_options = get_picklists_for_vessel(df, selected_db, selected_vessel)

# Debug expander showing raw candidate columns for selected DB+Vessel
with st.expander("🔎 Debug: raw candidate columns for selected DB+Vessel"):
    if selected_db and selected_db != "-- Select DB --" and selected_vessel and selected_vessel != "-- Select Vessel --":
        cond = (df["DB"].astype(str).str.strip() == selected_db) & (df["Vessel"].astype(str).str.strip() == selected_vessel)
        debug_rows = df.loc[cond, :]
        # show the commonly used columns if present
        debug_cols = [c for c in ["Pick List", "Pick List NO.", "Unique Code"] if c in debug_rows.columns]
        if not debug_cols:
            st.write("No candidate columns (Pick List / Pick List NO. / Unique Code) present in the matching rows.")
        else:
            st.dataframe(debug_rows[debug_cols].head(200))
    else:
        st.write("Select DB and Vessel to preview rows.")

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

# Preview loaded rows (relevant columns)
with st.expander("Preview loaded data (relevant columns)"):
    preview_cols = [c for c in EXPECTED_COLS if c in df.columns]
    if preview_cols:
        st.dataframe(df[preview_cols].head(200))
    else:
        st.write("No expected columns found to preview.")
