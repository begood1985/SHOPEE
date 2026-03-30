COMO EXECUTAR

1. Extraia o ZIP.
2. Abra o terminal dentro da pasta shopee_finance_app.
3. Instale as dependências:
   pip install -r requirements.txt
4. Rode o app:
   streamlit run app.py

ESTRUTURA
- app.py -> interface principal
- config/ -> constantes
- utils/ -> funções auxiliares
- data_loader/ -> leitura das planilhas
- processing/ -> normalização, métricas, filtros e conciliação
- visual/ -> gráficos
- export/ -> exportação do Excel
