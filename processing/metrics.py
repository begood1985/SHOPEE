import pandas as pd
from typing import Dict
from utils.column_utils import find_column

def safe_sum_cols(df, cols):
    """Função de segurança para garantir cálculo numérico exacto nas colunas"""
    return df[cols].apply(pd.to_numeric, errors='coerce').fillna(0).sum().sum() if cols else 0.0

def calculate_metrics(df: pd.DataFrame) -> Dict[str, float]:
    pedido_col = find_column(df, "ID do pedido")
    valor_total_col = find_column(df, "Valor Total")
    subtotal_col = find_column(df, "Subtotal do produto")
    qtd_col = find_column(df, "Quantidade")
    ret_col = find_column(df, "Returned quantity")

    # Taxas
    taxa_transacao_col = find_column(df, "Taxa de transação")
    comissao_liquida_col = find_column(df, "Taxa de comissão líquida")
    servico_liquida_col = find_column(df, "Taxa de serviço líquida")
    frete_reverso_col = find_column(df, "Taxa de Envio Reversa")
    ajuste_acao_col = find_column(df, "Ajuste por participação em ação comercial")
    
    # Descontos e Adições
    desconto_vendedor_col = find_column(df, "Desconto do vendedor") 
    cupom_vendedor_col = find_column(df, "Cupom do vendedor")
    incentivo_shopee_col = find_column(df, "Incentivo Shopee para ação comercial")

    # Base correta: Subtotal 
    base_faturamento_col = subtotal_col if subtotal_col else valor_total_col
    total_bruto = pd.to_numeric(df[base_faturamento_col], errors='coerce').fillna(0).sum() if base_faturamento_col else 0.0
    
    cols_taxas = [c for c in [taxa_transacao_col, comissao_liquida_col, servico_liquida_col, frete_reverso_col, ajuste_acao_col] if c]
    total_taxas = safe_sum_cols(df, cols_taxas)

    # TOTAL DE DESCONTOS APENAS PARA EXIBIÇÃO NO RELATÓRIO VISUAL
    cols_todos_desc = [c for c in [desconto_vendedor_col, cupom_vendedor_col] if c]
    total_descontos_exibicao = safe_sum_cols(df, cols_todos_desc)

    # CUPONS DO VENDEDOR (Único desconto que devemos subtrair matematicamente do repasse)
    cols_cupons = [c for c in [cupom_vendedor_col] if c]
    total_cupons = safe_sum_cols(df, cols_cupons)

    cols_adicoes = [c for c in [incentivo_shopee_col] if c]
    total_adicoes = safe_sum_cols(df, cols_adicoes)

    # CÁLCULO EXACTO DO ESPERADO
    # O Subtotal já abateu o "Desconto do Vendedor" na raiz, então subtraímos apenas o "Cupom do Vendedor"
    if subtotal_col:
        total_esperado = total_bruto - total_cupons + total_adicoes - total_taxas
    else:
        total_esperado = total_bruto - total_taxas - total_cupons

    # Cálculo de Devoluções
    total_devolvido = 0.0
    if base_faturamento_col and qtd_col and ret_col:
        qtd_segura = pd.to_numeric(df[qtd_col], errors='coerce').replace(0, pd.NA)
        proporcao = (pd.to_numeric(df[ret_col], errors='coerce') / qtd_segura).fillna(0).clip(lower=0, upper=1)
        total_devolvido = (pd.to_numeric(df[base_faturamento_col], errors='coerce') * proporcao).sum()

    return {
        "Faturamento bruto": total_bruto,
        "Total de taxas": total_taxas,
        "Total de descontos": total_descontos_exibicao,
        "Total de incentivos Shopee": total_adicoes,
        "Total esperado": total_esperado,
        "Líquido da plataforma": total_esperado,
        "Ticket médio": total_bruto / df[pedido_col].nunique() if pedido_col and not df.empty else 0.0,
        "Total de pedidos": df[pedido_col].nunique() if pedido_col else 0,
        "Total de itens": pd.to_numeric(df[qtd_col], errors='coerce').sum() if qtd_col else 0,
        "Total devolvido": total_devolvido,
        "Líquido após devoluções": total_esperado - total_devolvido,
        "Margem líquida operacional %": (total_esperado / total_bruto * 100) if total_bruto > 0 else 0.0,
        "Take Rate %": (total_taxas / total_bruto * 100) if total_bruto > 0 else 0.0,
        "Peso dos descontos %": (total_descontos_exibicao / total_bruto * 100) if total_bruto > 0 else 0.0
    }

def calculate_receipt_metrics(conc_df: pd.DataFrame) -> Dict[str, float]:
    total_esperado = pd.to_numeric(conc_df["valor_esperado"], errors='coerce').sum() if "valor_esperado" in conc_df.columns else 0.0
    total_recebido = pd.to_numeric(conc_df["valor_recebido"], errors='coerce').sum() if "valor_recebido" in conc_df.columns else 0.0
    total_reembolso = pd.to_numeric(conc_df["valor_reembolso"], errors='coerce').sum() if "valor_reembolso" in conc_df.columns else 0.0
    
    df_valido = conc_df.dropna(subset=["dias_para_receber", "valor_esperado"]).copy()
    df_valido["valor_esperado"] = pd.to_numeric(df_valido["valor_esperado"], errors='coerce')
    df_valido["dias_para_receber"] = pd.to_numeric(df_valido["dias_para_receber"], errors='coerce')
    
    pmr_ponderado = 0.0
    soma_esp_valido = df_valido["valor_esperado"].sum()
    if not df_valido.empty and soma_esp_valido > 0:
        pmr_ponderado = (df_valido["dias_para_receber"] * df_valido["valor_esperado"]).sum() / soma_esp_valido

    return {
        "Total vendido": pd.to_numeric(conc_df["valor_bruto"], errors='coerce').sum() if "valor_bruto" in conc_df.columns else 0.0,
        "Total esperado": total_esperado,
        "Total recebido": total_recebido,
        "Total de reembolsos": total_reembolso,
        "Eficiência de Recebimento %": (total_recebido / total_esperado * 100) if total_esperado > 0 else 0.0,
        "PMR Ponderado (dias)": pmr_ponderado,
        "Qtd pedidos": conc_df["ID do pedido"].nunique() if "ID do pedido" in conc_df.columns else 0,
        "Qtd com lançamento": (conc_df["status_conciliacao"] == "Com lançamento").sum() if "status_conciliacao" in conc_df.columns else 0,
        "Qtd sem lançamento": (conc_df["status_conciliacao"] == "Sem lançamento").sum() if "status_conciliacao" in conc_df.columns else 0,
        "% com lançamento": ((conc_df["status_conciliacao"] == "Com lançamento").sum() / len(conc_df) * 100) if not conc_df.empty and "status_conciliacao" in conc_df.columns else 0.0,
        "Prazo médio de recebimento": pd.to_numeric(conc_df["dias_para_receber"], errors='coerce').mean() if "dias_para_receber" in conc_df.columns else 0.0
    }