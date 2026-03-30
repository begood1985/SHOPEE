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

# Configuração da página
st.set_page_config(page_title="Depuradora Financeira", page_icon="📊", layout="wide")

def main():
    st.title("📊 Depuradora Financeira de Planilhas Shopee")
    st.caption("Relatório de conciliação e rentabilidade avançada para marketplace.")

    # Upload de arquivos
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
        # 1. Carregamento e Processamento Inicial
        sales_raw = load_sales_excel(uploaded_sales)
        ok, missing = validate_columns(sales_raw)

        if not ok:
            st.error("Faltam colunas essenciais na planilha de vendas: " + ", ".join(missing))
            st.dataframe(pd.DataFrame({"Colunas encontradas": sales_raw.columns}))
            return

        sales_df = normalize_sales_dataframe(sales_raw)
        filtered_sales = apply_filters(sales_df)
        metrics = calculate_metrics(filtered_sales)

        # 2. Painel de Métricas Principais (Faturamento e Caixa)
        st.subheader("Visão Geral de Vendas")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Faturamento Bruto", brl(metrics["Faturamento bruto"]))
        c2.metric("Líquido Plataforma", brl(metrics["Líquido da plataforma"]))
        c3.metric("Total de Taxas", brl(metrics["Total de taxas"]))
        c4.metric("Total de Descontos", brl(metrics["Total de descontos"]))

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Ticket Médio", brl(metrics["Ticket médio"]))
        c6.metric("Total de Pedidos", f"{int(metrics['Total de pedidos'])}")
        c7.metric("Total de Itens", f"{int(metrics['Total de itens'])}")
        c8.metric("Total Devolvido", brl(metrics["Total devolvido"]))

        # 3. Indicadores de Rentabilidade Estratégica
        st.subheader("Indicadores de Rentabilidade e Taxas")
        # Usamos .get para evitar erro se as fórmulas ainda não estiverem no metrics.py
        indicadores_estrategicos = pd.DataFrame([
            ("Take Rate (Carga de Taxas Real) %", f"{metrics.get('Take Rate %', 0):.2f}%"),
            ("Margem de Contribuição Líquida", brl(metrics.get("Margem de Contribuição", 0))),
            ("Margem de Contribuição %", f"{metrics.get('Margem de Contribuição %', 0):.2f}%"),
            ("Margem Líquida Operacional %", f"{metrics['Margem líquida operacional %']:.2f}%"),
            ("Peso dos Descontos %", f"{metrics['Peso dos descontos %']:.2f}%"),
        ], columns=["Indicador", "Valor"])
        st.dataframe(indicadores_estrategicos, use_container_width=True)

        # 4. Gráficos de Performance
        produto_col = find_column(filtered_sales, "Nome do Produto")
        valor_total_col = find_column(filtered_sales, "Valor Total")
        qtd_col = find_column(filtered_sales, "Quantidade")
        uf_col = find_column(filtered_sales, "UF")
        cidade_col = find_column(filtered_sales, "Cidade")
        pedido_col = find_column(filtered_sales, "ID do pedido")

        left, right = st.columns(2)
        with left:
            st.subheader("Top 10 Produtos (R$)")
            if produto_col and valor_total_col:
                top_prod_fat = filtered_sales.groupby(produto_col)[valor_total_col].sum().sort_values(ascending=False).head(10)
                plot_bar(top_prod_fat, "Faturamento por Produto")
            
            st.subheader("Vendas por UF")
            if uf_col and valor_total_col:
                vendas_uf = filtered_sales.groupby(uf_col)[valor_total_col].sum().sort_values(ascending=False).head(15)
                plot_bar(vendas_uf, "Faturamento por Estado")

        with right:
            st.subheader("Top 10 Produtos (Qtd)")
            if produto_col and qtd_col:
                top_prod_qtd = filtered_sales.groupby(produto_col)[qtd_col].sum().sort_values(ascending=False).head(10)
                plot_bar(top_prod_qtd, "Quantidade por Produto")
            
            st.subheader("Vendas por Cidade")
            if cidade_col and valor_total_col:
                vendas_cidade = filtered_sales.groupby(cidade_col)[valor_total_col].sum().sort_values(ascending=False).head(15)
                plot_bar(vendas_cidade, "Faturamento por Cidade")

        st.subheader("Base de Vendas Tratada")
        st.dataframe(filtered_sales, use_container_width=True, height=300)

        # 5. Conciliação de Recebimentos
        st.divider()
        st.header("💳 Conciliação Financeira")
        
        if uploaded_receipts:
            receipts_df = load_multiple_receipts(uploaded_receipts)
            conc_df = reconcile_sales_and_receipts(filtered_sales, receipts_df)
            receipt_metrics = calculate_receipt_metrics(conc_df)

            # Métricas de Saúde de Caixa
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Eficiência de Recebimento", f"{receipt_metrics.get('Eficiência de Recebimento %', 0):.2f}%")
            r2.metric("PMR Ponderado", f"{receipt_metrics.get('PMR Ponderado (dias)', 0):.1f} dias")
            r3.metric("Saldo Pendente", brl(receipt_metrics["Saldo pendente"]))
            r4.metric("Total Recebido", brl(receipt_metrics["Total recebido"]))

            # Alertas Críticos
            divergencias_criticas = conc_df[conc_df["status_conciliacao"].str.contains("Crítica|Subpago", na=False)]
            if not divergencias_criticas.empty:
                st.error(f"⚠️ Detectados {len(divergencias_criticas)} pedidos com pagamento crítico abaixo do esperado.")
                with st.expander("Ver Detalhes das Divergências Críticas"):
                    st.dataframe(divergencias_criticas, use_container_width=True)

            st.subheader("Status dos Pedidos")
            status_counts = conc_df["status_conciliacao"].value_counts()
            plot_bar(status_counts, "Distribuição por Status de Conciliação")

            st.subheader("Base Conciliada Completa")
            st.dataframe(conc_df, use_container_width=True, height=400)

            # Exportação
            excel_bytes = export_excel(filtered_sales, metrics, conc_df, receipt_metrics, receipts_df)
            st.download_button(
                label="📥 Baixar Relatório Completo (Excel)",
                data=excel_bytes,
                file_name="conciliacao_financeira_shopee.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.warning("Aguardando planilhas de recebimentos para iniciar a conciliação.")

    except Exception as e:
        st.error(f"Erro no processamento: {e}")

if __name__ == "__main__":
    main()