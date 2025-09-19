# modules/data_handler.py

import pandas as pd
import streamlit as st
import os

# Pega o caminho absoluto do diretório onde o script data_handler.py está
MODULES_DIR = os.path.dirname(os.path.abspath(__file__)) 
# Sobe um nível para chegar na pasta raiz do projeto (agrofel_agent)
PROJECT_ROOT = os.path.dirname(MODULES_DIR)

@st.cache_data
def load_data():
    """
    Carrega todos os arquivos de dados necessários a partir de arquivos CSV,
    usando um caminho absoluto para evitar erros de diretório de trabalho.
    """
    # Constrói o caminho completo para a pasta 'data'
    data_path = os.path.join(PROJECT_ROOT, "data")
    
    try:
        # --- MUDANÇA 1: Nomes dos arquivos alterados para .csv ---
        pedidos_path = os.path.join(data_path, "tb_pedidos_clientes_segmentos_produtos.csv")
        precos_path = os.path.join(data_path, "precos.csv")
        portfolio_path = os.path.join(data_path, "portfolio_oficial_2025_culturas.csv")

        # --- MUDANÇA 2: Função alterada para pd.read_csv com separador de ponto e vírgula ---
        # Note o parâmetro 'sep=";"'. É comum em arquivos CSV no Brasil. 
        # Se ocorrer erro, pode ser necessário ajustá-lo (para sep="," por exemplo).
        pedidos = pd.read_csv(pedidos_path, sep=";")
        precos = pd.read_csv(precos_path, sep=";", decimal=",")
        portfolio = pd.read_csv(portfolio_path, sep=";")
        
        if 'crf_tratado' in pedidos.columns:
            pedidos['crf_tratado'] = pedidos['crf_tratado'].astype(str)
            
        return pedidos, precos, portfolio
    except FileNotFoundError as e:
        st.error(f"Erro ao carregar os dados: Arquivo não encontrado - {e}. Verifique o caminho.")
        return None, None, None
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar os arquivos CSV: {e}")
        st.error("Verifique se o separador (sep=';') e o decimal (decimal=',') estão corretos para seus arquivos.")
        return None, None, None

# # modules/data_handler.py

# import pandas as pd
# import streamlit as st
# import os

# # Usamos o cache do Streamlit para carregar os dados apenas uma vez, otimizando a performance.
# MODULES_DIR = os.path.dirname(os.path.abspath(__file__)) 
# PROJECT_ROOT = os.path.dirname(MODULES_DIR)
# @st.cache_data
# def load_data():
#     """
#     Carrega todos os arquivos de dados necessários a partir de arquivos Excel,
#     usando um caminho absoluto para evitar erros de diretório de trabalho.
#     """
#     # Constrói o caminho completo para a pasta 'data'
#     data_path = os.path.join(PROJECT_ROOT, "data")
    
#     try:
#         pedidos_path = os.path.join(data_path, "tb_pedidos_clientes_segmentos_produtos.csv",sep=";")
#         precos_path = os.path.join(data_path, "precos.csv",sep=";")
#         portfolio_path = os.path.join(data_path, "portfolio_oficial_2025_culturas.csv",sep=";")

#         pedidos = pd.read_excel(pedidos_path)
#         precos = pd.read_excel(precos_path)
#         portfolio = pd.read_excel(portfolio_path)
        
#         if 'crf_tratado' in pedidos.columns:
#             pedidos['crf_tratado'] = pedidos['crf_tratado'].astype(str)
            
#         return pedidos, precos, portfolio
#     except FileNotFoundError as e:
#         # A mensagem de erro agora mostrará o caminho completo, facilitando a depuração
#         st.error(f"Erro ao carregar os dados: Arquivo não encontrado - {e}. Verifique o caminho.")
#         return None, None, None
# # @st.cache_data
# # def load_data(data_path="data"):
# #     """
# #     Carrega todos os arquivos de dados necessários a partir de arquivos Excel.
    
# #     Args:
# #         data_path (str): O caminho para a pasta contendo os arquivos de dados.

# #     Returns:
# #         tuple: Uma tupla contendo os três DataFrames (pedidos, precos, portfolio).
# #     """
# #     try:
# #         pedidos_path = os.path.join(data_path, "tb_pedidos_clientes_segmentos_produtos.xlsx")
# #         precos_path = os.path.join(data_path, "precos.xlsx")
# #         portfolio_path = os.path.join(data_path, "portfolio_oficial_2025_culturas.xlsx")

# #         pedidos = pd.read_excel(pedidos_path)
# #         precos = pd.read_excel(precos_path)
# #         portfolio = pd.read_excel(portfolio_path)
        
# #         # Tratamento básico de dados
# #         # Garante que colunas de CPF/CNPJ sejam strings para evitar problemas de formatação
# #         if 'crf_tratado' in pedidos.columns:
# #             pedidos['crf_tratado'] = pedidos['crf_tratado'].astype(str)
            
# #         return pedidos, precos, portfolio
# #     except FileNotFoundError as e:
# #         st.error(f"Erro ao carregar os dados: Arquivo não encontrado - {e}. Verifique o caminho em 'data/'.")
# #         return None, None, None