import pandas as pd
from utils.column_utils import find_column, find_column_flexible


def reconcile_sales_and_receipts(sales_df: pd.DataFrame, receipts_df: pd.DataFrame) -> pd.DataFrame:
    def pick_col(df: pd.DataFrame, options: list[str]) -> str | None:
        return find_column_flexible(df, options)

    pedido_col = find_column(sales_df, "ID do pedido")
    venda_data_col = find_column(sales_df, "Data de criação do pedido")

    subtotal_col = pick_col(sales_df, ["Subtotal do produto", "Subtotal", "Valor do produto"])
    valor_total_col = pick_col(sales_df, ["Valor Total", "Total global", "Total do pedido"])

    if pedido_col is None:
        raise ValueError("A folha de vendas não possui a coluna ID do pedido.")
    if receipts_df.empty:
        raise ValueError("Nenhum recebimento foi carregado.")

    taxa_transacao_col = pick_col(sales_df, ["Taxa de transação", "Taxa de transacao"])
    comissao_liq_col = pick_col(sales_df, ["Taxa de comissão líquida", "Taxa de comissao liquida"])
    servico_liq_col = pick_col(sales_df, ["Taxa de serviço líquida", "Taxa de servico liquida"])
    frete_rev_col = pick_col(sales_df, ["Taxa de Envio Reversa", "Taxa envio reversa", "Frete reverso"])
    ajuste_acao_col = pick_col(
        sales_df,
        [
            "Ajuste por participação em ação comercial",
            "Ajuste por participacao em acao comercial",
            "Ajuste ação comercial",
        ],
    )

    cupom_vend_col = pick_col(sales_df, ["Cupom do vendedor", "Cupom vendedor"])
    incentivo_shopee_col = pick_col(
        sales_df,
        [
            "Incentivo Shopee para ação comercial",
            "Incentivo Shopee para acao comercial",
            "Incentivo Shopee",
        ],
    )
    status_pedido_col = find_column(sales_df, "Status do pedido")

    sales_df = sales_df.copy()
    sales_df[pedido_col] = sales_df[pedido_col].fillna("").astype(str).str.strip()
    sales_df = sales_df[sales_df[pedido_col] != ""].copy()

    cols_taxas = [c for c in [taxa_transacao_col, comissao_liq_col, servico_liq_col, frete_rev_col, ajuste_acao_col] if c]
    cols_cupons = [c for c in [cupom_vend_col] if c]
    cols_adicoes = [c for c in [incentivo_shopee_col] if c]

    base_faturamento_col = subtotal_col if subtotal_col else valor_total_col
    sales_df["_base_calc"] = pd.to_numeric(sales_df[base_faturamento_col], errors="coerce").fillna(0)

    # Taxas, cupons e incentivos podem vir duplicados por item no mesmo pedido.
    # Nesses casos, consolidamos por pedido usando max() para considerar só uma vez.
    for col in cols_taxas + cols_cupons + cols_adicoes:
        sales_df[col] = pd.to_numeric(sales_df[col], errors="coerce").fillna(0)

    agg_dict = {"valor_bruto": ("_base_calc", "sum")}
    if venda_data_col:
        agg_dict["data_venda"] = (venda_data_col, "min")
    if status_pedido_col:
        agg_dict["_pedido_cancelado"] = (
            status_pedido_col,
            lambda s: s.astype(str).str.upper().str.contains("CANCELADO").any(),
        )

    for col in cols_taxas:
        agg_dict[f"_taxa_unique::{col}"] = (col, "max")
    for col in cols_cupons:
        agg_dict[f"_cupom_unique::{col}"] = (col, "max")
    for col in cols_adicoes:
        agg_dict[f"_adicao_unique::{col}"] = (col, "max")

    sales_summary = (
        sales_df.groupby(pedido_col)
        .agg(**agg_dict)
        .reset_index()
        .rename(columns={pedido_col: "ID do pedido"})
    )

    taxa_cols_summary = [c for c in sales_summary.columns if c.startswith("_taxa_unique::")]
    cupom_cols_summary = [c for c in sales_summary.columns if c.startswith("_cupom_unique::")]
    adicao_cols_summary = [c for c in sales_summary.columns if c.startswith("_adicao_unique::")]

    total_taxas_unicas = sales_summary[taxa_cols_summary].sum(axis=1) if taxa_cols_summary else 0.0
    total_cupons_unicos = sales_summary[cupom_cols_summary].sum(axis=1) if cupom_cols_summary else 0.0
    total_adicoes_unicas = sales_summary[adicao_cols_summary].sum(axis=1) if adicao_cols_summary else 0.0

    # Liquido esperado calculado somente apos consolidar por pedido.
    sales_summary["valor_esperado"] = (
        sales_summary["valor_bruto"]
        - total_cupons_unicos
        + total_adicoes_unicas
        - total_taxas_unicas
    )

    if "_pedido_cancelado" in sales_summary.columns:
        sales_summary.loc[sales_summary["_pedido_cancelado"], ["valor_bruto", "valor_esperado"]] = 0.0

    # -------------------------------
    # DOUBLE-ENTRY CHECK (PROVA REAL)
    # -------------------------------
    # 1) Consistencia de agregacao: soma consolidada vs soma base original filtrada.
    base_origem_check = sales_df["_base_calc"].copy()
    if "_pedido_cancelado" in sales_summary.columns and status_pedido_col:
        cancelados_origem = sales_df[status_pedido_col].astype(str).str.upper().str.contains("CANCELADO")
        base_origem_check = base_origem_check.where(~cancelados_origem, 0.0)
    bruto_origem_total = float(base_origem_check.sum())
    bruto_consolidado_total = float(sales_summary["valor_bruto"].sum())
    check_agregacao_global = round(bruto_origem_total - bruto_consolidado_total, 2) == 0

    # 2) Equacao de fechamento por pedido.
    esperado_recalculado = (
        sales_summary["valor_bruto"]
        - total_cupons_unicos
        + total_adicoes_unicas
        - total_taxas_unicas
    )
    check_equacao_pedido = (sales_summary["valor_esperado"] - esperado_recalculado).round(2).abs().eq(0)

    # 3) Verificacao cruzada total: valor_esperado final vs prova real da base de origem.
    total_esperado_consolidado = float(sales_summary["valor_esperado"].sum())
    total_esperado_prova_real = float(esperado_recalculado.sum())
    check_total_prova_real = round(total_esperado_consolidado - total_esperado_prova_real, 2) == 0

    # Flag final por pedido (booleana)
    sales_summary["check_integridade"] = check_equacao_pedido & check_agregacao_global & check_total_prova_real

    if "_pedido_cancelado" in sales_summary.columns:
        sales_summary = sales_summary.drop(columns=["_pedido_cancelado"])

    # Agrupar Recebimentos
    agg_receipts = {
        "valor_recebido": ("_receipt_amount", "sum"),
        "primeiro_recebimento": ("_receipt_date", "min"),
        "ultimo_recebimento": ("_receipt_date", "max"),
    }
    if "_receipt_refund_amount" in receipts_df.columns:
        agg_receipts["valor_reembolso"] = ("_receipt_refund_amount", "sum")

    receipts_summary = (
        receipts_df.groupby("_receipt_order_id")
        .agg(**agg_receipts)
        .reset_index()
        .rename(columns={"_receipt_order_id": "ID do pedido"})
    )

    conc = sales_summary.merge(receipts_summary, on="ID do pedido", how="left")
    conc["valor_recebido"] = conc["valor_recebido"].fillna(0.0)

    if "valor_reembolso" in conc.columns:
        conc["valor_reembolso"] = conc["valor_reembolso"].fillna(0.0)
    else:
        conc["valor_reembolso"] = 0.0

    # Divergencia residual: o reembolso explica parte da ausencia de caixa,
    # portanto nao deve ser somado como perda adicional.
    conc["divergencia"] = conc["valor_recebido"] - (conc["valor_esperado"] + conc["valor_reembolso"])
    # Gap bruto entre recebido e esperado (sem considerar reembolso).
    conc["divergencia_operacional_sem_reembolso"] = conc["valor_recebido"] - conc["valor_esperado"]

    def classify(row):
        recebido = row["valor_recebido"]
        reembolso = row["valor_reembolso"]
        if abs(recebido) <= 0.01 and abs(reembolso) <= 0.01:
            return "Sem lançamento"
        return "Com lançamento"

    conc["status_conciliacao"] = conc.apply(classify, axis=1)

    if "primeiro_recebimento" in conc.columns and "data_venda" in conc.columns:
        conc["dias_para_receber"] = (
            pd.to_datetime(conc["primeiro_recebimento"]) - pd.to_datetime(conc["data_venda"])
        ).dt.days
    else:
        conc["dias_para_receber"] = pd.NA

    return conc
