def next_matrix_number_countif_multi(df_list: list, pic: str, db: str, activity: str, use_date: datetime | None = None, seq_width: int = SEQ_WIDTH) -> str:
    """
    Count exact occurrences of PIC across multiple dataframes (list of df_matrix),
    then next_seq = total count + 1 → next sequence number.
    """
    if use_date is None:
        use_date = datetime.now()
    month_rom = _ROMAN.get(use_date.month, str(use_date.month))
    year = use_date.year

    total_count = 0

    for df_matrix in df_list:
        if df_matrix is None or df_matrix.empty:
            continue
        # detect PIC column name (case-insensitive)
        pic_col = next((c for c in df_matrix.columns if c.strip().lower() == "pic"), None)
        if pic_col is None:
            continue
        try:
            # exact match count
            total_count += int((df_matrix[pic_col] == pic).sum())
        except Exception:
            continue

    next_seq = total_count + 1
    seq_str = str(next_seq).zfill(seq_width)

    # PIC short name for final string
    pic_short = PIC_SHORTNAME.get(pic, str(pic).replace(" ", ""))

    # activity token: Delivery -> DEL else OTHER
    token = "DEL" if str(activity).strip().lower() == "delivery" else "OTHER"

    db_for_str = str(db).strip().upper()

    matrix_str = f"MATRIX - {seq_str}-{token}-{pic_short}-{db_for_str}-{month_rom}-{year}"
    return matrix_str
