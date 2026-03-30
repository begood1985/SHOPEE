import pandas as pd
import streamlit as st

from data_loader.receipts_loader import load_multiple_receipts
from data_loader.sales_loader import load_sales_excel, validate_columns
from export.excel_export import export_excel
from processing.filters import apply_filters
from processing.metrics import calculate_metrics, calculate_receipt_metrics
from processing.reconciliation import reconcile_sales_and_receipts
from processing.sales_normalizer import normalize_sales_dataframe
from utils.column_utils import find_column
from utils.money_utils import brl
from visual.charts import plot_bar, plot_line

st.set_page_config(page_title="Depuradora Financeira", page_icon="📊", layout="wide")


def main():
    st.title("📊 Depuradora Financeira de Planilhas Shopee")
    st.caption("Relatório único de conciliação usando Total global como base esperada de recebimento.")

    uploaded_sales = st.file_uploader("Envie a planilha .xlsx de vendas", type=["xlsx"])
    uploaded_receipts = st.file_uploader(
        "Envie uma ou mais planilhas .xlsx de recebimentos",
        type=["xlsx"],
        accept_multiple_files=True,
    )

    if not uploaded_sales:
        st.info("Envie a planilha de vendas para começar.")
        return

    try:
        sales_raw = load_sales_excel(uploaded_sales)
        ok, missing = validate_columns(sales_raw)

        if not ok:
            st.error("Faltam colunas essenciais na planilha de vendas: " + ", ".join(missing))
            st.dataframe(pd.DataFrame({"Colunas encontradas": sales_raw.columns}))
            return

        sales_df = normalize_sales_dataframe(sales_raw)
        filtered_sales = apply_filters(sales_df)
        metrics = calculate_metrics(filtered_sales)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Faturamento bruto", brl(metrics["Faturamento bruto"]))
        c2.metric("Líquido da plataforma", brl(metrics["Líquido da plataforma"]))
        c3.metric("Total de taxas", brl(metrics["Total de taxas"]))
        c4.metric("Total de descontos", brl(metrics["Total de descontos"]))

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Ticket médio", brl(metrics["Ticket médio"]))
        c6.metric("Total de pedidos", f"{int(metrics['Total de pedidos'])}")
        c7.metric("Total de itens", f"{int(metrics['Total de itens'])}")
        c8.metric("Total devolvido", brl(metrics["Total devolvido"]))

        st.subheader("Indicadores financeiros")
        indicadores = pd.DataFrame(
            [
                ("Faturamento bruto", brl(metrics["Faturamento bruto"])),
                ("Líquido da plataforma", brl(metrics["Líquido da plataforma"])),
                ("Líquido após devoluções", brl(metrics["Líquido após devoluções"])),
                ("Total devolvido", brl(metrics["Total devolvido"])),
                ("Margem líquida operacional %", f"{metrics['Margem líquida operacional %']:.2f}%"),
                ("Peso das taxas %", f"{metrics['Peso das taxas %']:.2f}%"),
                ("Peso dos descontos %", f"{metrics['Peso dos descontos %']:.2f}%"),
                ("Faturamento por item", brl(metrics["Faturamento por item"])),
                ("Comissão líquida", brl(metrics["Comissão líquida"])),
                ("Serviço líquido", brl(metrics["Serviço líquido"])),
                ("Taxa de transação", brl(metrics["Taxa de transação"])),
                ("Frete reverso", brl(metrics["Frete reverso"])),
            ],
            columns=["Indicador", "Valor"],
        )
        st.dataframe(indicadores, use_container_width=True)

        produto_col = find_column(filtered_sales, "Nome do Produto")
        valor_total_col = find_column(filtered_sales, "Valor Total")
        qtd_col = find_column(filtered_sales, "Quantidade")
        uf_col = find_column(filtered_sales, "UF")
        cidade_col = find_column(filtered_sales, "Cidade")
        pedido_col = find_column(filtered_sales, "ID do pedido")

        left, right = st.columns(2)

        with left:
            st.subheader("Top 10 produtos por faturamento")
            if produto_col and valor_total_col:
                top_prod_fat = (
                    filtered_sales.groupby(produto_col, dropna=False)[valor_total_col]
                    .sum()
                    .sort_values(ascending=False)
                    .head(10)
                )
                st.dataframe(top_prod_fat.reset_index(name="Faturamento"), use_container_width=True)
                if not top_prod_fat.empty:
                    plot_bar(top_prod_fat, "Top 10 produtos por faturamento")

            st.subheader("Vendas por UF")
            if uf_col and valor_total_col:
                vendas_uf = (
                    filtered_sales.groupby(uf_col, dropna=False)[valor_total_col]
                    .sum()
                    .sort_values(ascending=False)
                    .head(15)
                )
                st.dataframe(vendas_uf.reset_index(name="Faturamento"), use_container_width=True)
                if not vendas_uf.empty:
                    plot_bar(vendas_uf, "Vendas por UF")

        with right:
            st.subheader("Top 10 produtos por quantidade")
            if produto_col and qtd_col:
                top_prod_qtd = (
                    filtered_sales.groupby(produto_col, dropna=False)[qtd_col]
                    .sum()
                    .sort_values(ascending=False)
                    .head(10)
                )
                st.dataframe(top_prod_qtd.reset_index(name="Quantidade"), use_container_width=True)
                if not top_prod_qtd.empty:
                    plot_bar(top_prod_qtd, "Top 10 produtos por quantidade")

            st.subheader("Vendas por cidade")
            if cidade_col and valor_total_col:
                vendas_cidade = (
                    filtered_sales.groupby(cidade_col, dropna=False)[valor_total_col]
                    .sum()
                    .sort_values(ascending=False)
                    .head(15)
                )
                st.dataframe(vendas_cidade.reset_index(name="Faturamento"), use_container_width=True)
                if not vendas_cidade.empty:
                    plot_bar(vendas_cidade, "Vendas por cidade")

        st.subheader("Evolução diária")
        if "Data" in filtered_sales.columns and filtered_sales["Data"].notna().any() and valor_total_col and pedido_col:
            d1, d2 = st.columns(2)
            diaria_vendas = filtered_sales.groupby("Data")[valor_total_col].sum().sort_index()
            diaria_pedidos = filtered_sales.groupby("Data")[pedido_col].nunique().sort_index()

            with d1:
                plot_line(diaria_vendas, "Evolução diária de vendas")

            with d2:
                plot_line(diaria_pedidos, "Evolução diária de pedidos")

        st.subheader("Base de vendas tratada")
        st.dataframe(filtered_sales, use_container_width=True, height=320)

        conc_df = None
        receipt_metrics = None
        receipts_df = None

        st.divider()
        st.header("💳 Conciliação de Recebimentos")
        st.caption("Relatório único baseado no Total global da venda.")

        if uploaded_receipts:
            receipts_df = load_multiple_receipts(uploaded_receipts)

            st.subheader("Recebimentos consolidados")
            st.caption("Aqui entram juntos os pagamentos dos arquivos enviados, inclusive meses posteriores.")
            st.dataframe(receipts_df, use_container_width=True, height=250)

            conc_df = reconcile_sales_and_receipts(filtered_sales, receipts_df)
            receipt_metrics = calculate_receipt_metrics(conc_df)

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Total esperado", brl(receipt_metrics["Total esperado"]))
            r2.metric("Total recebido", brl(receipt_metrics["Total recebido"]))
            r3.metric("Saldo pendente", brl(receipt_metrics["Saldo pendente"]))
            r4.metric("Pedidos", f"{int(receipt_metrics['Qtd pedidos'])}")

            r5, r6, r7, r8 = st.columns(4)
            r5.metric("Integralmente recebidos", f"{int(receipt_metrics['Qtd integralmente recebidos'])}")
            r6.metric("Recebidos parcialmente", f"{int(receipt_metrics['Qtd recebidos parcialmente'])}")
            r7.metric("Não recebidos", f"{int(receipt_metrics['Qtd não recebidos'])}")
            r8.metric("Recebidos a maior", f"{int(receipt_metrics['Qtd recebidos a maior'])}")

            st.subheader("Resumo da conciliação")
            resumo_receb = pd.DataFrame(
                [
                    ("Total vendido", brl(receipt_metrics["Total vendido"])),
                    ("Total esperado", brl(receipt_metrics["Total esperado"])),
                    ("Total recebido", brl(receipt_metrics["Total recebido"])),
                    ("Saldo pendente", brl(receipt_metrics["Saldo pendente"])),
                    ("% conciliado", f"{receipt_metrics['% conciliado']:.2f}%"),
                    ("% não conciliado", f"{receipt_metrics['% não conciliado']:.2f}%"),
                    ("Prazo médio de recebimento", f"{receipt_metrics['Prazo médio de recebimento']:.2f} dias"),
                ],
                columns=["Indicador", "Valor"],
            )
            st.dataframe(resumo_receb, use_container_width=True)

            st.subheader("Base conciliada")
            st.dataframe(conc_df, use_container_width=True, height=400)

            st.subheader("Status da conciliação")
            status_counts = conc_df["status_conciliacao"].value_counts()
            if not status_counts.empty:
                plot_bar(status_counts, "Pedidos por status de conciliação")

            with st.expander("Ver divergências"):
                divergencias = conc_df[conc_df["status_conciliacao"] != "Recebido integralmente"].copy()
                st.dataframe(divergencias, use_container_width=True, height=320)

        excel_bytes = export_excel(filtered_sales, metrics, conc_df, receipt_metrics, receipts_df)

        st.download_button(
            label="📥 Baixar resultado em Excel",
            data=excel_bytes,
            file_name="resultado_conciliacao.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        st.error(f"Erro ao processar os arquivos: {e}")


if __name__ == "__main__":
    main()
