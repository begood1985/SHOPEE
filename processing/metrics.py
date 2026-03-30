import pandas as pd
from typing import Dict
from utils.column_utils import find_column

def calculate_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """Calcula métricas de faturamento e o Total Esperado solicitado."""
    pedido_col = find_column(df, "ID do pedido")
    valor_total_col = find_column(df, "Valor Total")
    qtd_col = find_column(df, "Quantidade")
    ret_col = find_column(df, "Returned quantity")

    # Colunas de Descontos
    desconto_vendedor_col = find_column(df, "Desconto do vendedor")
    cupom_vendedor_col = find_column(df, "Cupom do vendedor")
    cupom_shopee_col = find_column(df, "Cupom Shopee")
    incentivo_col = find_column(df, "Incentivo Shopee para ação comercial")

    # Colunas de Taxas
    taxa_transacao_col = find_column(df, "Taxa de transação")
    comissao_liquida_col = find_column(df, "Taxa de comissão líquida")
    servico_liquida_col = find_column(df, "Taxa de serviço líquida")
    frete_reverso_col = find_column(df, "Taxa de Envio Reversa")
    total_global_col = find_column(df, "Total global")

    # Cálculos de Totais
    total_bruto = df[valor_total_col].sum() if valor_total_col else 0.0
    
    # Soma de todos os descontos identificados
    cols_desconto = [c for c in [desconto_vendedor_col, cupom_vendedor_col, cupom_shopee_col, incentivo_col] if c]
    total_descontos = df[cols_desconto].sum().sum() if cols_desconto else 0.0
    
    # Soma de todas as taxas identificadas
    taxa_transacao = df[taxa_transacao_col].sum() if taxa_transacao_col else 0.0
    comissao_liq = df[comissao_liquida_col].sum() if comissao_liquida_col else 0.0
    servico_liq = df[servico_liquida_col].sum() if servico_liquida_col else 0.0
    frete_reverso = df[frete_reverso_col].sum() if frete_reverso_col else 0.0
    total_taxas = taxa_transacao + comissao_liq + servico_liq + frete_reverso

    # FÓRMULA: Bruto - Taxas - Descontos
    total_esperado = total_bruto - total_taxas - total_descontos

    # Cálculo de Devoluções
    total_devolvido = 0.0
    if valor_total_col and qtd_col and ret_col:
        qtd_segura = df[qtd_col].replace(0, pd.NA)
        proporcao = (df[ret_col] / qtd_segura).fillna(0).clip(lower=0, upper=1)
        total_devolvido = (df[valor_total_col] * proporcao).sum()
    elif valor_total_col and "Pedido Devolvido?" in df.columns:
        total_devolvido = df.loc[df["Pedido Devolvido?"], valor_total_col].sum()

    liquido_plataforma = df[total_global_col].sum() if total_global_col else (total_bruto - total_taxas)

    return {
        "Faturamento bruto": total_bruto,
        "Total de taxas": total_taxas,
        "Total de descontos": total_descontos,
        "Total esperado": total_esperado,
        "Líquido da plataforma": liquido_plataforma,
        "Ticket médio": total_bruto / df[pedido_col].nunique() if pedido_col and not df.empty else 0.0,
        "Total de pedidos": df[pedido_col].nunique() if pedido_col else 0,
        "Total de itens": df[qtd_col].sum() if qtd_col else 0,
        "Total devolvido": total_devolvido,
        "Líquido após devoluções": total_esperado - total_devolvido,
        "Margem líquida operacional %": (total_esperado / total_bruto * 100) if total_bruto else 0.0,
        "Take Rate %": (total_taxas / total_bruto * 100) if total_bruto else 0.0,
        "Peso dos descontos %": (total_descontos / total_bruto * 100) if total_bruto else 0.0,
        "Taxa de transação": taxa_transacao,
        "Frete reverso": frete_reverso,
        "Comissão líquida": comissao_liq,
        "Serviço líquido": servico_liq
    }

def calculate_receipt_metrics(conc_df: pd.DataFrame) -> Dict[str, float]:
    """Calcula métricas para o relatório de conciliação de recebimentos."""
    total_esperado = conc_df["valor_esperado"].sum() if "valor_esperado" in conc_df.columns else 0.0
    total_recebido = conc_df["valor_recebido"].sum() if "valor_recebido" in conc_df.columns else 0.0
    
    # PMR Ponderado
    df_valido = conc_df.dropna(subset=["dias_para_receber", "valor_esperado"])
    pmr_ponderado = 0.0
    if not df_valido.empty and df_valido["valor_esperado"].sum() > 0:
        pmr_ponderado = (df_valido["dias_para_receber"] * df_valido["valor_esperado"]).sum() / df_valido["valor_esperado"].sum()

    return {
        "Total vendido": conc_df["valor_bruto"].sum() if "valor_bruto" in conc_df.columns else 0.0,
        "Total esperado": total_esperado,
        "Total recebido": total_recebido,
        "Saldo pendente": total_esperado - total_recebido,
        "Eficiência de Recebimento %": (total_recebido / total_esperado * 100) if total_esperado > 0 else 0.0,
        "PMR Ponderado (dias)": pmr_ponderado,
        "Qtd pedidos": conc_df["ID do pedido"].nunique() if "ID do pedido" in conc_df.columns else 0,
        "Qtd integralmente recebidos": (conc_df["status_conciliacao"] == "Recebido integralmente").sum(),
        "Qtd recebidos parcialmente": (conc_df["status_conciliacao"] == "Recebido parcialmente").sum(),
        "Qtd não recebidos": (conc_df["status_conciliacao"] == "Não recebido").sum(),
        "Qtd recebidos a maior": (conc_df["status_conciliacao"] == "Recebido a maior").sum(),
        "% conciliado": ((conc_df["status_conciliacao"] == "Recebido integralmente").sum() / len(conc_df) * 100) if not conc_df.empty else 0.0,
        "Prazo médio de recebimento": conc_df["dias_para_receber"].mean() if "dias_para_receber" in conc_df.columns else 0.0
    }