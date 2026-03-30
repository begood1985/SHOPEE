import pandas as pd

from config.settings import DATE_COLUMNS, MONEY_COLUMNS
from utils.column_utils import find_column
from utils.money_utils import to_number
from utils.text_utils import normalize_text



def normalize_sales_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in MONEY_COLUMNS:
        real_col = find_column(df, col)
        if real_col:
            df[real_col] = to_number(df[real_col])

    for col in DATE_COLUMNS:
        real_col = find_column(df, col)
        if real_col:
            df[real_col] = pd.to_datetime(df[real_col], errors="coerce")

    text_cols = [
        "Status do pedido",
        "Status da Devolução / Reembolso",
        "Nome do Produto",
        "Cidade",
        "UF",
        "ID do pedido",
    ]
    for col in text_cols:
        real_col = find_column(df, col)
        if real_col:
            df[real_col] = df[real_col].fillna("").astype(str).str.strip()

    qtd_col = find_column(df, "Quantidade")
    ret_col = find_column(df, "Returned quantity")

    if qtd_col:
        df[qtd_col] = to_number(df[qtd_col])

    if ret_col:
        df[ret_col] = to_number(df[ret_col])

    data_col = find_column(df, "Data de criação do pedido")
    if data_col:
        df["Data"] = pd.to_datetime(df[data_col], errors="coerce").dt.date

    refund_col = find_column(df, "Status da Devolução / Reembolso")
    df["Pedido Devolvido?"] = False

    if refund_col:
        status_ref = df[refund_col].astype(str).str.lower()
        df["Pedido Devolvido?"] = status_ref.str.contains("reembolso|devolu", na=False)

    if ret_col:
        df["Pedido Devolvido?"] = df["Pedido Devolvido?"] | (df[ret_col] > 0)

    status_col = find_column(df, "Status do pedido")
    if status_col:
        df["_status_pedido_norm"] = df[status_col].apply(normalize_text)
    else:
        df["_status_pedido_norm"] = ""

    pedido_col = find_column(df, "ID do pedido")
    if pedido_col:
        df[pedido_col] = df[pedido_col].fillna("").astype(str).str.strip()

    return df
