import io
from typing import Dict

import pandas as pd



def export_excel(
    df: pd.DataFrame,
    metrics: Dict[str, float],
    conc_df: pd.DataFrame | None = None,
    receipt_metrics: Dict[str, float] | None = None,
    receipts_df: pd.DataFrame | None = None,
) -> bytes:
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(list(metrics.items()), columns=["Indicador", "Valor"]).to_excel(
            writer, index=False, sheet_name="Resumo_Vendas"
        )
        df.to_excel(writer, index=False, sheet_name="Base_Filtrada")

        if receipts_df is not None and not receipts_df.empty:
            receipts_df.to_excel(writer, index=False, sheet_name="Recebimentos_Consolidados")

        if conc_df is not None and not conc_df.empty:
            conc_df.to_excel(writer, index=False, sheet_name="Conciliacao")
            divergencias = conc_df[conc_df["status_conciliacao"] != "Recebido integralmente"].copy()
            divergencias.to_excel(writer, index=False, sheet_name="Divergencias")

        if receipt_metrics is not None:
            pd.DataFrame(list(receipt_metrics.items()), columns=["Indicador", "Valor"]).to_excel(
                writer, index=False, sheet_name="Resumo_Recebimentos"
            )

    return output.getvalue()
