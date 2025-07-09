# Load CSV from Google Sheets
@st.cache_data
def load_data():
    return pd.read_csv(CSV_URL)

df = load_data()

# Handle column renaming if needed
df.columns = df.columns.str.strip()
if "Nama Perusahaan" not in df.columns or "Pick Number" not in df.columns:
    st.error("❌ Required columns not found in the sheet!")
    st.stop()

# Set page config and title
st.set_page_config(page_title="Packing", layout="wide")
st.title("📦 Packing Module")

# 1. PIC Name (Static)
pic_list = [
    "Rikie Dwi Permana", "Idha Akhmad Sucahyo", "Rian Dinata",
    "Harimurti Krisandki", "Muchamad Mustofa", "Yogie Arie Wibowo"
]
selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)

# 2. Database (Nama Perusahaan)
db_options = sorted(df["Nama Perusahaan"].dropna().unique())
selected_db = st.selectbox("Database (Nama Perusahaan):", db_options)

# 3. Pick List (filtered)
filtered_df = df[df["Nama Perusahaan"] == selected_db]
pl_options = sorted(filtered_df["Pick Number"].dropna().unique())
selected_pl = st.selectbox("Pick List Number:", pl_options)

# 4. Upload Pictures
uploaded_files = st.file_uploader("Upload photos (unlimited):", accept_multiple_files=True, type=["jpg", "jpeg", "png"])

# 5. Submit Button
if st.button("✅ Packed"):
    if not selected_pl:
        st.warning("Please select a Pick List Number.")
    elif not uploaded_files:
        st.warning("Please upload at least one photo.")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        images_base64 = []

        for file in uploaded_files:
            b64 = base64.b64encode(file.read()).decode()
            images_base64.append({
                "filename": file.name,
                "content": b64
            })

        payload = {
            "timestamp": timestamp,
            "database": selected_db,
            "pic": selected_pic,
            "pick_list": selected_pl,
            "photos": images_base64
        }

        # Replace with your actual Apps Script Webhook URL
        webhook_url = "https://script.google.com/macros/s/YOUR_WEBAPP_ID/exec"
        response = requests.post(webhook_url, json=payload)

        if response.status_code == 200:
            result = response.json()
            st.success("✅ Packed data submitted successfully!")
            st.markdown(f"📁 [View uploaded folder]({result.get('drive_folder_url')})")
        else:
            st.error(f"❌ Failed to submit data. Error: {response.text}")
