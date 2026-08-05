# app.py
import streamlit as st
import pandas as pd
import requests
from io import StringIO
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# optional auth hook (if you have auth.py); fallback to allow all
try:
    from auth import check_password
except Exception:
    def check_password():
        return True

# -----------------------
# CONFIG (edit as needed)
# -----------------------
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwKTmWWaNcyZ6AQJwd6zJp6IPoNII_nE7AO46DTSYTpDLEVF9H2e5AFdYI6mF_hvBtF/exec"  # <- replace with your Apps Script URL
SHEET_ID = "1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo"
SHEET_NAME = "Finish Packing Detail"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"

DB_LIST = ["DMI", "PBN", "PKS", "PMT", "PSS", "PSM", "PST"]

# -----------------------
# Ship list (fleet routing derived from prefix)
# -----------------------
SHIP_LIST = [
    "TB: Pancaran 210", "TB: Pancaran 211", "TB: Pancaran 212", "TB: Pancaran 312",
    "TB: Pancaran 512", "TB: Pancaran 612", "TB: Pancaran 712", "BG: PST 110",
    "BG: PST 210", "BG: PST 211", "BG: PST 212", "BG: PST 312", "BG: PST 512",
    "BG: PST 712", "BG : KALTIM FT 36-09", "BG : KALTIM FT 50-01", "BG : KALTIM FT 50-02",
    "TB: Pancaran 113", "TB: Pancaran 213", "TB: Pancaran 313", "TB: Pancaran 513",
    "TB: Pancaran 613", "TB: Pancaran 713", "BG: PST 113", "BG: PST 213", "BG: PST 313",
    "BG : PST 513", "BG : PST 613", "BG : PST 713", "TB : Pancaran 215", "BG : PST 215",
    "TB: Pancaran 812", "TB: Pancaran 912", "TB: Pancaran 1212", "TB: Pancaran 1312",
    "TB : Michelle 219-01", "TB : Pancaran 813", "BG: PST 812", "BG: PST 912",
    "BG: PST 1212", "BG: PST 1312", "BG : Angeline 219-01", "BG : PST 813",
    "TB: Pancaran 115", "BG : PST 115", "TB : KALTIM DOLPHIN 10-10", "TB : KALTIM DOLPHIN 10-13",
    "TB : Pancaran 315", "BG : PST 315", "TB : KALTIM DOLPHIN 10-07", "TB : KALTIM DOLPHIN 10-15",
    "TB : KALTIM DOLPHIN 12-01", "BG: PST 1111", "TB: Pancaran 111", "TB: Pancaran 311",
    "TB: Pancaran 611", "BG: PST 610", "BG: PST 611", "TB : PERSADA XIII", "TB. Sorowako Star",
    "TB: Pancaran 122", "TB: Pancaran 222", "TB. Pancaran 511", "TB. Persada XI",
    "TB : Pancaran IV-115", "TB : Pancaran III-215", "TB : Pancaran IV-315", "TB : Pancaran III-515",
    "TB : Pancaran III-615", "TB : Pancaran III-715", "TB : Pancaran III-815",
    "Oil Barge : PMT III-215", "Oil Barge : PMT IV-315", "Oil Barge : PMT III-515",
    "Oil Barge : PMT III-615", "Oil Barge : PMT III-715", "Oil Barge : PMT III-815",
    "Oil Barge: PMT XLV 1015", "Oil Barge : PMT III-105", "Oil Barge : PMT II 1615",
    "Oil Barge : ROYAL 8", "Oil Barge : ROYAL 9", "Oil Barge : ROYAL 15", "Oil Barge : ROYAL 27",
    "TB : PANCARAN II 1615", "TB : ROYAL TB 8", "TB : ROYAL TB 9", "TB : ROYAL TB 15",
    "TB : ROYAL TB 27", "Oil Barge : ROYAL 1", "Oil Barge : PMT II 1815", "Oil Barge : ROYAL 17",
    "TB : ROYAL TB 1", "TB : PANCARAN II 1815", "TB : ROYAL TB 17", "TB : Pancaran XLV 1115",
    "TB : Pancaran XLV 1215", "Oil Barge: PMT XLV 1115", "Oil Barge: PMT XLV 1215",
    "Oil Barge : Pancaran 9113", "TB : KALTIM DOLPHIN 10-14", "Oil Barge : PMT IV-110",
    "TB : Pancaran 118", "TB : KALTIM DOLPHIN 17-04", "MT Pancaran 120", "MT Pancaran Integrity",
    "MT Pancaran Nusantara", "MT Maritim Indonesia", "MT Maritim Nusantara", "MT Maritim Khatulistiwa",
    "MT Maritim Cakrawala", "MT Pancaran Khatulistiwa", "MT Pancaran Agility", "MT Pancaran Prosperity",
    "MT Pancaran Infinity", "AHTS Triton Arjuna", "MV Pancaran Liberty", "MV Pancaran I 5505",
    "MV Pancaran Glory", "MV Pancaran Victory", "General Vessel", "TB Pancaran 9125",
    "TB Pancaran 7125", "TB Pancaran 7225", "BG PST 925", "BG PST 1025", "BG PST 1125",
    "BG PST 125", "BG PST 225", "OB PMT 9125", "OB PMT 7125", "OB PMT 7225", "BG PST 325",
    "Pancaran Cakrawala", "MT PAL 242", "MT Pancaran Legacy", "MT PAL 259", "TB TKSI 7",
    "TB TKSI I", "TB TKSI II", "TB TKSI 9", "TB TKSI 10", "TB TKSI XII", "TB TKSI 15",
    "BG AME II", "BG AME III", "BG AME IV", "BG AME VI", "BG AME VII", "BG AME 8", "BG AME IX",
    "BG AME X", "TB TKSI 6", "TB TKSI 16", "BG PMT 815", "TB PANCARAN 1125", "WORKSHOP BATAM",
    "WH GALANGAN SAMARINDA", "Tb. Royal TB 9", "MT Pancaran Spirit", "MT Pancaran Harmony",
]

# -----------------------
# City list (Tujuan)
# -----------------------
CITY_LIST = [
    "Aceh Barat Daya", "Aceh Besar", "Kota Lhokseumawe", "Kota Sabang", "Buleleng",
    "Karangasem", "Kota Denpasar", "Kota Cilegon", "Lebak", "Kota Bengkulu", "Kota Gorontalo",
    "Kota Jambi", "Cirebon", "Indramayu", "Subang", "Cilacap", "Kota Semarang", "Bangkalan",
    "Banyuwangi", "Gresik", "Kota Probolinggo", "Kota Surabaya", "Situbondo", "Sumenep",
    "Tuban", "Kayong Utara", "Ketapang", "Kota Pontianak", "Kota Banjarmasin", "Kotabaru",
    "Tanah Bumbu", "Kotawaringin Barat", "Kotawaringin Timur", "Balikpapan", "Kota Bontang",
    "Samarinda", "Kutai Kartanegara", "Kutai Timur", "Bulungan", "Kota Tarakan", "Bangka Barat",
    "Belitung", "Belitung Timur", "Kota Pangkal Pinang", "Bintan", "Karimun", "Batam",
    "Kota Tanjung Pinang", "Kota Bandar Lampung", "Tanggamus", "Halmahera Selatan", "Kota Ternate",
    "Kota Ambon", "Kota Bima", "Sumbawa Barat", "Kupang", "Kota Sorong", "Sorong", "Fak Fak",
    "Manokwari", "Mimika", "Biak Numfor", "Kota Jayapura", "Indragiri Hilir", "Kota Dumai",
    "Kota Pekanbaru", "Siak", "Kota Makassar", "Kota Pare Pare", "Pangkajene Kepulauan",
    "Banggai", "Kota Palu", "Poso", "Kolaka", "Kota Kendari", "Kota Bitung", "Kota Manado",
    "Kota Padang", "Kota Palembang", "Batu Bara", "Kota Medan", "Kota Tanjung Balai", "Langkat",
    "OB Balikpapan", "Padang OB", "Lampung OB", "Lampung", "Tanjung Uban", "OB Banyuwangi",
    "OB Pulau Bunyu", "OB lampung", "OB Paiton", "GSB Batam", "Kendari", "Kabil", "KRN Balikpapan",
    "Jakarta Utara", "Tambatan Jingga", "Muara Jawa", "Kijing", "Jetty KRN", "Pelabuhan Bitung",
    "Bali", "Lamongan", "Pelabuhan Belawan", "Tanjung Pandan", "Bagendang - Sampit", "Berau",
    "Kolonodale", "OB Tj Merpati", "SAMARINDA", "IBT Pulau Laut", "Mantuil",
    "Pasar Pagi,Sanga-Sanga,Balik Buaya", "Passing Trisakti", "Pelabuhan Lampung",
    "Laut Banyuwangi", "OB Melabouh", "Bahodopi", "Kota Samarinda", "OB Padang", "OB Plaju",
    "pelabuhan belawan", "Pelintung", "OB Muara Jawa", "Stagen", "AKR Stagen", "Batulicin",
    "Aceh", "Palembang", "OB Lampung", "OB Batam",
]

# -----------------------
# Helpers
# -----------------------
def load_sheet_csv(url: str) -> pd.DataFrame:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text), dtype=object)

def clean_candidate(val):
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val).strip()
    if isinstance(val, int):
        return str(val)
    s = str(val).strip()
    if s.lower() in {"", "nan", "none", "na"}:
        return None
    return s

def get_available_picks(df: pd.DataFrame, selected_db: str) -> list:
    df = df.copy()
    df.columns = df.columns.str.strip()
    required = {"DB", "Pick List Number"}
    if not required.issubset(set(df.columns)):
        missing = required - set(df.columns)
        raise ValueError(f"Sheet missing required columns: {missing}")

    df["DB"] = df["DB"].astype(str).str.strip()
    filtered = df[df["DB"] == selected_db].copy()

    picks = []
    for _, row in filtered.iterrows():
        candidate = clean_candidate(row.get("Pick List Number", None))
        if candidate:
            picks.append(candidate)

    seen = set()
    ordered = []
    for p in picks:
        if p not in seen:
            seen.add(p)
            ordered.append(p)

    digits = [x for x in ordered if str(x).isdigit()]
    nondigits = [x for x in ordered if not str(x).isdigit()]
    digits_sorted = sorted(digits, key=lambda s: int(s))
    return digits_sorted + nondigits

def fleet_for_ship(ship: str) -> str:
    """Return 'TBBG', 'MTMV', or 'BOTH' based on ship name prefix."""
    s = ship.strip().upper().replace(".", " ").replace(":", " ")
    tokens = s.split()
    prefix = tokens[0] if tokens else ""
    if s.startswith("OIL BARGE"):
        return "TBBG"
    if s.startswith("AHTS") or s.startswith("PANCARAN CAKRAWALA"):
        return "MTMV"
    if prefix in {"TB", "BG", "OB"}:
        return "TBBG"
    if prefix in {"MT", "MV"}:
        return "MTMV"
    return "BOTH"

# -----------------------
# UI
# -----------------------
if check_password():
    st.set_page_config(page_title="Outbound", layout="wide")
    st.title("Outbound")

    # Nomor Matrix (free text)
    nomor_matrix = st.text_input("Nomor Matrix:")

    # Nama Kapal
    nama_kapal = st.selectbox("Nama Kapal:", SHIP_LIST)

    # DB select
    selected_db = st.selectbox("Database (DB):", DB_LIST)

    # Pick List selection from sheet
    with st.spinner("Loading pick lists..."):
        try:
            df_sheet = load_sheet_csv(CSV_URL)
            available_picks = get_available_picks(df_sheet, selected_db)
        except Exception as e:
            st.error(f"Failed to load sheet or parse picks: {e}")
            available_picks = []

    if not available_picks:
        st.warning("No available Pick Lists for this Database.")
        pick_numbers = st.multiselect("Pick List Number(s):", [])
    else:
        pick_numbers = st.multiselect("Pick List Number(s):", available_picks)

    # Tujuan
    tujuan = st.selectbox("Tujuan:", CITY_LIST)

    # Matrix dibuat kapan
    matrix_date = st.date_input("Matrix dibuat kapan:")

    # Actual Outbound
    actual_outbound = st.date_input("Actual Outbound:")

    # Leadtime (free text, days)
    leadtime_str = st.text_input("Leadtime (hari):")

    # Estimasi ketibaan = Actual Outbound + Leadtime
    estimasi = None
    if leadtime_str.strip():
        try:
            estimasi = actual_outbound + timedelta(days=int(leadtime_str.strip()))
            st.info(f"Estimasi Ketibaan: **{estimasi.isoformat()}**")
        except ValueError:
            st.warning("Leadtime harus berupa angka (hari).")

    # Submit
    if st.button("✅ Submit"):
        if not nomor_matrix.strip():
            st.warning("Please fill Nomor Matrix.")
            st.stop()
        if not nama_kapal:
            st.warning("Please select Nama Kapal.")
            st.stop()
        if not selected_db:
            st.warning("Please select a Database.")
            st.stop()
        if not pick_numbers:
            st.warning("Please select at least one Pick List number.")
            st.stop()
        if not tujuan:
            st.warning("Please select Tujuan.")
            st.stop()
        if not leadtime_str.strip() or estimasi is None:
            st.warning("Please fill a valid Leadtime (angka hari).")
            st.stop()

        fleet = fleet_for_ship(nama_kapal)

        payload = {
            "timestamp": datetime.now(ZoneInfo("Asia/Jakarta")).isoformat(),
            "nomor_matrix": nomor_matrix.strip(),
            "nama_kapal": nama_kapal,
            "DB": selected_db,
            "pick_lists": pick_numbers,
            "tujuan": tujuan,
            "matrix_date": matrix_date.isoformat(),
            "actual_outbound": actual_outbound.isoformat(),
            "leadtime": int(leadtime_str.strip()),
            "estimasi_ketibaan": estimasi.isoformat(),
            "fleet": fleet,
        }

        try:
            resp = requests.post(APPS_SCRIPT_URL, json=payload, timeout=60)
            if resp.status_code in (200, 201):
                st.success("✅ Submission successful.")
                try:
                    st.json(resp.json())
                except Exception:
                    st.write("Server response (non-JSON):")
                    st.write(resp.text)
            else:
                st.error(f"Server returned {resp.status_code}: {resp.text[:1000]}")
        except Exception as e:
            st.error(f"Failed to send payload: {e}")
