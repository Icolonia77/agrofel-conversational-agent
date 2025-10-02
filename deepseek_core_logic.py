import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import euclidean_distances
from sklearn.feature_extraction.text import TfidfVectorizer
import re

def find_product_by_name(product_name: str, portfolio: pd.DataFrame):
    """
    Busca um produto pelo nome no portfólio de forma FLEXÍVEL e INTELIGENTE.
    Melhoria: Busca por similaridade textual e por componentes NPK.
    """
    if portfolio is None or portfolio.empty:
        return []
    
    # Garantir que a coluna sku_descricao seja string
    portfolio = portfolio.copy()
    portfolio['sku_descricao'] = portfolio['sku_descricao'].astype(str)
    
    # 1. Busca exata (case insensitive)
    exact_match = portfolio[
        portfolio['sku_descricao'].str.strip().str.lower() == product_name.strip().lower()
    ]
    if not exact_match.empty:
        return exact_match[['cod_sku', 'sku_descricao', 'N', 'P', 'K', 'cultura']].to_dict('records')
    
    # 2. Busca por substring
    substring_match = portfolio[
        portfolio['sku_descricao'].str.lower().str.contains(product_name.lower(), na=False)
    ]
    if not substring_match.empty:
        return substring_match[['cod_sku', 'sku_descricao', 'N', 'P', 'K', 'cultura']].to_dict('records')
    
    # 3. Busca por NPK (formato 10.20.20 ou 10-20-20)
    npk_match = re.search(r'(\d+)[\.\-](\d+)[\.\-](\d+)', product_name)
    if npk_match:
        n_val, p_val, k_val = map(int, npk_match.groups())
        npk_match_products = portfolio[
            (portfolio['N'] == n_val) & 
            (portfolio['P'] == p_val) & 
            (portfolio['K'] == k_val)
        ]
        if not npk_match_products.empty:
            return npk_match_products[['cod_sku', 'sku_descricao', 'N', 'P', 'K', 'cultura']].to_dict('records')
    
    # 4. Busca por números NPK soltos
    numbers = re.findall(r'\d+', product_name)
    if len(numbers) >= 3:
        n_val, p_val, k_val = map(int, numbers[:3])
        npk_match_products = portfolio[
            (portfolio['N'] == n_val) & 
            (portfolio['P'] == p_val) & 
            (portfolio['K'] == k_val)
        ]
        if not npk_match_products.empty:
            return npk_match_products[['cod_sku', 'sku_descricao', 'N', 'P', 'K', 'cultura']].to_dict('records')
    
    return []

def find_similar_products_by_npk(target_n: float, target_p: float, target_k: float, portfolio: pd.DataFrame, top_n: int = 3):
    """
    Encontra os produtos mais similares com base na composição NPK.
    MELHORIA: Aceita valores NPK diretamente, não precisa de cod_sku de referência.
    """
    if portfolio is None or portfolio.empty:
        return []
    
    # Criar vetor de referência
    ref_vector = np.array([[target_n, target_p, target_k]])
    
    # Preparar vetores dos outros produtos
    portfolio_clean = portfolio.dropna(subset=['N', 'P', 'K']).copy()
    if portfolio_clean.empty:
        return []
    
    other_vectors = portfolio_clean[['N', 'P', 'K']].values
    
    # Calcular distâncias euclidianas
    distances = euclidean_distances(ref_vector, other_vectors)[0]
    portfolio_clean['similarity_score'] = 1 / (1 + distances)  # Converter distância para similaridade
    
    # Ordenar por similaridade e pegar os top_n
    similar_products = portfolio_clean.sort_values("similarity_score", ascending=False).head(top_n)
    
    return similar_products[['cod_sku', 'sku_descricao', 'N', 'P', 'K', 'cultura', 'similarity_score']].to_dict('records')

def find_products_by_flexible_search(search_term: str, portfolio: pd.DataFrame, top_n: int = 5):
    """
    Busca FLEXÍVEL por produtos usando múltiplas estratégias.
    NOVA FUNÇÃO: Combina busca textual e por NPK.
    """
    if portfolio is None or portfolio.empty:
        return []
    
    portfolio = portfolio.copy()
    portfolio['sku_descricao'] = portfolio['sku_descricao'].astype(str)
    
    results = []
    
    # 1. Busca textual direta
    direct_matches = portfolio[
        portfolio['sku_descricao'].str.lower().str.contains(search_term.lower(), na=False)
    ]
    if not direct_matches.empty:
        for _, product in direct_matches.head(top_n).iterrows():
            results.append({
                'cod_sku': product['cod_sku'],
                'sku_descricao': product['sku_descricao'],
                'N': product['N'],
                'P': product['P'],
                'K': product['K'],
                'cultura': product.get('cultura', ''),
                'match_type': 'textual_direct',
                'confidence': 1.0
            })
    
    # 2. Busca por NPK se o termo contém números
    npk_pattern = re.search(r'(\d+)[\.\-]?(\d+)[\.\-]?(\d+)', search_term)
    if npk_pattern:
        n_val, p_val, k_val = map(int, npk_pattern.groups())
        npk_matches = portfolio[
            (portfolio['N'] == n_val) & 
            (portfolio['P'] == p_val) & 
            (portfolio['K'] == k_val)
        ]
        if not npk_matches.empty:
            for _, product in npk_matches.iterrows():
                results.append({
                    'cod_sku': product['cod_sku'],
                    'sku_descricao': product['sku_descricao'],
                    'N': product['N'],
                    'P': product['P'],
                    'K': product['K'],
                    'cultura': product.get('cultura', ''),
                    'match_type': 'npk_exact',
                    'confidence': 0.9
                })
    
    # 3. Busca por similaridade de NPK se encontrou números
    numbers = re.findall(r'\d+', search_term)
    if len(numbers) >= 3:
        n_val, p_val, k_val = map(int, numbers[:3])
        similar_npk = find_similar_products_by_npk(n_val, p_val, k_val, portfolio, top_n=3)
        for product in similar_npk:
            results.append({
                'cod_sku': product['cod_sku'],
                'sku_descricao': product['sku_descricao'],
                'N': product['N'],
                'P': product['P'],
                'K': product['K'],
                'cultura': product.get('cultura', ''),
                'match_type': 'npk_similar',
                'confidence': product.get('similarity_score', 0.7)
            })
    
    # Remover duplicatas e ordenar por confiança
    seen_skus = set()
    unique_results = []
    for result in sorted(results, key=lambda x: x['confidence'], reverse=True):
        if result['cod_sku'] not in seen_skus:
            seen_skus.add(result['cod_sku'])
            unique_results.append(result)
    
    return unique_results[:top_n]

def get_product_price(cod_sku: str, precos: pd.DataFrame):
    """
    Obtém o preço de um produto específico pelo seu cod_sku.
    """
    if precos is None or precos.empty:
        return None
    price_info = precos[precos['cod_sku'] == cod_sku]
    if not price_info.empty:
        return price_info.iloc[0].to_dict()
    return None

def find_vendor_by_cep(cep: str, pedidos: pd.DataFrame):
    """
    Encontra o vendedor associado a um CEP com base em pedidos históricos.
    """
    if pedidos is None or pedidos.empty:
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
    """
    Busca o nome de um cliente pelo CPF/CNPJ.
    """
    if pedidos is None or pedidos.empty or cpf_cnpj is None:
        return None
    cpf_cnpj_cleaned = "".join(filter(str.isdigit, str(cpf_cnpj)))
    client_orders = pedidos[pedidos['crf_tratado'] == cpf_cnpj_cleaned]
    if not client_orders.empty:
        client_name = client_orders.iloc[0]['Nome_tratado']
        return client_name
    return None

def recomendar_por_cultura(cultura: str, portfolio: pd.DataFrame):
    """
    Busca e retorna uma lista de produtos recomendados para uma cultura específica.
    MELHORIA: Busca mais flexível por cultura.
    """
    if portfolio is None or portfolio.empty:
        return []
    
    # Busca flexível por cultura
    recomendados = portfolio[
        portfolio['cultura'].str.contains(cultura, case=False, na=False) |
        portfolio['cultura'].str.contains(cultura.split()[0] if ' ' in cultura else cultura, case=False, na=False)
    ]
    
    if not recomendados.empty:
        return recomendados[['sku_descricao', 'N', 'P', 'K', 'cultura']].to_dict('records')
    return []

def calcular_valor_total(product_name: str, quantity: int, portfolio: pd.DataFrame, precos: pd.DataFrame):
    """
    Calcula o valor total de um item do pedido.
    MELHORIA: Usa busca flexível para encontrar o produto.
    """
    if portfolio is None or portfolio.empty or precos is None or precos.empty:
        return None

    # Usa busca flexível para encontrar o produto
    product_matches = find_products_by_flexible_search(product_name, portfolio, top_n=1)
    
    if not product_matches:
        return None  # Produto não encontrado

    cod_sku = product_matches[0]['cod_sku']
    
    # Usa o cod_sku para buscar o preço
    price_info = precos[precos['cod_sku'] == cod_sku]
    
    if price_info.empty or pd.isna(price_info.iloc[0]['preco']):
        return None  # Preço não encontrado ou nulo

    unit_price = float(price_info.iloc[0]['preco'])
    
    return unit_price * quantity

def suggest_alternative_products(search_term: str, portfolio: pd.DataFrame, precos: pd.DataFrame, max_suggestions: int = 3):
    """
    SUGESTÃO DE PRODUTOS ALTERNATIVOS quando o produto exato não é encontrado.
    NOVA FUNÇÃO: Oferece alternativas antes de sugerir encaminhamento.
    """
    if portfolio is None or portfolio.empty:
        return []
    
    # Busca flexível para encontrar produtos relacionados
    suggestions = find_products_by_flexible_search(search_term, portfolio, top_n=max_suggestions)
    
    # Adiciona informações de preço
    for suggestion in suggestions:
        price_info = get_product_price(suggestion['cod_sku'], precos)
        if price_info:
            suggestion['preco'] = price_info.get('preco')
        else:
            suggestion['preco'] = None
    
    return suggestions