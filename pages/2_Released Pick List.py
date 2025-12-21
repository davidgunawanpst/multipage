import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from io import StringIO
from auth import check_password  # your auth module
import base64

files = st.file_uploader("Upload PDF", type=["pdf"])
if files:
    pdf_bytes = files.read()
    pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    payload = {
        "pdf_data": pdf_b64,
        "pdf_filename": files.name
    }

    resp = requests.post(
        "YOUR_WEBHOOK_URL",
        json=payload,
    )

    st.json(resp.json())

