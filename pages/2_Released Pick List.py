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
