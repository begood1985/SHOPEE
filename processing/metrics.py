import pandas as pd
from typing import Dict
from utils.column_utils import find_column

def safe_sum_cols(df, cols):
    """Função de segurança para garantir cálculo numérico exacto nas colunas"""
    return df[cols].apply(pd.to_numeric, errors='coerce').fillna(0).sum().sum() if cols else 0.0

def calculate_metrics(df: pd.DataFrame) -> Dict[str, float]:

    # --- NOVA TRAVA MATEMÁTICA: IGNORAR CANCELADOS NAS MÉTRICAS TOP-LEVEL ---
    status_pedido_col = find_column(df, "Status do pedido")
    if status_pedido_col:
        # Filtra a tabela para excluir cancelados antes da matemática acontecer
        df = df[~df[status_pedido_col].astype(str).str.upper().str.contains("CANCELADO")].copy()
    # ------------------------------------------------------------------------

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

    # Preparação para Consolidação (Evitar duplicidade em pedidos multi-item)
    temp = df.copy()
    cols_taxas = [c for c in [taxa_transacao_col, comissao_liquida_col, servico_liquida_col, frete_reverso_col, ajuste_acao_col] if c]
    cols_cupons = [c for c in [cupom_vendedor_col] if c]
    cols_adicoes = [c for c in [incentivo_shopee_col] if c]
    cols_todos_desc = [c for c in [desconto_vendedor_col, cupom_vendedor_col] if c]

    # Cálculos por linha
    base_faturamento_col = subtotal_col if subtotal_col else valor_total_col
    temp['_bruto_row'] = pd.to_numeric(temp[base_faturamento_col], errors='coerce').fillna(0)
    temp['_taxas_row'] = temp[cols_taxas].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) if cols_taxas else 0.0
    temp['_cupons_row'] = temp[cols_cupons].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) if cols_cupons else 0.0
    temp['_adicoes_row'] = temp[cols_adicoes].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) if cols_adicoes else 0.0
    temp['_desc_vis_row'] = temp[cols_todos_desc].apply(pd.to_numeric, errors='coerce').fillna(0).sum(axis=1) if cols_todos_desc else 0.0

    # Agrupamento por ID do pedido: Soma o bruto (itens), mas pega o máximo das taxas/cupons (repetidos)
    order_agg = temp.groupby(pedido_col).agg({
        '_bruto_row': 'sum',
        '_taxas_row': 'max',
        '_cupons_row': 'max',
        '_adicoes_row': 'max',
        '_desc_vis_row': 'max'
    })

    total_bruto = order_agg['_bruto_row'].sum()
    total_taxas = order_agg['_taxas_row'].sum()
    total_cupons = order_agg['_cupons_row'].sum()
    total_adicoes = order_agg['_adicoes_row'].sum()
    total_descontos_exibicao = order_agg['_desc_vis_row'].sum()

    # Cálculo do Esperado: Subtotal - Cupom Vendedor + Incentivos - Taxas
    total_esperado = total_bruto - total_cupons + total_adicoes - total_taxas

    # Cálculo de Devoluções (mantido por linha pois é proporcional ao item)
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
    total_bruto_venda = pd.to_numeric(conc_df["valor_bruto"], errors='coerce').sum() if "valor_bruto" in conc_df.columns else 0.0
    
    divergencia_total = conc_df["divergencia"].sum() if "divergencia" in conc_df.columns else 0.0
    ganhos_ajustes = conc_df[conc_df["divergencia"] > 0]["divergencia"].sum() if "divergencia" in conc_df.columns else 0.0
    
    # Perdas por devolução/reembolso (divergência negativa onde houve reembolso)
    perdas_totais = conc_df[conc_df["divergencia"] < 0]["divergencia"].sum() if "divergencia" in conc_df.columns else 0.0
    
    # Cálculo da Taxa Efetiva
    taxa_efetiva_percent = 0.0
    if total_bruto_venda > 0:
        total_encargos = total_bruto_venda - total_recebido
        taxa_efetiva_percent = (total_encargos / total_bruto_venda) * 100

    outras_diferencas_neg = perdas_totais # Ajustar se houver métrica específica para isso
    
    df_valido = conc_df.dropna(subset=["dias_para_receber", "valor_esperado"]).copy()
    df_valido["valor_esperado"] = pd.to_numeric(df_valido["valor_esperado"], errors='coerce')
    df_valido["dias_para_receber"] = pd.to_numeric(df_valido["dias_para_receber"], errors='coerce')
    
    pmr_ponderado = 0.0
    soma_esp_valido = df_valido["valor_esperado"].sum()
    if not df_valido.empty and soma_esp_valido > 0:
        pmr_ponderado = (df_valido["dias_para_receber"] * df_valido["valor_esperado"]).sum() / soma_esp_valido

    return {
        "Total vendido": total_bruto_venda,
        "Total esperado": total_esperado,
        "Total recebido": total_recebido,
        "Total de reembolsos": total_reembolso,
        "Divergência Total (Ajustes)": divergencia_total,
        "Saldos Positivos (Ganhos)": ganhos_ajustes,
        "Saldos Negativos (Diferenças)": perdas_totais,
        "Outras Diferenças Negativas": outras_diferencas_neg,
        "Taxa Efetiva %": taxa_efetiva_percent,
        "Eficiência de Recebimento %": (total_recebido / total_esperado * 100) if total_esperado > 0 else 0.0,
        "PMR Ponderado (dias)": pmr_ponderado,
        "Qtd pedidos": conc_df["ID do pedido"].nunique() if "ID do pedido" in conc_df.columns else 0,
        "Qtd com lançamento": (conc_df["status_conciliacao"] == "Com lançamento").sum() if "status_conciliacao" in conc_df.columns else 0,
        "Qtd sem lançamento": (conc_df["status_conciliacao"] == "Sem lançamento").sum() if "status_conciliacao" in conc_df.columns else 0,
        "% com lançamento": ((conc_df["status_conciliacao"] == "Com lançamento").sum() / len(conc_df) * 100) if not conc_df.empty and "status_conciliacao" in conc_df.columns else 0.0,
        "Prazo médio de recebimento": pd.to_numeric(conc_df["dias_para_receber"], errors='coerce').mean() if "dias_para_receber" in conc_df.columns else 0.0
    }