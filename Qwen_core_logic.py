import pandas as pd
import re
from sklearn.metrics.pairwise import euclidean_distances
from fuzzywuzzy import process

def normalize_npk_string(text: str):
    """
    Extrai e normaliza uma string de NPK de entradas como:
    '10-20-20', '10 20 20', '15.23-30', etc.
    Retorna (N, P, K) como inteiros ou None se inválido.
    """
    # Remove tudo exceto dígitos, pontos e hífens
    cleaned = re.sub(r'[^\d\-\.]', ' ', text)
    # Substitui múltiplos espaços por um único
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Tenta padrões comuns
    patterns = [
        r'(\d+)\s*-\s*(\d+)\s*-\s*(\d+)',  # 10-20-20
        r'(\d+)\s+(\d+)\s+(\d+)',           # 10 20 20
        r'(\d+)\.(\d+)\s*-\s*(\d+)',        # 15.23-30 → (15, 23, 30)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, cleaned)
        if match:
            try:
                n = int(float(match.group(1)))
                p = int(float(match.group(2)))
                k = int(float(match.group(3)))
                return (n, p, k)
            except:
                continue
    return None

def find_product_by_name_or_npk(query: str, portfolio: pd.DataFrame):
    """
    Busca produtos por nome COMERCIAL (fuzzy) OU por formulação NPK.
    Retorna lista de produtos encontrados.
    """
    if portfolio is None or portfolio.empty:
        return []

    results = []

    # 1. Tenta interpretar como NPK
    npk_tuple = normalize_npk_string(query)
    if npk_tuple:
        n, p, k = npk_tuple
        # Busca exata por NPK
        exact_match = portfolio[
            (portfolio['N'] == n) & 
            (portfolio['P'] == p) & 
            (portfolio['K'] == k)
        ]
        if not exact_match.empty:
            results.extend(exact_match[['cod_sku', 'sku_descricao', 'N', 'P', 'K']].to_dict('records'))
            return results  # Retorna imediatamente se encontrar exato

    # 2. Busca por nome comercial (fuzzy)
    query_clean = str(query).strip()
    all_names = portfolio['sku_descricao'].astype(str).tolist()
    
    # Fuzzy match com threshold alto
    matches = process.extractBests(query_clean, all_names, score_cutoff=80, limit=3)
    
    for name, score in matches:
        product_row = portfolio[portfolio['sku_descricao'] == name].iloc[0]
        results.append({
            'cod_sku': product_row['cod_sku'],
            'sku_descricao': name,
            'N': product_row['N'],
            'P': product_row['P'],
            'K': product_row['K']
        })
    
    return results

def find_similar_products_by_npk_vector(n: int, p: int, k: int, portfolio: pd.DataFrame, top_k: int = 3):
    """
    Encontra produtos com NPK mais próximos de (n, p, k) usando distância euclidiana.
    """
    if portfolio is None or portfolio.empty:
        return []
    
    ref_vector = [[n, p, k]]
    portfolio_vectors = portfolio[['N', 'P', 'K']].fillna(0).values
    
    distances = euclidean_distances(ref_vector, portfolio_vectors)[0]
    portfolio = portfolio.copy()
    portfolio['dist'] = distances
    similar = portfolio.sort_values("dist").head(top_k)
    
    return similar[['cod_sku', 'sku_descricao', 'N', 'P', 'K']].to_dict('records')

def get_product_price(cod_sku: str, precos: pd.DataFrame):
    if precos is None:
        return None
    price_info = precos[precos['cod_sku'] == cod_sku]
    if not price_info.empty:
        return price_info.iloc[0].to_dict()
    return None

def find_vendor_by_cep(cep: str, pedidos: pd.DataFrame):
    if pedidos is None:
        return None
    cep_cleaned = "".join(filter(str.isdigit, str(cep)))
    if len(cep_cleaned) != 8:
        return None
    vendor_info = pedidos[pedidos['cep'] == cep_cleaned]
    if not vendor_info.empty:
        vendedor = vendor_info['Cod_Vendedor_Nome'].mode()[0]
        return vendedor
    return "Vendedor Padrão da Matriz"

def get_client_info_by_cpf_cnpj(cpf_cnpj: str, pedidos: pd.DataFrame):
    if pedidos is None or cpf_cnpj is None:
        return None
    cpf_cnpj_cleaned = "".join(filter(str.isdigit, str(cpf_cnpj)))
    client_orders = pedidos[pedidos['crf_tratado'] == cpf_cnpj_cleaned]
    if not client_orders.empty:
        client_name = client_orders.iloc[0]['Nome_tratado']
        return client_name
    return None

def recomendar_por_cultura(cultura: str, portfolio: pd.DataFrame):
    if portfolio is None:
        return []
    recomendados = portfolio[portfolio['cultura'].str.contains(cultura, case=False, na=False)]
    if not recomendados.empty:
        return recomendados[['sku_descricao', 'N', 'P', 'K']].to_dict('records')
    return []

def calcular_valor_total(cod_sku: str, quantity: int, precos: pd.DataFrame):
    """
    Calcula o valor total usando cod_sku (mais confiável).
    """
    if precos is None:
        return None
    price_info = precos[precos['cod_sku'] == cod_sku]
    if price_info.empty or pd.isna(price_info.iloc[0]['preco']):
        return None
    unit_price = float(price_info.iloc[0]['preco'])
    return unit_price * quantity