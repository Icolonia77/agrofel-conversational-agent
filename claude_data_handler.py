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
    Inclui validações e limpezas adicionais para maior robustez.
    """
    data_path = os.path.join(PROJECT_ROOT, "data")
    
    try:
        pedidos_path = os.path.join(data_path, "tb_pedidos_clientes_segmentos_produtos.csv")
        precos_path = os.path.join(data_path, "precos.csv")
        portfolio_path = os.path.join(data_path, "portfolio_oficial_2025_culturas.csv")

        # Carrega os arquivos
        pedidos = pd.read_csv(pedidos_path, sep=";")
        precos = pd.read_csv(precos_path, sep=";", decimal=",")
        portfolio = pd.read_csv(portfolio_path, sep=";")
        
        # --- LIMPEZA E VALIDAÇÃO DOS DADOS ---
        
        # PEDIDOS
        if 'crf_tratado' in pedidos.columns:
            pedidos['crf_tratado'] = pedidos['crf_tratado'].astype(str)
        
        # PREÇOS
        if 'preco' in precos.columns:
            # Converte preços para numérico, tratando erros
            precos['preco'] = pd.to_numeric(precos['preco'], errors='coerce')
        
        if 'cod_sku' in precos.columns:
            precos['cod_sku'] = precos['cod_sku'].astype(str).str.strip()
        
        # PORTFOLIO (mais importante para busca)
        if 'sku_descricao' in portfolio.columns:
            # Garante que é string e remove espaços extras
            portfolio['sku_descricao'] = portfolio['sku_descricao'].astype(str).str.strip()
            # Remove entradas vazias ou inválidas
            portfolio = portfolio[portfolio['sku_descricao'].notna()]
            portfolio = portfolio[portfolio['sku_descricao'] != '']
            portfolio = portfolio[portfolio['sku_descricao'] != 'nan']
        
        if 'cod_sku' in portfolio.columns:
            portfolio['cod_sku'] = portfolio['cod_sku'].astype(str).str.strip()
        
        # Converte colunas NPK para numéricas
        for col in ['N', 'P', 'K']:
            if col in portfolio.columns:
                portfolio[col] = pd.to_numeric(portfolio[col], errors='coerce').fillna(0)
        
        # Converte cultura para string e remove vazios
        if 'cultura' in portfolio.columns:
            portfolio['cultura'] = portfolio['cultura'].astype(str)
            portfolio['cultura'] = portfolio['cultura'].replace('nan', '')
        
        # Remove duplicatas do portfolio baseado em cod_sku
        if 'cod_sku' in portfolio.columns:
            portfolio = portfolio.drop_duplicates(subset=['cod_sku'], keep='first')
        
        # Log de informações úteis
        st.sidebar.success(f"✅ Dados carregados com sucesso!")
        st.sidebar.info(f"📦 {len(portfolio)} produtos no portfólio")
        st.sidebar.info(f"💰 {len(precos)} preços cadastrados")
        
        return pedidos, precos, portfolio
        
    except FileNotFoundError as e:
        st.error(f"❌ Erro ao carregar os dados: Arquivo não encontrado - {e}")
        st.error(f"📂 Caminho esperado: {data_path}")
        st.info("Verifique se os arquivos CSV estão na pasta 'data' do projeto.")
        return None, None, None
    
    except Exception as e:
        st.error(f"❌ Ocorreu um erro ao processar os arquivos CSV: {e}")
        st.error("Verifique se o separador (sep=';') e o decimal (decimal=',') estão corretos.")
        st.error("Verifique também se os nomes das colunas esperadas existem nos arquivos.")
        return None, None, None