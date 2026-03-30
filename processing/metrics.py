from typing import Dict

import pandas as pd

from utils.column_utils import find_column



def calculate_metrics(df: pd.DataFrame) -> Dict[str, float]:
    pedido_col = find_column(df, "ID do pedido")
    valor_total_col = find_column(df, "Valor Total")
    qtd_col = find_column(df, "Quantidade")
    ret_col = find_column(df, "Returned quantity")

    desconto_vendedor_col = find_column(df, "Desconto do vendedor")
    cupom_vendedor_col = find_column(df, "Cupom do vendedor")
    cupom_shopee_col = find_column(df, "Cupom Shopee")
    incentivo_col = find_column(df, "Incentivo Shopee para ação comercial")

    taxa_transacao_col = find_column(df, "Taxa de transação")
    comissao_bruta_col = find_column(df, "Taxa de comissão bruta")
    comissao_liquida_col = find_column(df, "Taxa de comissão líquida")
    servico_bruta_col = find_column(df, "Taxa de serviço bruta")
    servico_liquida_col = find_column(df, "Taxa de serviço líquida")
    frete_reverso_col = find_column(df, "Taxa de Envio Reversa")
    total_global_col = find_column(df, "Total global")

    total_vendas = df[valor_total_col].sum() if valor_total_col else 0.0
    total_pedidos = df[pedido_col].nunique() if pedido_col else float(len(df))
    total_itens = df[qtd_col].sum() if qtd_col else 0.0

    total_devolvido = 0.0
    if valor_total_col and qtd_col and ret_col:
        qtd_segura = df[qtd_col].replace(0, pd.NA)
        proporcao = (df[ret_col] / qtd_segura).fillna(0).clip(lower=0, upper=1)
        total_devolvido = (df[valor_total_col] * proporcao).sum()
    elif valor_total_col and "Pedido Devolvido?" in df.columns:
        total_devolvido = df.loc[df["Pedido Devolvido?"], valor_total_col].sum()

    pedidos_devolvidos = (
        df.loc[df["Pedido Devolvido?"], pedido_col].nunique()
        if pedido_col and "Pedido Devolvido?" in df.columns
        else 0
    )

    desconto_vendedor = df[desconto_vendedor_col].sum() if desconto_vendedor_col else 0.0
    cupom_vendedor = df[cupom_vendedor_col].sum() if cupom_vendedor_col else 0.0
    cupom_shopee = df[cupom_shopee_col].sum() if cupom_shopee_col else 0.0
    incentivo = df[incentivo_col].sum() if incentivo_col else 0.0
    total_descontos = desconto_vendedor + cupom_vendedor + cupom_shopee + incentivo

    taxa_transacao = df[taxa_transacao_col].sum() if taxa_transacao_col else 0.0
    comissao_bruta = df[comissao_bruta_col].sum() if comissao_bruta_col else 0.0
    comissao_liquida = df[comissao_liquida_col].sum() if comissao_liquida_col else 0.0
    servico_bruta = df[servico_bruta_col].sum() if servico_bruta_col else 0.0
    servico_liquida = df[servico_liquida_col].sum() if servico_liquida_col else 0.0
    frete_reverso = df[frete_reverso_col].sum() if frete_reverso_col else 0.0
    total_taxas = taxa_transacao + comissao_liquida + servico_liquida + frete_reverso

    if total_global_col:
        liquido_plataforma = df[total_global_col].sum()
    else:
        liquido_plataforma = total_vendas - total_taxas

    resultado_liquido_apos_devolucoes = liquido_plataforma - total_devolvido

    ticket_medio = total_vendas / total_pedidos if total_pedidos else 0.0
    faturamento_por_item = total_vendas / total_itens if total_itens else 0.0
    percentual_devolucao = (pedidos_devolvidos / total_pedidos * 100) if total_pedidos else 0.0
    margem_liquida = (liquido_plataforma / total_vendas * 100) if total_vendas else 0.0
    peso_taxas = (total_taxas / total_vendas * 100) if total_vendas else 0.0
    peso_descontos = (total_descontos / total_vendas * 100) if total_vendas else 0.0

    return {
        "Faturamento bruto": total_vendas,
        "Líquido da plataforma": liquido_plataforma,
        "Total de taxas": total_taxas,
        "Total de descontos": total_descontos,
        "Ticket médio": ticket_medio,
        "Total de pedidos": total_pedidos,
        "Total de itens": total_itens,
        "Total devolvido": total_devolvido,
        "% de devolução": percentual_devolucao,
        "Líquido após devoluções": resultado_liquido_apos_devolucoes,
        "Margem líquida operacional %": margem_liquida,
        "Peso das taxas %": peso_taxas,
        "Peso dos descontos %": peso_descontos,
        "Faturamento por item": faturamento_por_item,
        "Comissão bruta": comissao_bruta,
        "Comissão líquida": comissao_liquida,
        "Serviço bruto": servico_bruta,
        "Serviço líquido": servico_liquida,
        "Taxa de transação": taxa_transacao,
        "Frete reverso": frete_reverso,
    }



def calculate_receipt_metrics(conc_df: pd.DataFrame) -> Dict[str, float]:
    total_vendido = conc_df["valor_vendido"].sum() if "valor_vendido" in conc_df.columns else 0.0
    total_esperado = conc_df["valor_esperado"].sum() if "valor_esperado" in conc_df.columns else 0.0
    total_recebido = conc_df["valor_recebido"].sum() if "valor_recebido" in conc_df.columns else 0.0
    saldo_pendente = total_esperado - total_recebido

    qtd_pedidos = conc_df["ID do pedido"].nunique() if "ID do pedido" in conc_df.columns else 0
    qtd_integral = (conc_df["status_conciliacao"] == "Recebido integralmente").sum()
    qtd_parcial = (conc_df["status_conciliacao"] == "Recebido parcialmente").sum()
    qtd_nao = (conc_df["status_conciliacao"] == "Não recebido").sum()
    qtd_maior = (conc_df["status_conciliacao"] == "Recebido a maior").sum()

    perc_conciliado = (qtd_integral / qtd_pedidos * 100) if qtd_pedidos else 0.0
    perc_nao_conciliado = ((qtd_parcial + qtd_nao + qtd_maior) / qtd_pedidos * 100) if qtd_pedidos else 0.0

    prazo_medio = conc_df["dias_para_receber"].dropna().mean() if "dias_para_receber" in conc_df.columns else 0.0

    return {
        "Total vendido": total_vendido,
        "Total esperado": total_esperado,
        "Total recebido": total_recebido,
        "Saldo pendente": saldo_pendente,
        "Qtd pedidos": qtd_pedidos,
        "Qtd integralmente recebidos": qtd_integral,
        "Qtd recebidos parcialmente": qtd_parcial,
        "Qtd não recebidos": qtd_nao,
        "Qtd recebidos a maior": qtd_maior,
        "% conciliado": perc_conciliado,
        "% não conciliado": perc_nao_conciliado,
        "Prazo médio de recebimento": prazo_medio if pd.notna(prazo_medio) else 0.0,
    }
