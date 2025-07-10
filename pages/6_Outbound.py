import streamlit as st
from datetime import date

st.set_page_config(page_title="Outbound", layout="wide")
st.title("Outbound Monitoring")

st.write("This is a placeholder for the Delivery Planning module.")
pic_list = [
  "PIC 1",
  "PIC 2"
]
db_list = [
    "DMI",
    "PBN",
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
