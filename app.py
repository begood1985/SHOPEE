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
        c1, c2, c3 = st.columns(3) 
        c1.metric("Faturamento Bruto", brl(metrics["Faturamento bruto"]))
        c2.metric("Total de Taxas", brl(metrics["Total de taxas"]))
        c3.metric("Total de Descontos", brl(metrics["Total de descontos"]))

        c_a, c_b, c_c, c_d = st.columns(4)
        c_a.metric("Ticket Médio", brl(metrics["Ticket médio"]))
        c_b.metric("Total de Pedidos", f"{int(metrics['Total de pedidos'])}")
        c_c.metric("Total de Itens", f"{int(metrics['Total de itens'])}")
        c_d.metric("Total Devolvido", brl(metrics["Total devolvido"]))

        # 3. Indicadores de Rentabilidade Estratégica
        st.subheader("Indicadores de Rentabilidade e Taxas")
        indicadores_estrategicos = pd.DataFrame([
            ("Total Esperado (Bruto - Taxas - Descontos)", brl(metrics.get("Total esperado", 0))),
            ("Líquido da Plataforma", brl(metrics["Líquido da plataforma"])),
            ("Take Rate (Carga de Taxas Real) %", f"{metrics.get('Take Rate %', 0):.2f}%"),
            ("Margem Líquida Operacional %", f"{metrics['Margem líquida operacional %']:.2f}%"),
            ("Peso dos Descontos %", f"{metrics['Peso dos descontos %']:.2f}%"),
        ], columns=["Indicador", "Valor"])
        st.dataframe(indicadores_estrategicos, use_container_width=True)

        # 4. Gráficos de Performance
        produto_col = find_column(filtered_sales, "Nome do Produto")
        valor_total_col = find_column(filtered_sales, "Valor Total")
        uf_col = find_column(filtered_sales, "UF")

        left, right = st.columns(2)
        with left:
            st.subheader("Top 10 Produtos (R$)")
            if produto_col and valor_total_col:
                top_prod_fat = filtered_sales.groupby(produto_col)[valor_total_col].sum().sort_values(ascending=False).head(10)
                plot_bar(top_prod_fat, "Faturamento por Produto")
            
        with right:
            st.subheader("Vendas por UF")
            if uf_col and valor_total_col:
                vendas_uf = filtered_sales.groupby(uf_col)[valor_total_col].sum().sort_values(ascending=False).head(15)
                plot_bar(vendas_uf, "Faturamento por Estado")

        st.subheader("Base de Vendas Tratada")
        st.dataframe(filtered_sales, use_container_width=True, height=300)

        # 5. Conciliação de Recebimentos
        st.divider()
        st.header("💳 Conciliação Financeira")
        
        if uploaded_receipts:
            receipts_df = load_multiple_receipts(uploaded_receipts)
            conc_df = reconcile_sales_and_receipts(filtered_sales, receipts_df)
            receipt_metrics = calculate_receipt_metrics(conc_df)

            # --- ATUALIZADO: Métricas de Saúde de Caixa e Divergências ---
            st.subheader("Indicadores de Repasse e Eficiência")
            r1, r2, r3, r4, r5 = st.columns(5)
            r1.metric("Total Esperado", brl(receipt_metrics.get("Total esperado", 0)))
            r2.metric("Total Recebido", brl(receipt_metrics.get("Total recebido", 0)))
            r3.metric("Total Reembolso", brl(receipt_metrics.get("Total de reembolsos", 0)))
            r4.metric("Divergência Total", brl(receipt_metrics.get("Divergência Total (Ajustes)", 0)))
            r5.metric("Eficiência %", f"{receipt_metrics.get('Eficiência de Recebimento %', 0):.2f}%")

            st.subheader("Análise de Divergências (Ganhos e Perdas)")
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Saldos Positivos (Ganhos c/ Frete/PIX)", brl(receipt_metrics.get("Saldos Positivos (Ganhos)", 0)))
            d2.metric("Saldos Negativos (Devoluções/Taxas)", brl(receipt_metrics.get("Saldos Negativos (Diferenças)", 0)))
            d3.metric("Lançados", f"{int(receipt_metrics.get('Qtd com lançamento', 0))}")
            d4.metric("Sem Lançamento", f"{int(receipt_metrics.get('Qtd sem lançamento', 0))}")
            # -------------------------------------------------------------

            # Alertas: Pedidos sem lançamento
            pedidos_sem_lancamento = conc_df[conc_df["status_conciliacao"] == "Sem lançamento"]
            if not pedidos_sem_lancamento.empty:
                st.error(f"⚠️ Detectados {len(pedidos_sem_lancamento)} pedidos sem nenhum lançamento financeiro (Sem Recebimento / Sem Reembolso).")
                with st.expander("Ver Detalhes dos Pedidos Sem Lançamento"):
                    st.dataframe(pedidos_sem_lancamento[["ID do pedido", "valor_esperado", "valor_recebido", "valor_reembolso", "status_conciliacao"]], use_container_width=True)

            st.subheader("Status dos Pedidos")
            status_counts = conc_df["status_conciliacao"].value_counts()
            plot_bar(status_counts, "Distribuição por Lançamentos")

            st.subheader("Base Conciliada (Focada em Lançamentos Financeiros)")
            # --- ATUALIZADO: A coluna 'divergencia' foi adicionada à lista de exibição ---
            colunas_exibicao = ["ID do pedido", "valor_recebido", "valor_reembolso", "status_conciliacao", "valor_esperado", "divergencia", "data_venda", "primeiro_recebimento"]
            colunas_existentes = [col for col in colunas_exibicao if col in conc_df.columns]
            
            # Formatação opcional para destacar os ganhos e perdas na tabela
            st.dataframe(conc_df[colunas_existentes], use_container_width=True, height=400)

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