import streamlit as st

st.set_page_config(page_title="Packing", layout="wide")
st.title("Packing")
pic_list = [
    "Rikie Dwi Permana",
    "Idha Akhmad Sucahyo",
    "Rian Dinata",
    "Harimurti Krisandki",
    "Muchamad Mustofa",
    "Yogie Arie Wibowo"
]
db_list = [
    "DMI",
    "PKS",
    "PMT",
    "PSM",
    "PSS",
    "PST"
]
selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
selected_db = st.selectbox("Database:", db_list)
nomor_pl = st.number_input("Nomor Pick List:", min_value=0, step=1)
uploaded_files = st.file_uploader("Upload photos (unlimited):", accept_multiple_files=True, type=["jpg", "jpeg", "png"])


st.write("This is a placeholder for the Packing module.")
