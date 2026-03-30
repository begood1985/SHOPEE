import re
import unicodedata

import pandas as pd


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    value = str(value).strip().lower()
    value = value.replace("\u00A0", " ")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"\s+", " ", value).strip()
    return value



def normalize_header_name(col: str) -> str:
    col = normalize_text(col)
    col = re.sub(r"[^a-z0-9]+", " ", col).strip()
    col = re.sub(r"\s+", " ", col)
    return col
