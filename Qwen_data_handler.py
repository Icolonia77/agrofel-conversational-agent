import pandas as pd
import streamlit as st
import os

# Determina o diretório raiz do projeto de forma robusta
MODULES_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(MODULES_DIR)

@st.cache_data
def load_data():
    """
    Carrega todos os arquivos de dados necessários a partir de arquivos CSV,
    usando caminhos absolutos e tratamento seguro de tipos.
    """
    data_path = os.path.join(PROJECT_ROOT, "data")
    
    try:
        pedidos_path = os.path.join(data_path, "tb_pedidos_clientes_segmentos_produtos.csv")
        precos_path = os.path.join(data_path, "precos.csv")
        portfolio_path = os.path.join(data_path, "portfolio_oficial_2025_culturas.csv")

        # Leitura com separador ';' e decimal ',' (padrão brasileiro)
        pedidos = pd.read_csv(pedidos_path, sep=";", dtype=str)  # Tudo como string inicialmente
        precos = pd.read_csv(precos_path, sep=";", decimal=",")
        portfolio = pd.read_csv(portfolio_path, sep=";")

        # Garantir que 'crf_tratado' seja string (CPF/CNPJ)
        if 'crf_tratado' in pedidos.columns:
            pedidos['crf_tratado'] = pedidos['crf_tratado'].astype(str).str.strip()

        # Garantir que 'sku_descricao' seja string e sem valores nulos
        if 'sku_descricao' in portfolio.columns:
            portfolio['sku_descricao'] = portfolio['sku_descricao'].fillna("").astype(str).str.strip()

        # Converter colunas N, P, K para numérico (permite comparação por formulação)
        for col in ['N', 'P', 'K']:
            if col in portfolio.columns:
                portfolio[col] = pd.to_numeric(portfolio[col], errors='coerce').fillna(0).astype(int)

        # Garantir que 'preco' em precos seja numérico
        if 'preco' in precos.columns:
            precos['preco'] = pd.to_numeric(precos['preco'], errors='coerce')

        return pedidos, precos, portfolio

    except FileNotFoundError as e:
        st.error(f"Erro ao carregar os dados: Arquivo não encontrado — {e}")
        st.error("Verifique se os arquivos CSV estão na pasta 'data/'.")
        return None, None, None

    except Exception as e:
        st.error(f"Erro ao processar os arquivos CSV: {e}")
        st.error("Confirme se o separador é ';' e o decimal é ',' nos seus arquivos.")
        return None, None, None