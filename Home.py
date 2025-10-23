import streamlit as st

import streamlit as st
from auth import check_password

if check_password():
    st.set_page_config(page_title="Warehouse Operations Suite", layout="wide")
    st.title("Welcome to the Packing Monitoring App (sementara)")
    st.write("Silahkan gunakan sidebar untuk menavigasi menu yang dituju.")
    st.write("Untuk monitoring Pick List dapat diakses di link berikut:")
    st.markdown("[Monitoring SLA Pick List](https://docs.google.com/spreadsheets/d/1YsSJSlezQHZKdY0P21Co7NxecPzrmYNCKMvbceYaLEo)")
