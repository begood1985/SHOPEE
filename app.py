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

# Configuração da página para máxima visibilidade
st.set_page_config(page_title="Auditoria Shopee Pro", page_icon="💰", layout="wide")

def main():
    st.title("💰 Auditoria Financeira Avançada Shopee")
    st.markdown("---")

    # Sidebar para Uploads e Organização
    with st.sidebar:
        st.header("📂 Entrada de Dados")
        uploaded_sales = st.file_uploader("1. Planilha de Vendas (.xlsx)", type=["xlsx"])
        uploaded_receipts = st.file_uploader("2. Planilhas de Recebimentos (.xlsx)", type=["xlsx"], accept_multiple_files=True)
        st.info("💡 Dica: Use as planilhas oficiais exportadas da Central do Vendedor.")

    if not uploaded_sales:
        st.warning("⚠️ Por favor, carregue a planilha de vendas na barra lateral para começar.")
        return

    try:
        # 1. Processamento de Dados
        sales_raw = load_sales_excel(uploaded_sales)
        ok, missing = validate_columns(sales_raw)
        if not ok:
            st.error(f"❌ Colunas ausentes: {', '.join(missing)}")
            return

        sales_df = normalize_sales_dataframe(sales_raw)
        filtered_sales = apply_filters(sales_df)
        metrics = calculate_metrics(filtered_sales)

        # ==========================================
        # ABA 1: PERFORMANCE DE VENDAS (SAÚDE DO NEGÓCIO)
        # ==========================================
        st.header("📈 Desempenho Comercial")
        
        with st.container():
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("GMV (Volume Total)", brl(metrics.get("Volume Transacionado (GMV)", 0)), 
                          help="Tudo o que o cliente pagou (Preço + Frete).")
            with c2:
                st.metric("Faturamento Líquido (Produtos)", brl(metrics.get("Faturamento bruto", 0)),
                          help="Valor real dos seus produtos vendidos.")
            with c3:
                st.metric("Total de Taxas", f"- {brl(metrics.get('Total de taxas', 0))}", 
                          delta_color="inverse", help="Comissões e fretes retidos pela Shopee.")

        st.markdown("#### 🎯 Rentabilidade Estratégica")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Take Rate (Taxas)", f"{metrics.get('Take Rate %', 0):.2f}%")
        m2.metric("Margem Operacional", f"{metrics.get('Margem líquida operacional %', 0):.2f}%")
        m3.metric("Ticket Médio", brl(metrics.get("Ticket médio", 0)))
        m4.metric("Total de Pedidos", f"{int(metrics.get('Total de pedidos', 0))} un")

        st.markdown("---")
        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Top 10 Produtos")
            prod_col = find_column(filtered_sales, "Nome do Produto")
            val_col = find_column(filtered_sales, "Valor Total")
            if prod_col and val_col:
                top_data = filtered_sales.groupby(prod_col)[val_col].sum().sort_values(ascending=False).head(10)
                plot_bar(top_data, "Ranking por Faturamento")
        with g2:
            st.subheader("Concentração por Estado")
            uf_col = find_column(filtered_sales, "UF")
            if uf_col and val_col:
                uf_data = filtered_sales.groupby(uf_col)[val_col].sum().sort_values(ascending=False)
                plot_bar(uf_data, "Vendas por UF")

        # ==========================================
        # ABA 2: AUDITORIA FINANCEIRA (CONCILIAÇÃO)
        # ==========================================
        st.divider()
        st.header("💳 Auditoria de Caixa (Conciliação Financeira)")

        if uploaded_receipts:
            receipts_df = load_multiple_receipts(uploaded_receipts)
            conc_df = reconcile_sales_and_receipts(filtered_sales, receipts_df)
            r_metrics = calculate_receipt_metrics(conc_df)

            # Destaque visual do Reembolso e Eficiência
            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Total Esperado", brl(r_metrics.get('Total esperado', 0)))
            a2.metric("Total Recebido", brl(r_metrics.get('Total recebido', 0)))
            a3.metric("Total de Reembolsos", brl(r_metrics.get('Total de reembolsos', 0)), delta_color="inverse")
            a4.metric("Eficiência de Repasse", f"{r_metrics.get('Eficiência de Recebimento %', 0):.2f}%")
            st.metric("Integridade do Processamento", r_metrics.get("Integridade do Processamento", "N/A"))
            st.caption(
                "Divergência Contábil (com reembolso): "
                f"{brl(r_metrics.get('Divergência Total (Ajustes)', 0))} | "
                "Divergência Operacional (sem reembolso): "
                f"{brl(r_metrics.get('Divergência Operacional (sem reembolso)', 0))}"
            )

            # Prova real por pedido: bloqueia exportação se houver divergência matemática.
            integrity_ok = True
            divergent_ids = []
            if "check_integridade" in conc_df.columns:
                invalid_rows = conc_df[~conc_df["check_integridade"].fillna(False)]
                if not invalid_rows.empty:
                    integrity_ok = False
                    divergent_ids = invalid_rows["ID do pedido"].astype(str).tolist()
                    divergent_ids = sorted(set([x for x in divergent_ids if x.strip() != ""]))
                    st.error(
                        "❌ Prova Real falhou para os pedidos: "
                        + ", ".join(divergent_ids[:50])
                        + (" ..." if len(divergent_ids) > 50 else "")
                    )
            if r_metrics.get("Integridade do Processamento") == "Falha":
                integrity_ok = False
                st.error(
                    "❌ Auditoria de fluxo de caixa inconsistente: "
                    "Total Recebido != Total Esperado + Total Reembolsos + Divergência Total."
                )

            with st.expander("📝 Entenda a Prova Real do seu Caixa", expanded=True):
                col_math_1, col_math_2 = st.columns(2)
                with col_math_1:
                    st.write("**Fluxo de Fechamento:**")
                    st.write(f"(+) Valor Esperado de Vendas: `{brl(r_metrics.get('Total esperado', 0))}`")
                    st.write(f"(+) Reembolsos (valor negativo): `{brl(r_metrics.get('Total de reembolsos', 0))}`")
                    st.write(f"(+) Divergência Residual (Ajustes): `{brl(r_metrics.get('Divergência Total (Ajustes)', 0))}`")
                    st.write(f"**(=) TOTAL REAL RECEBIDO: {brl(r_metrics.get('Total recebido', 0))}**")
                
                with col_math_2:
                    # --- ATUALIZADO: Detalhamento com Subgrupos Visuais ---
                    st.write("**Detalhamento de Divergências:**")
                    
                    # Subgrupo de Ganhos
                    st.write(f"🟢 **Ganhos c/ Frete/PIX: {brl(r_metrics.get('Saldos Positivos (Ganhos)', 0))}**")
                    st.caption("↳ Ajustes de frete, comissão e incentivos PIX.")
                    
                    st.markdown("---")
                    
                    # Subgrupo de Diferenças Negativas
                    st.write(f"🔴 **Diferenças Negativas: {brl(r_metrics.get('Saldos Negativos (Diferenças)', 0))}**")
                    st.write(f"↳ Reembolsos Diretos: `{brl(r_metrics.get('Total de reembolsos', 0))}`")
                    st.write(f"↳ Outros Ajustes: `{brl(r_metrics.get('Outras Diferenças Negativas', 0))}`")
                    st.write(
                        f"↳ Visão Operacional (sem reembolso): "
                        f"`{brl(r_metrics.get('Divergência Operacional (sem reembolso)', 0))}`"
                    )
                    st.caption("↳ Outros Ajustes já excluem reembolsos para evitar dupla contagem.")
                    
                    st.markdown("---")
                    st.write(f"📊 Pedidos Auditados: `{int(r_metrics.get('Qtd pedidos', 0))}`")
                    # -----------------------------------------------------

            with st.expander("🔎 Relatório Completo de Outros Ajustes", expanded=False):
                # Decomposicao:
                # gap_faturamento = recebido - esperado
                # gap_faturamento = reembolso + divergencia_residual
                aux = conc_df.copy()
                aux["divergencia"] = pd.to_numeric(aux["divergencia"], errors="coerce").fillna(0.0)
                aux["valor_reembolso"] = pd.to_numeric(aux["valor_reembolso"], errors="coerce").fillna(0.0)
                aux["valor_recebido"] = pd.to_numeric(aux["valor_recebido"], errors="coerce").fillna(0.0)
                aux["valor_esperado"] = pd.to_numeric(aux["valor_esperado"], errors="coerce").fillna(0.0)
                aux["gap_faturamento"] = aux["valor_recebido"] - aux["valor_esperado"]
                aux["outros_ajustes"] = aux["divergencia"]
                aux["impacto_reembolso"] = aux["valor_reembolso"]

                neg_gap = aux[aux["gap_faturamento"] < -0.01]["gap_faturamento"].sum()
                neg_reembolso = aux[aux["impacto_reembolso"] < -0.01]["impacto_reembolso"].sum()
                neg_outros = aux[aux["outros_ajustes"] < -0.01]["outros_ajustes"].sum()

                x1, x2, x3 = st.columns(3)
                x1.metric("Gap Negativo (Recebido - Esperado)", brl(neg_gap))
                x2.metric("Parcela de Reembolsos", brl(neg_reembolso))
                x3.metric("Parcela de Outros Ajustes", brl(neg_outros))

                st.caption(
                    "Outros Ajustes = divergência residual após considerar reembolsos. "
                    "Ou seja, é o que sobra do gap que não é explicado nem por recebimento nem por reembolso."
                )

                top_outros = aux[aux["outros_ajustes"] < -0.01].copy()
                if not top_outros.empty:
                    top_outros = top_outros.sort_values("outros_ajustes").head(30)
                    cols_show = [
                        "ID do pedido",
                        "valor_esperado",
                        "valor_recebido",
                        "valor_reembolso",
                        "outros_ajustes",
                        "divergencia",
                        "status_conciliacao",
                    ]
                    cols_show = [c for c in cols_show if c in top_outros.columns]
                    st.write("**Top pedidos com maiores Outros Ajustes (negativos):**")
                    st.dataframe(top_outros[cols_show], use_container_width=True)
                else:
                    st.success("Não há outros ajustes negativos relevantes no período filtrado.")

            # Exportação
            st.divider()
            if integrity_ok:
                excel_bytes = export_excel(filtered_sales, metrics, conc_df, r_metrics, receipts_df)
                st.download_button(
                    label="📥 Baixar Auditoria Completa em Excel",
                    data=excel_bytes,
                    file_name=f"auditoria_shopee_{pd.Timestamp.now().strftime('%d_%m_%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            else:
                st.warning("Exportação bloqueada até corrigir as divergências de integridade.")

        else:
            st.warning("🧐 Aguardando planilhas de recebimentos para gerar a auditoria.")

    except Exception as e:
        st.error(f"🚨 Erro no Processamento: {str(e)}")

if __name__ == "__main__":
    main()
