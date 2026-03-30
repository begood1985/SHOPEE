import pandas as pd
from utils.column_utils import find_column

def reconcile_sales_and_receipts(sales_df: pd.DataFrame, receipts_df: pd.DataFrame) -> pd.DataFrame:
    pedido_col = find_column(sales_df, "ID do pedido")
    venda_data_col = find_column(sales_df, "Data de criação do pedido")
    
    # Base real de facturação
    subtotal_col = find_column(sales_df, "Subtotal do produto")
    valor_total_col = find_column(sales_df, "Valor Total")
    
    if pedido_col is None:
        raise ValueError("A folha de vendas não possui a coluna ID do pedido.")
    if receipts_df.empty:
        raise ValueError("Nenhum recebimento foi carregado.")

    # Taxas Cobradas pela Plataforma (O que sai)
    taxa_transacao_col = find_column(sales_df, "Taxa de transação")
    comissao_liq_col = find_column(sales_df, "Taxa de comissão líquida")
    servico_liq_col = find_column(sales_df, "Taxa de serviço líquida")
    frete_rev_col = find_column(sales_df, "Taxa de Envio Reversa")
    ajuste_acao_col = find_column(sales_df, "Ajuste por participação em ação comercial")
    
    # Cupons do Vendedor (O Desconto do Vendedor JÁ ESTÁ no Subtotal, não podemos subtrair de novo!)
    cupom_vend_col = find_column(sales_df, "Cupom do vendedor")
    
    # Adições/Incentivos da Plataforma (O que entra)
    incentivo_shopee_col = find_column(sales_df, "Incentivo Shopee para ação comercial")

    sales_df = sales_df.copy()
    sales_df[pedido_col] = sales_df[pedido_col].fillna("").astype(str).str.strip()

    cols_taxas = [c for c in [taxa_transacao_col, comissao_liq_col, servico_liq_col, frete_rev_col, ajuste_acao_col] if c]
    cols_cupons = [c for c in [cupom_vend_col] if c]
    cols_adicoes = [c for c in [incentivo_shopee_col] if c]
    
    # Conversão de segurança para evitar que valores em texto quebrem a matemática
    def safe_sum(df, cols):
        return df[cols].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) if cols else 0.0

    sales_df['_taxas_soma'] = safe_sum(sales_df, cols_taxas)
    sales_df['_cupons_vend_soma'] = safe_sum(sales_df, cols_cupons)
    sales_df['_adicoes_soma'] = safe_sum(sales_df, cols_adicoes)
    
    # APLICAÇÃO DA FÓRMULA CORRIGIDA
    if subtotal_col:
        sales_df['_base_calc'] = pd.to_numeric(sales_df[subtotal_col], errors='coerce').fillna(0)
        # FÓRMULA: Subtotal - Cupom Vendedor + Incentivos - Taxas
        sales_df['_esperado_final'] = (
            sales_df['_base_calc']
            - sales_df['_cupons_vend_soma'] 
            + sales_df['_adicoes_soma'] 
            - sales_df['_taxas_soma']
        )
        base_faturamento = subtotal_col
    else:
        bruto_col = pd.to_numeric(sales_df[valor_total_col], errors='coerce').fillna(0)
        sales_df['_esperado_final'] = bruto_col - sales_df['_taxas_soma'] - sales_df['_cupons_vend_soma']
        base_faturamento = valor_total_col

    # Agrupar Vendas
    agg_dict = {
        "valor_bruto": (base_faturamento, "sum"),
        "valor_esperado": ('_esperado_final', "sum"),
    }
    if venda_data_col:
        agg_dict["data_venda"] = (venda_data_col, "min")

    sales_summary = sales_df.groupby(pedido_col).agg(**agg_dict).reset_index().rename(columns={pedido_col: "ID do pedido"})

    # Agrupar Recebimentos
    agg_receipts = {
        "valor_recebido": ("_receipt_amount", "sum"),
        "primeiro_recebimento": ("_receipt_date", "min"),
        "ultimo_recebimento": ("_receipt_date", "max")
    }
    if "_receipt_refund_amount" in receipts_df.columns:
        agg_receipts["valor_reembolso"] = ("_receipt_refund_amount", "sum")

    receipts_summary = receipts_df.groupby("_receipt_order_id").agg(**agg_receipts).reset_index().rename(columns={"_receipt_order_id": "ID do pedido"})

    conc = sales_summary.merge(receipts_summary, on="ID do pedido", how="left")
    conc["valor_recebido"] = conc["valor_recebido"].fillna(0.0)
    
    if "valor_reembolso" in conc.columns:
        conc["valor_reembolso"] = conc["valor_reembolso"].fillna(0.0)
    else:
        conc["valor_reembolso"] = 0.0

    def classify(row):
        recebido = row["valor_recebido"]
        reembolso = row["valor_reembolso"]
        if abs(recebido) <= 0.01 and abs(reembolso) <= 0.01: 
            return "Sem lançamento"
        return "Com lançamento"

    conc["status_conciliacao"] = conc.apply(classify, axis=1)
    
    if "primeiro_recebimento" in conc.columns and "data_venda" in conc.columns:
        conc["dias_para_receber"] = (pd.to_datetime(conc["primeiro_recebimento"]) - pd.to_datetime(conc["data_venda"])).dt.days
    else:
        conc["dias_para_receber"] = pd.NA

    return conc