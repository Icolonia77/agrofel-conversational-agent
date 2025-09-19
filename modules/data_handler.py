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
    data_path = os.path.join(PROJECT_ROOT, "data")
    
    try:
        pedidos_path = os.path.join(data_path, "tb_pedidos_clientes_segmentos_produtos.csv")
        precos_path = os.path.join(data_path, "precos.csv")
        portfolio_path = os.path.join(data_path, "portfolio_oficial_2025_culturas.csv")

        pedidos = pd.read_csv(pedidos_path, sep=";")
        precos = pd.read_csv(precos_path, sep=";", decimal=",")
        portfolio = pd.read_csv(portfolio_path, sep=";")
        
        # Garante que as colunas de identificação sejam tratadas como texto
        if 'crf_tratado' in pedidos.columns:
            pedidos['crf_tratado'] = pedidos['crf_tratado'].astype(str)
        
        # --- LINHA ADICIONADA AQUI ---
        # Garante que a coluna de descrição do produto seja sempre texto (string)
        if 'sku_descricao' in portfolio.columns:
            portfolio['sku_descricao'] = portfolio['sku_descricao'].astype(str)
        # -----------------------------
            
        return pedidos, precos, portfolio
    except FileNotFoundError as e:
        st.error(f"Erro ao carregar os dados: Arquivo não encontrado - {e}. Verifique o caminho.")
        return None, None, None
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar os arquivos CSV: {e}")
        st.error("Verifique se o separador (sep=';') e o decimal (decimal=',') estão corretos para seus arquivos.")
        return None, None, None