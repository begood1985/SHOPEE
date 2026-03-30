import pandas as pd

from utils.column_utils import find_column



def reconcile_sales_and_receipts(sales_df: pd.DataFrame, receipts_df: pd.DataFrame) -> pd.DataFrame:
    pedido_col = find_column(sales_df, "ID do pedido")
    venda_data_col = find_column(sales_df, "Data de criação do pedido")
    valor_total_col = find_column(sales_df, "Valor Total")
    total_global_col = find_column(sales_df, "Total global")

    if pedido_col is None:
        raise ValueError("A planilha de vendas não possui a coluna ID do pedido.")

    if receipts_df.empty:
        raise ValueError("Nenhum recebimento foi carregado.")

    if total_global_col:
        expected_col = total_global_col
    elif valor_total_col:
        expected_col = valor_total_col
    else:
        raise ValueError("A planilha de vendas não possui Total global nem Valor Total.")

    sales_df = sales_df.copy()
    sales_df[pedido_col] = sales_df[pedido_col].fillna("").astype(str).str.strip()

    agg_dict = {
        "valor_vendido": (valor_total_col, "sum") if valor_total_col else (pedido_col, "size"),
        "valor_esperado": (expected_col, "sum"),
    }

    if venda_data_col:
        agg_dict["data_venda"] = (venda_data_col, "min")

    sales_summary = (
        sales_df.groupby(pedido_col, dropna=False)
        .agg(**agg_dict)
        .reset_index()
        .rename(columns={pedido_col: "ID do pedido"})
    )

    receipts_summary = (
        receipts_df.groupby("_receipt_order_id", dropna=False)
        .agg(
            valor_recebido=("_receipt_amount", "sum"),
            qtd_lancamentos=("_receipt_amount", "size"),
            primeiro_recebimento=("_receipt_date", "min"),
            ultimo_recebimento=("_receipt_date", "max"),
            arquivos_origem=(
                "_receipt_source_file",
                lambda s: ", ".join(sorted(set([x for x in s if str(x).strip()])))
            ),
            abas_origem=(
                "_receipt_source_sheet",
                lambda s: ", ".join(sorted(set([x for x in s if str(x).strip()])))
            ),
        )
        .reset_index()
        .rename(columns={"_receipt_order_id": "ID do pedido"})
    )

    conc = sales_summary.merge(receipts_summary, on="ID do pedido", how="left")

    conc["valor_recebido"] = conc["valor_recebido"].fillna(0.0)
    conc["qtd_lancamentos"] = conc["qtd_lancamentos"].fillna(0).astype(int)
    conc["arquivos_origem"] = conc["arquivos_origem"].fillna("")
    conc["abas_origem"] = conc["abas_origem"].fillna("")
    conc["diferenca"] = conc["valor_recebido"] - conc["valor_esperado"]

    tolerancia = 0.01

    def classify(row):
        esperado = row["valor_esperado"]
        recebido = row["valor_recebido"]
        diff = row["diferenca"]

        if abs(recebido) <= tolerancia:
            return "Não recebido"
        if abs(diff) <= tolerancia:
            return "Recebido integralmente"
        if 0 < recebido < esperado:
            return "Recebido parcialmente"
        if recebido > esperado:
            return "Recebido a maior"
        if recebido < 0:
            return "Líquido negativo"
        return "Em análise"

    conc["status_conciliacao"] = conc.apply(classify, axis=1)

    if "primeiro_recebimento" in conc.columns and "data_venda" in conc.columns:
        conc["dias_para_receber"] = (
            pd.to_datetime(conc["primeiro_recebimento"], errors="coerce")
            - pd.to_datetime(conc["data_venda"], errors="coerce")
        ).dt.days
    else:
        conc["dias_para_receber"] = pd.NA

    return conc
