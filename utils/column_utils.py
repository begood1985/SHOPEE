from typing import List

import pandas as pd

from utils.text_utils import normalize_header_name, normalize_text



def find_column(df: pd.DataFrame, target: str) -> str | None:
    target_norm = normalize_text(target)
    for col in df.columns:
        if normalize_text(col) == target_norm:
            return col
    return None



def find_column_flexible(df: pd.DataFrame, possibilities: List[str]) -> str | None:
    norm_map = {col: normalize_header_name(col) for col in df.columns}

    for wanted in possibilities:
        wanted_norm = normalize_header_name(wanted)
        for real_col, norm_col in norm_map.items():
            if norm_col == wanted_norm:
                return real_col

    for wanted in possibilities:
        wanted_norm = normalize_header_name(wanted)
        for real_col, norm_col in norm_map.items():
            if wanted_norm in norm_col or norm_col in wanted_norm:
                return real_col

    return None



def pick_first_existing_column(df: pd.DataFrame, candidates: List[str]) -> str | None:
    for candidate in candidates:
        col = find_column_flexible(df, [candidate])
        if col:
            return col
    return None
