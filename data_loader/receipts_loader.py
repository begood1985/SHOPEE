from typing import List

import pandas as pd
import streamlit as st

from utils.column_utils import pick_first_existing_column
from utils.money_utils import to_number
from utils.text_utils import normalize_header_name



def get_first_sheet_name(file) -> str:
    file.seek(0)
    xls = pd.ExcelFile(file, engine="openpyxl")
    if not xls.sheet_names:
        raise ValueError("O arquivo de recebimento não possui abas.")
    return xls.sheet_names[0]



def score_receipt_header_row(row_values: List[str]) -> int:
    row_text = " | ".join([normalize_header_name(x) for x in row_values])

    score = 0

    if "id do pedido" in row_text or "numero do pedido" in row_text or "order id" in row_text:
        score += 5

    if "quantia total lancada" in row_text:
        score += 5
    elif "quantia total" in row_text and "lancada" in row_text:
        score += 4

    if "data de conclusao do pagamento" in row_text:
        score += 5
    elif "conclusao do pagamento" in row_text:
        score += 4
    elif "data de pagamento" in row_text:
        score += 3

    return score



def detect_header_row_receipts(raw: pd.DataFrame, max_scan_rows: int = 15) -> int | None:
    scan_limit = min(len(raw), max_scan_rows)
    best_idx = None
    best_score = -1

    for i in range(scan_limit):
        row_values = raw.iloc[i].fillna("").astype(str).tolist()
        score = score_receipt_header_row(row_values)
        if score > best_score:
            best_score = score
            best_idx = i

    if best_score >= 8:
        return best_idx
    return None



def find_receipt_id_column(df: pd.DataFrame) -> str | None:
    candidates = [
        "ID do pedido",
        "Numero do pedido",
        "Número do pedido",
        "Order ID",
    ]
    col = pick_first_existing_column(df, candidates)
    if col:
        return col

    for real_col in df.columns:
        norm = normalize_header_name(real_col)
        if "id" in norm and "pedido" in norm:
            return real_col
        if "order" in norm and "id" in norm:
            return real_col
    return None



def find_receipt_amount_column(df: pd.DataFrame) -> str | None:
    candidates = [
        "Quantia total lançada (R$)",
        "Quantia total lançada",
        "Quantia total",
        "Total lançado",
    ]
    col = pick_first_existing_column(df, candidates)
    if col:
        return col

    for real_col in df.columns:
        norm = normalize_header_name(real_col)
        if "quantia" in norm and "total" in norm and "lanc" in norm:
            return real_col
        if "total" in norm and "lanc" in norm:
            return real_col
    return None



def find_receipt_date_column(df: pd.DataFrame) -> str | None:
    candidates = [
        "Data de conclusão do pagamento",
        "Data conclusão do pagamento",
        "Data de pagamento",
        "Data pagamento",
    ]
    col = pick_first_existing_column(df, candidates)
    if col:
        return col

    for real_col in df.columns:
        norm = normalize_header_name(real_col)
        if "data" in norm and "pagamento" in norm and "conclus" in norm:
            return real_col
        if "data" in norm and "pagamento" in norm:
            return real_col
    return None


def find_receipt_refund_column(df: pd.DataFrame) -> str | None:
    candidates = [
        "Valor do Reembolso",
        "Valor de Reembolso",
        "Refund Amount",
    ]
    col = pick_first_existing_column(df, candidates)
    if col:
        return col

    for real_col in df.columns:
        norm = normalize_header_name(real_col)
        if "valor" in norm and "reembolso" in norm:
            return real_col
    return None


def load_receipt_sheet_organized(file, source_name: str | None = None) -> pd.DataFrame:
    selected_sheet = get_first_sheet_name(file)

    file.seek(0)
    raw = pd.read_excel(
        file,
        sheet_name=selected_sheet,
        header=None,
        dtype=str,
        engine="openpyxl",
    ).dropna(how="all").copy()

    if raw.empty:
        raise ValueError(f"A aba '{selected_sheet}' do arquivo '{source_name or 'recebimentos'}' está vazia.")

    header_row_idx = detect_header_row_receipts(raw)

    if header_row_idx is None:
        raise ValueError(
            f"Não consegui localizar o cabeçalho da aba '{selected_sheet}' no arquivo "
            f"'{source_name or 'recebimentos'}'."
        )

    file.seek(0)
    df = pd.read_excel(
        file,
        sheet_name=selected_sheet,
        header=header_row_idx,
        dtype=str,
        engine="openpyxl",
    )

    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").copy()

    total_linhas_brutas = len(df)

    order_col = find_receipt_id_column(df)
    amount_col = find_receipt_amount_column(df)
    date_col = find_receipt_date_column(df)
    refund_col = find_receipt_refund_column(df)

    if not order_col or not amount_col or not date_col:
        raise ValueError(
            f"A aba '{selected_sheet}' do arquivo '{source_name or 'recebimentos'}' não possui "
            f"as colunas mínimas necessárias. Colunas encontradas: {list(df.columns)}"
        )

    cols_to_keep = [order_col, amount_col, date_col]
    if refund_col:
        cols_to_keep.append(refund_col)

    df = df[cols_to_keep].copy()

    rename_map = {
        order_col: "_receipt_order_id",
        amount_col: "_receipt_amount",
        date_col: "_receipt_date",
    }
    if refund_col:
        rename_map[refund_col] = "_receipt_refund_amount"

    df = df.rename(columns=rename_map)

    df["_receipt_order_id"] = df["_receipt_order_id"].fillna("").astype(str).str.strip()
    df["_receipt_amount"] = to_number(df["_receipt_amount"])
    df["_receipt_date"] = pd.to_datetime(df["_receipt_date"], errors="coerce")
    
    if "_receipt_refund_amount" in df.columns:
        df["_receipt_refund_amount"] = to_number(df["_receipt_refund_amount"])
        
    df["_receipt_source_file"] = source_name or ""
    df["_receipt_source_sheet"] = selected_sheet

    before_filter = len(df)
    df = df[df["_receipt_order_id"] != ""].copy()
    after_filter = len(df)

    st.info(
        f"Arquivo '{source_name or 'recebimentos'}' | Aba '{selected_sheet}' | "
        f"Cabeçalho detectado na linha {header_row_idx + 1} | "
        f"Linhas lidas: {total_linhas_brutas:,} | "
        f"Linhas com ID válido: {after_filter:,} | "
        f"Descartadas sem ID: {before_filter - after_filter:,}"
    )

    return df



def load_multiple_receipts(files) -> pd.DataFrame:
    frames = []

    progress_bar = st.progress(0, text="Iniciando carregamento dos recebimentos...")
    status_box = st.empty()

    total_files = len(files)

    for idx, file in enumerate(files, start=1):
        file_name = getattr(file, "name", f"arquivo_{idx}")
        status_box.info(f"Processando arquivo {idx}/{total_files}: {file_name}")

        df = load_receipt_sheet_organized(file=file, source_name=file_name)
        frames.append(df)

        progress = int((idx / total_files) * 100)
        progress_bar.progress(progress, text=f"Carregando recebimentos... {idx}/{total_files} arquivo(s)")

    status_box.success("Carregamento dos recebimentos concluído.")

    if not frames:
        progress_bar.progress(100, text="Nenhum recebimento encontrado.")
        return pd.DataFrame(columns=[
            "_receipt_order_id",
            "_receipt_amount",
            "_receipt_date",
            "_receipt_refund_amount",
            "_receipt_source_file",
            "_receipt_source_sheet",
        ])

    receipts_df = pd.concat(frames, ignore_index=True)

    progress_bar.progress(100, text=f"Recebimentos carregados com sucesso: {len(receipts_df):,} linhas.")
    st.success(f"Total consolidado de recebimentos carregados: {len(receipts_df):,} linhas.")

    return receipts_df