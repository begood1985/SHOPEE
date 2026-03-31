import pandas as pd
from typing import Dict
from utils.column_utils import find_column, find_column_flexible


def safe_sum_cols(df, cols):
    """Soma segura de colunas numéricas."""
    return df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum().sum() if cols else 0.0


def calculate_metrics(df: pd.DataFrame) -> Dict[str, float]:
    def pick_col(frame: pd.DataFrame, options: list[str]) -> str | None:
        return find_column_flexible(frame, options)

    pedido_col = find_column(df, "ID do pedido")
    valor_total_col = pick_col(df, ["Valor Total", "Total global", "Total do pedido"])
    subtotal_col = pick_col(df, ["Subtotal do produto", "Subtotal", "Valor do produto"])
    qtd_col = find_column(df, "Quantidade")
    ret_col = find_column(df, "Returned quantity")
    status_pedido_col = find_column(df, "Status do pedido")

    taxa_transacao_col = pick_col(df, ["Taxa de transação", "Taxa de transacao"])
    comissao_liquida_col = pick_col(df, ["Taxa de comissão líquida", "Taxa de comissao liquida"])
    servico_liquida_col = pick_col(df, ["Taxa de serviço líquida", "Taxa de servico liquida"])
    frete_reverso_col = pick_col(df, ["Taxa de Envio Reversa", "Taxa envio reversa", "Frete reverso"])
    ajuste_acao_col = pick_col(
        df,
        [
            "Ajuste por participação em ação comercial",
            "Ajuste por participacao em acao comercial",
            "Ajuste ação comercial",
        ],
    )

    desconto_vendedor_col = find_column(df, "Desconto do vendedor")
    cupom_vendedor_col = find_column(df, "Cupom do vendedor")
    incentivo_shopee_col = find_column(df, "Incentivo Shopee para ação comercial")

    if pedido_col is None:
        # Fallback simples caso não exista ID do pedido na base.
        base_faturamento_col = subtotal_col if subtotal_col else valor_total_col
        total_bruto = pd.to_numeric(df[base_faturamento_col], errors="coerce").fillna(0).sum() if base_faturamento_col else 0.0
        total_gmv = pd.to_numeric(df[valor_total_col], errors="coerce").fillna(0).sum() if valor_total_col else 0.0

        cols_taxas = [c for c in [taxa_transacao_col, comissao_liquida_col, servico_liquida_col, frete_reverso_col, ajuste_acao_col] if c]
        cols_todos_desc = [c for c in [desconto_vendedor_col, cupom_vendedor_col] if c]
        cols_cupons = [c for c in [cupom_vendedor_col] if c]
        cols_adicoes = [c for c in [incentivo_shopee_col] if c]

        total_taxas = safe_sum_cols(df, cols_taxas)
        total_descontos_exibicao = safe_sum_cols(df, cols_todos_desc)
        total_cupons = safe_sum_cols(df, cols_cupons)
        total_adicoes = safe_sum_cols(df, cols_adicoes)
        total_esperado = total_bruto - total_cupons + total_adicoes - total_taxas

        total_devolvido = 0.0
        if base_faturamento_col and qtd_col and ret_col:
            qtd_segura = pd.to_numeric(df[qtd_col], errors="coerce").replace(0, pd.NA)
            proporcao = (pd.to_numeric(df[ret_col], errors="coerce") / qtd_segura).fillna(0).clip(lower=0, upper=1)
            total_devolvido = (pd.to_numeric(df[base_faturamento_col], errors="coerce") * proporcao).sum()

        total_pedidos = 0
        return {
            "Volume Transacionado (GMV)": total_gmv,
            "Faturamento bruto": total_bruto,
            "Total de taxas": total_taxas,
            "Total de descontos": total_descontos_exibicao,
            "Total de incentivos Shopee": total_adicoes,
            "Total esperado": total_esperado,
            "Líquido da plataforma": total_esperado,
            "Ticket médio": 0.0,
            "Total de pedidos": total_pedidos,
            "Total de itens": pd.to_numeric(df[qtd_col], errors="coerce").sum() if qtd_col else 0,
            "Total devolvido": total_devolvido,
            "Líquido após devoluções": total_esperado - total_devolvido,
            "Margem líquida operacional %": (total_esperado / total_bruto * 100) if total_bruto > 0 else 0.0,
            "Take Rate %": (total_taxas / total_bruto * 100) if total_bruto > 0 else 0.0,
            "Peso dos descontos %": (total_descontos_exibicao / total_bruto * 100) if total_bruto > 0 else 0.0,
        }

    df_work = df.copy()
    df_work[pedido_col] = df_work[pedido_col].fillna("").astype(str).str.strip()
    df_work = df_work[df_work[pedido_col] != ""].copy()

    base_faturamento_col = subtotal_col if subtotal_col else valor_total_col
    df_work["_valor_bruto_item"] = pd.to_numeric(df_work[base_faturamento_col], errors="coerce").fillna(0) if base_faturamento_col else 0.0
    df_work["_gmv_item"] = pd.to_numeric(df_work[valor_total_col], errors="coerce").fillna(0) if valor_total_col else 0.0
    df_work["_qtd_item"] = pd.to_numeric(df_work[qtd_col], errors="coerce").fillna(0) if qtd_col else 0.0
    df_work["_ret_item"] = pd.to_numeric(df_work[ret_col], errors="coerce").fillna(0) if ret_col else 0.0

    cols_taxas = [c for c in [taxa_transacao_col, comissao_liquida_col, servico_liquida_col, frete_reverso_col, ajuste_acao_col] if c]
    cols_todos_desc = [c for c in [desconto_vendedor_col, cupom_vendedor_col] if c]
    cols_cupons = [c for c in [cupom_vendedor_col] if c]
    cols_adicoes = [c for c in [incentivo_shopee_col] if c]

    for col in cols_taxas + cols_todos_desc + cols_cupons + cols_adicoes:
        df_work[col] = pd.to_numeric(df_work[col], errors="coerce").fillna(0)

    agg_dict = {
        "_valor_bruto_pedido": ("_valor_bruto_item", "sum"),
        "_gmv_pedido": ("_gmv_item", "sum"),
        "_qtd_pedido": ("_qtd_item", "sum"),
        "_ret_pedido": ("_ret_item", "sum"),
    }
    if status_pedido_col:
        agg_dict["_pedido_cancelado"] = (
            status_pedido_col,
            lambda s: s.astype(str).str.upper().str.contains("CANCELADO").any(),
        )

    for col in cols_taxas:
        agg_dict[f"_taxa_unique::{col}"] = (col, "max")
    for col in cols_todos_desc:
        agg_dict[f"_desc_unique::{col}"] = (col, "max")
    for col in cols_cupons:
        agg_dict[f"_cupom_unique::{col}"] = (col, "max")
    for col in cols_adicoes:
        agg_dict[f"_adicao_unique::{col}"] = (col, "max")

    pedidos = df_work.groupby(pedido_col).agg(**agg_dict).reset_index()

    if "_pedido_cancelado" in pedidos.columns:
        pedidos = pedidos[~pedidos["_pedido_cancelado"]].copy()

    taxa_cols_summary = [c for c in pedidos.columns if c.startswith("_taxa_unique::")]
    desc_cols_summary = [c for c in pedidos.columns if c.startswith("_desc_unique::")]
    cupom_cols_summary = [c for c in pedidos.columns if c.startswith("_cupom_unique::")]
    adicao_cols_summary = [c for c in pedidos.columns if c.startswith("_adicao_unique::")]

    total_bruto = pedidos["_valor_bruto_pedido"].sum() if "_valor_bruto_pedido" in pedidos.columns else 0.0
    total_gmv = pedidos["_gmv_pedido"].sum() if "_gmv_pedido" in pedidos.columns else 0.0
    total_taxas = pedidos[taxa_cols_summary].sum(axis=1).sum() if taxa_cols_summary else 0.0
    total_descontos_exibicao = pedidos[desc_cols_summary].sum(axis=1).sum() if desc_cols_summary else 0.0
    total_cupons = pedidos[cupom_cols_summary].sum(axis=1).sum() if cupom_cols_summary else 0.0
    total_adicoes = pedidos[adicao_cols_summary].sum(axis=1).sum() if adicao_cols_summary else 0.0

    total_esperado = total_bruto - total_cupons + total_adicoes - total_taxas

    total_devolvido = 0.0
    if "_valor_bruto_pedido" in pedidos.columns and "_qtd_pedido" in pedidos.columns and "_ret_pedido" in pedidos.columns:
        qtd_segura = pedidos["_qtd_pedido"].replace(0, pd.NA)
        proporcao = (pedidos["_ret_pedido"] / qtd_segura).fillna(0).clip(lower=0, upper=1)
        total_devolvido = (pedidos["_valor_bruto_pedido"] * proporcao).sum()

    total_pedidos = pedidos[pedido_col].nunique() if pedido_col in pedidos.columns else 0

    return {
        "Volume Transacionado (GMV)": total_gmv,
        "Faturamento bruto": total_bruto,
        "Total de taxas": total_taxas,
        "Total de descontos": total_descontos_exibicao,
        "Total de incentivos Shopee": total_adicoes,
        "Total esperado": total_esperado,
        "Líquido da plataforma": total_esperado,
        "Ticket médio": (total_bruto / total_pedidos) if total_pedidos > 0 else 0.0,
        "Total de pedidos": total_pedidos,
        "Total de itens": pedidos["_qtd_pedido"].sum() if "_qtd_pedido" in pedidos.columns else 0,
        "Total devolvido": total_devolvido,
        "Líquido após devoluções": total_esperado - total_devolvido,
        "Margem líquida operacional %": (total_esperado / total_bruto * 100) if total_bruto > 0 else 0.0,
        "Take Rate %": (total_taxas / total_bruto * 100) if total_bruto > 0 else 0.0,
        "Peso dos descontos %": (total_descontos_exibicao / total_bruto * 100) if total_bruto > 0 else 0.0,
    }


def calculate_receipt_metrics(conc_df: pd.DataFrame) -> Dict[str, float]:
    total_esperado = pd.to_numeric(conc_df["valor_esperado"], errors="coerce").sum() if "valor_esperado" in conc_df.columns else 0.0
    total_recebido = pd.to_numeric(conc_df["valor_recebido"], errors="coerce").sum() if "valor_recebido" in conc_df.columns else 0.0
    total_reembolso = pd.to_numeric(conc_df["valor_reembolso"], errors="coerce").sum() if "valor_reembolso" in conc_df.columns else 0.0

    work = conc_df.copy()
    work["divergencia"] = pd.to_numeric(work.get("divergencia", 0.0), errors="coerce").fillna(0.0)
    work["valor_reembolso"] = pd.to_numeric(work.get("valor_reembolso", 0.0), errors="coerce").fillna(0.0)
    # Com a formula nova, "divergencia" ja e o ajuste residual nao explicado por recebimento/reembolso.
    work["outros_ajustes"] = work["divergencia"]
    work["divergencia_operacional_sem_reembolso"] = pd.to_numeric(
        work.get("divergencia_operacional_sem_reembolso", work.get("valor_recebido", 0.0) - work.get("valor_esperado", 0.0)),
        errors="coerce",
    ).fillna(0.0)

    divergencia_total = work["divergencia"].sum()
    divergencia_operacional_total = work["divergencia_operacional_sem_reembolso"].sum()
    ganhos_ajustes = work[work["divergencia"] > 0.01]["divergencia"].sum()
    perdas_totais = work[work["divergencia"] < -0.01]["divergencia"].sum()
    outras_diferencas_neg = work[work["outros_ajustes"] < -0.01]["outros_ajustes"].sum()

    df_valido = conc_df.dropna(subset=["dias_para_receber", "valor_esperado"]).copy()
    df_valido["valor_esperado"] = pd.to_numeric(df_valido["valor_esperado"], errors="coerce")
    df_valido["dias_para_receber"] = pd.to_numeric(df_valido["dias_para_receber"], errors="coerce")

    pmr_ponderado = 0.0
    soma_esp_valido = df_valido["valor_esperado"].sum()
    if not df_valido.empty and soma_esp_valido > 0:
        pmr_ponderado = (df_valido["dias_para_receber"] * df_valido["valor_esperado"]).sum() / soma_esp_valido

    # Prova real de fechamento de caixa:
    # Total Recebido = Total Esperado + Total Reembolsos + Divergencia Total
    diferenca_fechamento = total_recebido - (total_esperado + total_reembolso + divergencia_total)
    fechamento_ok = round(diferenca_fechamento, 2) == 0

    return {
        "Total vendido": pd.to_numeric(conc_df["valor_bruto"], errors="coerce").sum() if "valor_bruto" in conc_df.columns else 0.0,
        "Total esperado": total_esperado,
        "Total recebido": total_recebido,
        "Total de reembolsos": total_reembolso,
        "Divergência Total (Ajustes)": divergencia_total,
        "Divergência Operacional (sem reembolso)": divergencia_operacional_total,
        "Saldos Positivos (Ganhos)": ganhos_ajustes,
        "Saldos Negativos (Diferenças)": perdas_totais,
        "Outras Diferenças Negativas": outras_diferencas_neg,
        "Eficiência de Recebimento %": (total_recebido / total_esperado * 100) if total_esperado > 0 else 0.0,
        "Integridade do Processamento": "OK" if fechamento_ok else "Falha",
        "Diferença da Prova Real": diferenca_fechamento,
        "PMR Ponderado (dias)": pmr_ponderado,
        "Qtd pedidos": conc_df["ID do pedido"].nunique() if "ID do pedido" in conc_df.columns else 0,
        "Qtd com lançamento": (conc_df["status_conciliacao"] == "Com lançamento").sum() if "status_conciliacao" in conc_df.columns else 0,
        "Qtd sem lançamento": (conc_df["status_conciliacao"] == "Sem lançamento").sum() if "status_conciliacao" in conc_df.columns else 0,
        "% com lançamento": ((conc_df["status_conciliacao"] == "Com lançamento").sum() / len(conc_df) * 100) if not conc_df.empty and "status_conciliacao" in conc_df.columns else 0.0,
        "Prazo médio de recebimento": pd.to_numeric(conc_df["dias_para_receber"], errors="coerce").mean() if "dias_para_receber" in conc_df.columns else 0.0,
    }
