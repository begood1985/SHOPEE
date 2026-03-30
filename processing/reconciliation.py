import pandas as pd
from utils.column_utils import find_column

def reconcile_sales_and_receipts(sales_df: pd.DataFrame, receipts_df: pd.DataFrame) -> pd.DataFrame:
    """Concilia vendas e recebimentos com tolerância a arredondamentos."""
    pedido_col = find_column(sales_df, "ID do pedido")
    venda_data_col = find_column(sales_df, "Data de criação do pedido")
    bruto_col = find_column(sales_df, "Valor Total")
    total_global_col = find_column(sales_df, "Total global")
    
    if pedido_col is None:
        raise ValueError("A planilha de vendas não possui a coluna ID do pedido.")
    if receipts_df.empty:
        raise ValueError("Nenhum recebimento foi carregado.")

    sales_df = sales_df.copy()
    sales_df[pedido_col] = sales_df[pedido_col].fillna("").astype(str).str.strip()

    # CORREÇÃO: Definir o valor esperado por pedido de forma robusta
    if total_global_col:
        sales_df['_esperado_final'] = sales_df[total_global_col]
    else:
        # Fallback manual: Bruto - Taxas (Descontos vendedor já costumam estar fora do Valor Total)
        taxa_transacao_col = find_column(sales_df, "Taxa de transação")
        comissao_liq_col = find_column(sales_df, "Taxa de comissão líquida")
        servico_liq_col = find_column(sales_df, "Taxa de serviço líquida")
        frete_rev_col = find_column(sales_df, "Taxa de Envio Reversa")
        
        cols_taxas = [c for c in [taxa_transacao_col, comissao_liq_col, servico_liq_col, frete_rev_col] if c]
        sales_df['_taxas_soma'] = sales_df[cols_taxas].sum(axis=1) if cols_taxas else 0.0
        sales_df['_esperado_final'] = sales_df[bruto_col] - sales_df['_taxas_soma']

    # Agrupar Vendas
    agg_dict = {
        "valor_bruto": (bruto_col, "sum"),
        "valor_esperado": ('_esperado_final', "sum"),
    }
    if venda_data_col:
        agg_dict["data_venda"] = (venda_data_col, "min")

    sales_summary = sales_df.groupby(pedido_col).agg(**agg_dict).reset_index().rename(columns={pedido_col: "ID do pedido"})

    # Agrupar Recebimentos
    receipts_summary = receipts_df.groupby("_receipt_order_id").agg(
        valor_recebido=("_receipt_amount", "sum"),
        primeiro_recebimento=("_receipt_date", "min"),
        ultimo_recebimento=("_receipt_date", "max")
    ).reset_index().rename(columns={"_receipt_order_id": "ID do pedido"})

    # Cruzamento
    conc = sales_summary.merge(receipts_summary, on="ID do pedido", how="left")
    conc["valor_recebido"] = conc["valor_recebido"].fillna(0.0)
    conc["diferenca"] = conc["valor_recebido"] - conc["valor_esperado"]

    # CORREÇÃO: Classificação com margem de tolerância (0.10 centavos)
    def classify(row):
        esperado = row["valor_esperado"]
        recebido = row["valor_recebido"]
        diff = row["diferenca"]
        
        if abs(recebido) <= 0.01: return "Não recebido"
        if abs(diff) <= 0.10: return "Recebido integralmente"
        if diff < -0.10:
            if recebido < (esperado * 0.7): return "Divergência Crítica (Subpago)"
            return "Recebido parcialmente"
        return "Recebido a maior"

    conc["status_conciliacao"] = conc.apply(classify, axis=1)
    
    if "primeiro_recebimento" in conc.columns and "data_venda" in conc.columns:
        conc["dias_para_receber"] = (pd.to_datetime(conc["primeiro_recebimento"]) - pd.to_datetime(conc["data_venda"])).dt.days
    else:
        conc["dias_para_receber"] = pd.NA

    return conc