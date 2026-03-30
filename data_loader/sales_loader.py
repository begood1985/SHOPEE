from typing import List, Tuple

import pandas as pd

from config.settings import ESSENTIAL_COLUMNS
from utils.column_utils import find_column



def load_sales_excel(file) -> pd.DataFrame:
    file.seek(0)
    df = pd.read_excel(file, sheet_name=0, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").copy()
    return df



def validate_columns(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    missing = []
    for c in ESSENTIAL_COLUMNS:
        if find_column(df, c) is None:
            missing.append(c)
    return len(missing) == 0, missing
