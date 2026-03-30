from datetime import date

import streamlit as st

from utils.column_utils import find_column


def apply_filters(df):
    st.sidebar.header("Filtros")
    filtered = df.copy()

    data_col = find_column(filtered, "Data de criação do pedido")
    status_col = find_column(filtered, "Status do pedido")
    uf_col = find_column(filtered, "UF")
    cidade_col = find_column(filtered, "Cidade")
    produto_col = find_column(filtered, "Nome do Produto")

    if data_col and filtered[data_col].notna().any():

        min_date = date(2025, 1, 1)
        max_date = date(2026, 12, 31)

        default_start = date(2025, 12, 1)
        default_end = date(2025, 12, 31)

        selected_dates = st.sidebar.date_input(
            "Período das vendas",
            value=(default_start, default_end),
            min_value=min_date,
            max_value=max_date,
        )

        if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
            start_date, end_date = selected_dates

            filtered = filtered[
                (filtered[data_col].dt.date >= start_date)
                & (filtered[data_col].dt.date <= end_date)
            ]

    if status_col:
        status = st.sidebar.multiselect(
            "Status do pedido",
            sorted([s for s in filtered[status_col].dropna().unique() if s]),
            default=[],
        )

        if status:
            filtered = filtered[filtered[status_col].isin(status)]

    only_completed = st.sidebar.checkbox("Somente pedidos concluídos")

    if only_completed:
        filtered = filtered[
            filtered["_status_pedido_norm"].isin(
                ["concluido", "concluido entregue", "completed"]
            )
        ]

    only_refunds = st.sidebar.checkbox("Somente devolvidos/reembolsados")

    if only_refunds:
        filtered = filtered[filtered["Pedido Devolvido?"]]

    if uf_col:
        uf = st.sidebar.multiselect(
            "UF",
            sorted([u for u in filtered[uf_col].dropna().unique() if u]),
            default=[],
        )

        if uf:
            filtered = filtered[filtered[uf_col].isin(uf)]

    if cidade_col:
        cidade = st.sidebar.multiselect(
            "Cidade",
            sorted([c for c in filtered[cidade_col].dropna().unique() if c])[:300],
            default=[],
        )

        if cidade:
            filtered = filtered[filtered[cidade_col].isin(cidade)]

    if produto_col:
        produto = st.sidebar.text_input("Filtrar produto por nome")

        if produto:
            filtered = filtered[
                filtered[produto_col].str.contains(produto, case=False, na=False)
            ]

    return filtered