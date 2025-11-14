import streamlit as st
import requests
import pandas as pd
from io import StringIO
from urllib.parse import quote_plus
from datetime import datetime

# ----------------------
# Configuration (public sheets)
# ----------------------
# main sheet (List Finish Packing)
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
WORKSHEET_NAME = "List Finish Packing"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote_plus(WORKSHEET_NAME)}"

# matrix numbering sheet (public) — PENOMORAN-MATRIX
MATRIX_SHEET_ID = "1d9nYJEqus6B4f_W1OrRYYo3mZuYbh9lRkSM7-ywNsCk"
MATRIX_SHEET_NAME = "PENOMORAN-MATRIX"
MATRIX_CSV_URL = f"https://docs.google.com/spreadsheets/d/{MATRIX_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote_plus(MATRIX_SHEET_NAME)}"

# static lists
ADMIN_PICS = [
    "Abim Priambada",
    "Maftuh Ikhsan",
    "Rifka Fahrul Musthofa",
    "Rudi Haryanto",
]

DB_LIST = ["DMI", "PBN", "PKS", "PMT", "PSM", "PSS", "PST"]

MODA_OPTIONS = ["Sea Freight", "Air Freight", "Land Freight", "Handcarry"]

# activity options requested
ACTIVITY_OPTIONS = ["APDP", "Petty Cash", "Delivery", "Scraps"]

# mapping for PIC -> short name used in matrix
PIC_SHORTNAME = {
    "Abim Priambada": "ABIM",
    "Maftuh Ikhsan": "MAFTUH",
    "Rifka Fahrul Musthofa": "FAHRUL",
    "Rudi Haryanto": "RUDI",
}

# expected columns to map (case-insensitive)
EXPECTED_COLS = ["DB", "Pick List", "Timestamp", "PIC", "Urgency", "Vessel", "Concat"]

# fixed sequence width (default 3 as requested)
SEQ_WIDTH = 3

# ----------------------
# Utilities
# ----------------------
@st.cache_data(ttl=300)
def load_sheet_csv(url: str) -> pd.DataFrame:
    """Load a public Google Sheet CSV into a pandas DataFrame."""
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    df = pd.read_csv(StringIO(resp.text), dtype=object)
    return df

def _clean_candidate_value(val):
    """Normalize candidate value: clean floats like 3008.0 -> '3008', preserve strings."""
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
    # try parse string numeric like "3008.0"
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

def _extract_from_concat(concat_val):
    """Concat format like 'DMI|3015' or 'DMI|DMI-Manual-1' => return last cleaned part."""
    if pd.isna(concat_val):
        return None
    s = str(concat_val).strip()
    if s == "":
        return None
    parts = [p.strip() for p in s.split("|") if p and p.strip() != ""]
    if not parts:
        return None
    return _clean_candidate_value(parts[-1])

def get_vessels_for_db(df: pd.DataFrame, selected_db: str) -> list:
    """Return sorted unique Vessel values for a DB (trim whitespace)."""
    if "DB" not in df.columns or "Vessel" not in df.columns:
        return []
    subset = df[df["DB"].astype(str).str.strip() == selected_db]
    vessels = subset["Vessel"].dropna().astype(str).str.strip().unique().tolist()
    vessels = [v for v in vessels if v != ""]
    return sorted(vessels)

def get_picklists_for_vessel_using_concat(df: pd.DataFrame, selected_db: str, selected_vessel: str) -> list:
    """
    Collect picklist IDs for rows matching DB+Vessel using Pick List, Concat, or Pick List NO.
    Returns unique picks in stable order: numeric picks sorted numerically first, then non-numeric in first-seen order.
    """
    if not {"DB", "Vessel"}.issubset(df.columns):
        return []
    cond = (df["DB"].astype(str).str.strip() == selected_db) & (df["Vessel"].astype(str).str.strip() == selected_vessel)
    rows = df.loc[cond, :]
    picks_raw = []
    for _, r in rows.iterrows():
        candidate = None
        if "Pick List" in r.index:
            candidate = _clean_candidate_value(r.get("Pick List", None))
        if (candidate is None or str(candidate).strip() == "") and "Concat" in r.index:
            candidate = _extract_from_concat(r.get("Concat", None))
        if (candidate is None or str(candidate).strip() == "") and "Pick List NO." in r.index:
            candidate = _clean_candidate_value(r.get("Pick List NO.", None))
        if candidate and str(candidate).strip() != "":
            picks_raw.append(str(candidate).strip())
    # preserve order & uniqueness
    seen = set()
    final_ordered = []
    for p in picks_raw:
        if p not in seen:
            seen.add(p)
            final_ordered.append(p)
    # numeric-first sort (numerics ascending), then non-numeric in original order
    numeric = [x for x in final_ordered if x.isdigit()]
    non_numeric = [x for x in final_ordered if not x.isdigit()]
    numeric_sorted = sorted(numeric, key=lambda s: int(s))
    return numeric_sorted + non_numeric

def aggregate_picklists_for_vessels(df: pd.DataFrame, selected_db: str, selected_vessels: list) -> list:
    """Aggregate picklists across multiple vessels preserving first-seen order then numeric-first sort."""
    if not selected_vessels:
        return []
    picks_seen = []
    for vessel in selected_vessels:
        for p in get_picklists_for_vessel_using_concat(df, selected_db, vessel):
            picks_seen.append(p)
    seen = set(); ordered = []
    for p in picks_seen:
        if p not in seen:
            seen.add(p); ordered.append(p)
    numeric = [x for x in ordered if x.isdigit()]
    non_numeric = [x for x in ordered if not x.isdigit()]
    numeric_sorted = sorted(numeric, key=lambda s: int(s))
    return numeric_sorted + non_numeric

# ----------------------
# Matrix numbering (STRICTLY using COUNTIF PIC from PENOMORAN-MATRIX)
# ----------------------
_ROMAN = {1:"I",2:"II",3:"III",4:"IV",5:"V",6:"VI",7:"VII",8:"VIII",9:"IX",10:"X",11:"XI",12:"XII"}

def _normalize_pic_for_count(raw_pic) -> str:
    """Normalize PIC string for counting: trim, collapse spaces for robust matching."""
    if pd.isna(raw_pic):
        return ""
    s = str(raw_pic).strip()
    s = " ".join(s.split())
    return s

def next_matrix_number_countif(df_matrix: pd.DataFrame, pic: str, db: str, activity: str, use_date: datetime | None = None, seq_width: int = SEQ_WIDTH) -> str:
    """
    Generate next NOMOR MATRIX strictly by COUNTIF PIC from df_matrix (PENOMORAN-MATRIX).
    - Counts rows where PIC (normalized) == selected pic (normalized), then next_seq = count + 1.
    - Uses PIC_SHORTNAME mapping for short name in the generated string.
    - If activity == "Delivery" -> token "DEL", else -> "OTHER".
    - Format: MATRIX - 026-<TOKEN>-<PicShort>-<DB>-<ROMANMONTH>-<YEAR>
    """
    if use_date is None:
        use_date = datetime.now()
    month_rom = _ROMAN.get(use_date.month, str(use_date.month))
    year = use_date.year

    # normalize pic for comparison (case-insensitive, collapsed spaces)
    target_pic_norm = _normalize_pic_for_count(pic)

    # detect PIC column name (case-insensitive)
    cols_lower = {c.lower(): c for c in df_matrix.columns}
    pic_col = None
    for cand in ["pic"]:
        if cand in cols_lower:
            pic_col = cols_lower[cand]
            break
    if pic_col is None:
        # fallback: any column named 'pic' ignoring case/spacing
        for c in df_matrix.columns:
            if c.strip().lower() == "pic":
                pic_col = c
                break

    # If pic_col not found, treat count as zero (next will be 1)
    if pic_col is None:
        count_for_pic = 0
    else:
        try:
            series = df_matrix[pic_col].astype(object).fillna("").apply(_normalize_pic_for_count)
            count_for_pic = int(series.eq(target_pic_norm).sum())
        except Exception:
            # safe fallback
            count_for_pic = 0

    next_seq = count_for_pic + 1
    seq_str = str(next_seq).zfill(seq_width)

    # PIC short name for final string: look up mapping, fallback to cleaned uppercase-without-spaces if missing
    pic_short = PIC_SHORTNAME.get(pic, None)
    if not pic_short:
        # fallback: remove spaces and capitalize first letter
        pic_short = str(pic).strip()
        pic_short = " ".join(pic_short.split())
        pic_short = pic_short.replace(" ", "")
    # activity token: Delivery -> DEL else OTHER
    token = "DEL" if str(activity).strip().lower() == "delivery" else "OTHER"

    db_for_str = str(db).strip().upper()

    matrix_str = f"MATRIX - {seq_str}-{token}-{pic_short}-{db_for_str}-{month_rom}-{year}"
    return matrix_str

# ----------------------
# App UI
# ----------------------
st.set_page_config(page_title="Matrix Generator (Pick Lists)", layout="wide")
st.title("Matrix Generator — Pick Lists & Numbering")

# Load both sheets (public)
with st.spinner("Loading sheets..."):
    try:
        df_main = load_sheet_csv(CSV_URL)
    except Exception as e:
        st.error(f"Failed to load main sheet: {e}")
        st.stop()
    try:
        df_matrix = load_sheet_csv(MATRIX_CSV_URL)
    except Exception as e:
        st.error(f"Failed to load matrix sheet: {e}")
        st.stop()

# Map expected columns case-insensitively in main df
cols_map = {}
for c in df_main.columns:
    for exp in EXPECTED_COLS:
        if c.strip().lower() == exp.lower():
            cols_map[exp] = c
df = df_main.rename(columns={v: k for k, v in cols_map.items()})

# ensure object dtype for referenced cols
for col in ["DB","Pick List","Vessel","Concat","PIC","Timestamp","Urgency"]:
    if col in df.columns:
        df[col] = df[col].astype(object)

# Main inputs
selected_pic = st.selectbox("Select Admin PIC", ADMIN_PICS)
selected_db = st.selectbox("DB", ["-- Select DB --"] + DB_LIST)
selected_activity = st.selectbox("Activity", ACTIVITY_OPTIONS)

# Vessel multiselect (based on DB)
vessel_options = []
if selected_db and selected_db != "-- Select DB --":
    vessel_options = get_vessels_for_db(df, selected_db)
selected_vessels = st.multiselect("Vessel (choose one or more)", options=vessel_options)

# Aggregate picklist options across selected vessels
picklist_options = []
if selected_db and selected_db != "-- Select DB --" and selected_vessels:
    picklist_options = aggregate_picklists_for_vessels(df, selected_db, selected_vessels)

selected_picklists = st.multiselect("Pick List (choose one or more)", options=picklist_options)

# Tujuan and Moda Pengiriman
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

# Matrix generator UI (COUNTIF PIC strictly, seq width fixed)
st.markdown("### Matrix number")
with st.expander("Generate next NOMOR MATRIX for this PIC (COUNTIF PIC from PENOMORAN-MATRIX)"):
    chosen_date = st.date_input("Matrix Date (used to build month/year)", value=datetime.now().date())
    st.write(f"Sequence zero-pad width is fixed to {SEQ_WIDTH}.")
    if st.button("Generate Matrix Number"):
        try:
            matrix_number = next_matrix_number_countif(
                df_matrix,
                pic=selected_pic,
                db=selected_db if selected_db and selected_db != "-- Select DB --" else "UNKNOWN",
                activity=selected_activity,
                use_date=datetime.combine(chosen_date, datetime.min.time()),
                seq_width=SEQ_WIDTH,
            )
            st.success("Generated: " + matrix_number)
            st.code(matrix_number)
        except Exception as e:
            st.error(f"Failed to generate matrix number: {e}")

# Placeholder Submit / Save
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
            "activity": selected_activity,
            "vessels": selected_vessels,
            "picklists": selected_picklists,
            "tujuan": tujuan,
            "moda": moda,
        })

# Debug / preview
with st.expander("Preview loaded data (A:G if available)"):
    preview_cols = [c for c in ["DB","Pick List","Timestamp","PIC","Urgency","Vessel","Concat"] if c in df.columns]
    if preview_cols:
        st.dataframe(df[preview_cols].head(200))
    else:
        st.dataframe(df.head(200))

# --- Diagnostic block: paste into your Matrix expander just before generation ---
import re
st.write("**Diagnostic: PENOMORAN-MATRIX PIC matching**")

# confirm df_matrix exists and shape
st.write("Matrix DF loaded rows:", None if 'df_matrix' not in globals() else df_matrix.shape)

# find pic column robustly
pic_col = None
if 'df_matrix' in globals():
    cols_lower = {c.strip().lower(): c for c in df_matrix.columns}
    for key in ["pic", "person in charge", "penanggung jawab"]:
        if key in cols_lower:
            pic_col = cols_lower[key]
            break
    if pic_col is None:
        # fallback: any column name containing "pic"
        for c in df_matrix.columns:
            if "pic" in c.lower():
                pic_col = c
                break

st.write("Detected PIC column:", pic_col)

if pic_col and 'df_matrix' in globals():
    raw_series = df_matrix[pic_col].astype(object).fillna("").astype(str)
    st.subheader("Sample PIC values (first 50)")
    st.write(raw_series.head(50).tolist())
    st.subheader("Unique PIC value counts (top 50)")
    st.write(raw_series.value_counts().head(50))

    target = str(selected_pic)
    def collapse_spaces(s): return " ".join(s.split())
    def remove_spaces(s): return "".join(s.split())
    # prepared normalized series
    v_strip = raw_series.str.strip()
    v_up_collapsed = v_strip.apply(collapse_spaces).str.upper()
    v_up_nospaces = v_strip.apply(remove_spaces).str.upper()
    v_up_raw = v_strip.str.upper()

    t_strip = target.strip()
    t_up_collapsed = collapse_spaces(t_strip).upper()
    t_up_nospaces = remove_spaces(t_strip).upper()
    t_up_raw = t_strip.upper()

    counts = {
        "raw_exact": int((raw_series == target).sum()),
        "strip_exact": int((v_strip == t_strip).sum()),
        "upper+collapsed": int((v_up_collapsed == t_up_collapsed).sum()),
        "upper+nospaces": int((v_up_nospaces == t_up_nospaces).sum()),
        "upper+raw": int((v_up_raw == t_up_raw).sum())
    }
    st.write("Counts by strategy:", counts)

    # fuzzy tokens
    tokens = [t.upper() for t in re.findall(r"\w+", t_strip)]
    fuzzy_count = int(raw_series.apply(lambda s: all(tok in s.upper() for tok in tokens)).sum()) if tokens else 0
    st.write("fuzzy_token_contains_count:", fuzzy_count)

else:
    st.warning("df_matrix or PIC column not found — check sheet loaded and header names.")

