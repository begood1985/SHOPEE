from typing import List, Tuple

import pandas as pd

from config.settings import ESSENTIAL_COLUMNS
from utils.column_utils import find_column, find_column_flexible



def load_sales_excel(file) -> pd.DataFrame:
    file.seek(0)
    df = pd.read_excel(file, sheet_name=0, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").copy()
    return df



def validate_columns(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    aliases = {
        "ID do pedido": ["ID do pedido", "Número do pedido", "Numero do pedido", "Order ID"],
        "Data de criação do pedido": ["Data de criação do pedido", "Data de criacao do pedido", "Data do pedido"],
        "Subtotal do produto": ["Subtotal do produto", "Subtotal", "Valor do produto"],
        "Taxa de transação": ["Taxa de transação", "Taxa de transacao"],
        "Taxa de comissão líquida": ["Taxa de comissão líquida", "Taxa de comissao liquida"],
        "Taxa de serviço líquida": ["Taxa de serviço líquida", "Taxa de servico liquida"],
        "Cupom do vendedor": ["Cupom do vendedor", "Cupom vendedor"],
        "Desconto do vendedor": ["Desconto do vendedor"],
    }

    missing = []
    for c in ESSENTIAL_COLUMNS:
        if find_column(df, c) is not None:
            continue
        if c in aliases and find_column_flexible(df, aliases[c]) is not None:
            continue
        if c == "Cupom Shopee":
            # Algumas exportações não trazem essa coluna sem impactar a conciliação.
            continue
        missing.append(c)
    return len(missing) == 0, missing
