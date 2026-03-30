import re

import pandas as pd



def clean_money_string(value: str) -> str:
    value = str(value).strip()
    value = re.sub(r"R\$\s*", "", value)
    value = value.replace("\u00A0", "")
    value = value.replace(" ", "")
    value = value.replace("−", "-").replace("–", "-")

    if value in ["", "-", "nan", "None", "NaT"]:
        return "0"

    if "," in value:
        value = value.replace(".", "")
        value = value.replace(",", ".")

    return value



def to_number(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0.0)

    cleaned = series.astype(str).map(clean_money_string)
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0)



def brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
