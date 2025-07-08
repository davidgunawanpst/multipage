import streamlit as st

st.set_page_config(page_title="Delivery Planning", layout="wide")
st.title("Delivery Planning")

st.write("This is a placeholder for the Delivery Planning module.")
pic_list = [
  "Sendy Juniar Eka",
  "Junedi",
  "Abim Priambada"
]
db_list = [
    "DMI",
    "PKS",
    "PMT",
    "PSM",
    "PSS",
    "PST"
]
pl_list = [
  11111,
  22222,
  33333,
  44444
]

selected_pic = st.selectbox("PIC (Submitting this form):", pic_list)
selected_db = st.selectbox("Database:", db_list)
tujuan = st.text_input("Tujuan Pengiriman:")
nomor_pl = st.multiselect("Nomor Pick List Terkirim:", pl_list)

st.write("This is a placeholder for the Packing module.")
