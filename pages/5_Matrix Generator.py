import streamlit as st
import requests
import pandas as pd
from io import StringIO
from urllib.parse import quote_plus
from datetime import datetime
import time

# ----------------------
# Configuration (public sheets)
# ----------------------
# main sheet (List Finish Packing)
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
WORKSHEET_NAME = "List Finish Packing"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote_plus(WORKSHEET_NAME)}"

# sheet for picklist source
LIST_ALL_PACKING_SHEET = "List All Packing"
LIST_ALL_PACKING_CSV = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote_plus(LIST_ALL_PACKING_SHEET)}"

# matrix numbering sheet (public)
MATRIX_SHEET_ID = "1ICIDY-69EvwZAY2EjdOhN8lCvWu4vRtjLVX1Y1-Nm4o"
MATRIX_SHEET_NAME = "PENOMORAN MATRIX"
MATRIX_CSV_URL = f"https://docs.google.com/spreadsheets/d/{MATRIX_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote_plus(MATRIX_SHEET_NAME)}"

# matrix numbering sheet 2
MATRIX2_SHEET_NAME = "PENOMORAN MATRIX STREAMLIT"
MATRIX2_CSV_URL = f"https://docs.google.com/spreadsheets/d/{MATRIX_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={quote_plus(MATRIX2_SHEET_NAME)}"

# webhook URL
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyCf9IGtpa8z3IQ0Nn7_3HE94812q4_iAzCWf8sRIXLIqhGGsp6F2Huf9gl76IBjrcn3g/exec"

# static lists
ADMIN_PICS = ["Abim Priambada","Maftuh Ikhsan","Fahrul","Rudi Haryanto"]
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
SEQ_WIDTH = 3

# ----------------------
# Utilities
# ----------------------
@st.cache_data(ttl=300)
def load_sheet_csv(url: str) -> pd.DataFrame:
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text), dtype=object)

def load_sheet_csv_fresh(url: str) -> pd.DataFrame:
    sep = "&" if "?" in url else "?"
    url_fresh = f"{url}{sep}_={int(time.time() * 1000)}"
    resp = requests.get(url_fresh, timeout=20)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text), dtype=object)

def get_vessels_for_db(df: pd.DataFrame, selected_db: str) -> list:
    if "DB" not in df.columns or "Vessel" not in df.columns:
        return []
    subset = df[df["DB"].astype(str).str.strip() == selected_db]
    vessels = subset["Vessel"].dropna().astype(str).str.strip().unique().tolist()
    return sorted([v for v in vessels if v != ""])

# ----------------------
# Matrix numbering
# ----------------------
_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI",
          7: "VII", 8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII"}

def next_matrix_number_countif_multi(df_matrix_a, df_matrix_b, pic, db, activity, use_date=None, seq_width=3):
    if use_date is None:
        use_date = datetime.now()
    month_rom = _ROMAN.get(use_date.month, str(use_date.month))
    year = use_date.year

    pic_col_a = next((c for c in df_matrix_a.columns if c.strip().lower() == "pic"), None)
    count_a = df_matrix_a[pic_col_a].astype(str).str.strip().eq(pic).sum() if pic_col_a else 0

    pic_col_b = next((c for c in df_matrix_b.columns if c.strip().lower() == "pic"), None)
    count_b = df_matrix_b[pic_col_b].astype(str).str.strip().eq(pic).sum() if pic_col_b else 0

    next_seq = int(count_a + count_b + 1)
    seq_str = str(next_seq).zfill(seq_width)

    pic_short = PIC_SHORTNAME.get(pic, pic.replace(" ", ""))
    token = "DEL" if str(activity).strip().lower() == "delivery" else "OTHER"

    return f"MATRIX - {seq_str}-{token}-{pic_short}-{db}-{month_rom}-{year}"

# ----------------------
# Streamlit UI
# ----------------------
st.set_page_config(page_title="Matrix Generator", layout="wide")
st.title("Matrix Generator — Pick Lists & Numbering")

with st.spinner("Loading main sheet..."):
    try:
        df_main = load_sheet_csv(CSV_URL)
    except Exception as e:
        st.error(f"Failed to load main sheet: {e}")
        st.stop()

cols_map = {exp: c for c in df_main.columns for exp in EXPECTED_COLS if c.strip().lower() == exp.lower()}
df = df_main.rename(columns={v: k for k, v in cols_map.items()})

for col in ["DB","Pick List","Vessel","Concat","PIC","Timestamp","Urgency"]:
    if col in df.columns:
        df[col] = df[col].astype(object)

selected_pic = st.selectbox("Select Admin PIC", ADMIN_PICS)
selected_db = st.selectbox("DB", ["-- Select DB --"] + DB_LIST)
selected_activity = st.selectbox("Activity", ACTIVITY_OPTIONS)

vessel_options = get_vessels_for_db(df, selected_db) if selected_db != "-- Select DB --" else []
selected_vessels = st.multiselect("Vessel (choose one or more)", vessel_options)

# ----------------------
# Picklists from List All Packing
# ----------------------
def extract_picklist_candidates_from_row(r):
    for colname in ["Pick List", "Pick List NO.", "Picklist", "Picklist No.", "Concat"]:
        if colname in r and pd.notna(r[colname]) and str(r[colname]).strip() != "":
            return str(r[colname]).strip()
    return None

try:
    df_all = load_sheet_csv(LIST_ALL_PACKING_CSV)

    finish_col = None
    tanggal_col = None
    for c in df_all.columns:
        cl = c.strip().lower()
        if cl == "actual finish packing":
            finish_col = c
        elif cl == "tanggal matrix":
            tanggal_col = c

    finish_nonempty = df_all[finish_col].astype(str).str.strip() != "" if finish_col else pd.Series([False]*len(df_all))
    tanggal_empty = df_all[tanggal_col].astype(str).str.strip() == "" if tanggal_col else pd.Series([True]*len(df_all))

    mask = finish_nonempty
    df_filtered = df_all.loc[mask].copy()

    # --- DEBUG TABLE A ---
    st.subheader("A. Rows with non-empty Actual Finish Packing")
    finish_nonempty = df['Actual Finish Packing'].notna() & (df['Actual Finish Packing'].astype(str).str.strip() != "")
    st.dataframe(df[finish_nonempty])
    
    # --- DEBUG TABLE B ---
    st.subheader("B. Rows with empty Tanggal Matrix")
    tanggal_empty = df['Tanggal Matrix'].isna() | (df['Tanggal Matrix'].astype(str).str.strip() == "")
    st.dataframe(df[tanggal_empty])

    if selected_db != "-- Select DB --" and "DB" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["DB"].astype(str).str.strip() == selected_db]

    if selected_vessels and "Vessel" in df_filtered.columns:
        df_filtered = df_filtered[df_filtered["Vessel"].astype(str).str.strip().isin(selected_vessels)]

    # ------------------------
    # OPTION B PATCH
    # ------------------------
    all_items = []

    for _, row in df_filtered.iterrows():
        raw = extract_picklist_candidates_from_row(row)
        if not raw:
            continue

        cleaned = (
            raw.replace("|", ",")
               .replace(";", ",")
               .replace("\n", ",")
        )

        for part in cleaned.split(","):
            part = part.strip()
            if part:
                all_items.append(part)

    # dedupe while keeping order
    seen = set()
    picklist_candidates = []
    for item in all_items:
        if item not in seen:
            seen.add(item)
            picklist_candidates.append(item)

    # numeric detection BUT strings allowed
    numeric = []
    words = []

    for x in picklist_candidates:
        # numeric-only (digit)
        if x.isdigit():
            numeric.append(x)
        else:
            words.append(x)

    numeric_sorted = sorted(numeric, key=int)

    picklist_options = numeric_sorted + words

except Exception as ex:
    st.warning(f"Could not load List All Packing for picklists: {ex}")
    picklist_options = []

selected_picklists = st.multiselect("Pick List (choose one or more)", picklist_options)

# Tujuan & Moda
tujuan = st.text_input("Tujuan")
moda = st.selectbox("Moda Pengiriman", ["-- Select Moda --"] + MODA_OPTIONS)

st.divider()

# ----------------------
# MATRIX GENERATOR
# ----------------------
if "matrix_number" not in st.session_state:
    st.session_state.matrix_number = None

st.write("Generate Nomor Matrix")
if moda == "Handcarry":
    st.session_state.matric_number = "Handcarry"
else:
    matrix_generated = st.session_state.matrix_number

if st.button("Generate Matrix Number"):
    if moda == "Handcarry":
        st.session_state.matrix_number = "Handcarry"
        st.success("Generated: Handcarry")
        st.code("Handcarry")
    else:
        try:
            df_matrix_a = load_sheet_csv_fresh(MATRIX_CSV_URL)
            df_matrix_b = load_sheet_csv_fresh(MATRIX2_CSV_URL)

            today_dt = datetime.now()
            use_date = datetime.combine(today_dt.date(), datetime.min.time())

            matrix_number = next_matrix_number_countif_multi(
                df_matrix_a, df_matrix_b,
                pic=selected_pic,
                db=selected_db if selected_db != "-- Select DB --" else "UNKNOWN",
                activity=selected_activity,
                use_date=use_date,
                seq_width=SEQ_WIDTH,
            )
            st.session_state.matrix_number = matrix_number
            st.success("Generated: " + matrix_number)
            st.code(matrix_number)
        except Exception as e:
            st.error(f"Failed to generate matrix number (fetching fresh data): {e}")

# ----------------------
# COMMIT DATA
# ----------------------
st.write("Commit Nomor Matrix dan Rencana Pengiriman")
if st.button("Commit"):
    if not st.session_state.matrix_number:
        st.error("Please generate a Matrix Number first.")
    else:
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
            payload = {
                "NOMOR MATRIX": st.session_state.matrix_number,
                "MATRIX DATE": datetime.now().strftime("%Y-%m-%d"),
                "DATABASE": selected_db,
                "Pick List No.": ";".join(selected_picklists),
                "PIC": selected_pic,
                "ACTIVITY": selected_activity.upper(),
                "Vessel Name": "-".join(selected_vessels),
                "Moda Pengiriman": moda,
                "Tujuan Pengiriman": tujuan,
            }

            st.json(payload)

            try:
                response = requests.post(WEBHOOK_URL, json=payload, timeout=20)
                if response.status_code == 200:
                    st.success(f"Committed successfully: {response.status_code}")
                    st.info(f"Payload sent to Apps Script: {WEBHOOK_URL}")
                else:
                    st.error(f"Failed to commit. Status code: {response.status_code}")
            except Exception as e:
                st.error(f"Failed to send payload: {e}")
