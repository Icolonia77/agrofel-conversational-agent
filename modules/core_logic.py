# modules/core_logic.py

import pandas as pd
from sklearn.metrics.pairwise import euclidean_distances

def find_product_by_name(product_name: str, portfolio: pd.DataFrame):
    """
    Busca um produto pelo nome no portfólio de forma flexível.
    """
    if portfolio is None:
        return []
    result = portfolio[portfolio['sku_descricao'].str.contains(product_name, case=False, na=False)]
    if not result.empty:
        return result[['cod_sku', 'sku_descricao', 'N', 'P', 'K']].to_dict('records')
    return []

def find_similar_products_by_npk(cod_sku_ref: str, portfolio: pd.DataFrame):
    """
    Encontra os 3 produtos mais similares a um produto de referência com base no NPK.
    """
    if portfolio is None or cod_sku_ref not in portfolio['cod_sku'].values:
        return []
    ref_product = portfolio[portfolio['cod_sku'] == cod_sku_ref]
    if ref_product.empty:
        return []
    ref_vector = ref_product[['N', 'P', 'K']].fillna(0).values
    other_products = portfolio[portfolio['cod_sku'] != cod_sku_ref].copy()
    other_vectors = other_products[['N', 'P', 'K']].fillna(0).values
    if len(other_vectors) == 0:
        return []
    distances = euclidean_distances(ref_vector, other_vectors)[0]
    other_products['dist'] = distances
    similar = other_products.sort_values("dist").head(3)
    return similar[['cod_sku', 'sku_descricao', 'N', 'P', 'K']].to_dict('records')

def get_product_price(cod_sku: str, precos: pd.DataFrame):
    """
    Obtém o preço de um produto específico pelo seu cod_sku.
    """
    if precos is None:
        return None
    price_info = precos[precos['cod_sku'] == cod_sku]
    if not price_info.empty:
        return price_info.iloc[0].to_dict()
    return None

def find_vendor_by_cep(cep: str, pedidos: pd.DataFrame):
    """
    Encontra o vendedor associado a um CEP com base em pedidos históricos.
    """
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
    """
    Busca o nome de um cliente pelo CPF/CNPJ.
    """
    if pedidos is None or cpf_cnpj is None:
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
    """
    if portfolio is None:
        return []
    recomendados = portfolio[portfolio['cultura'].str.contains(cultura, case=False, na=False)]
    if not recomendados.empty:
        return recomendados[['sku_descricao', 'N', 'P', 'K', 'segmento']].to_dict('records')
    return []

def calcular_valor_total(product_name: str, quantity: int, portfolio: pd.DataFrame, precos: pd.DataFrame):
    """
    Calcula o valor total de um item do pedido.
    Retorna o valor total ou None se o produto ou preço não for encontrado.
    """
    if portfolio is None or precos is None:
        return None

    # Encontra o produto no portfólio para obter o cod_sku
    # CORREÇÃO: Sintaxe correta para aplicar múltiplos métodos de string (.str.strip().str.lower())
    product_info = portfolio[portfolio['sku_descricao'].str.strip().str.lower() == product_name.strip().lower()]
    
    if product_info.empty:
        return None # Produto não encontrado no portfólio

    cod_sku = product_info.iloc[0]['cod_sku']
    
    # Usa o cod_sku para buscar o preço
    price_info = precos[precos['cod_sku'] == cod_sku]
    
    if price_info.empty or pd.isna(price_info.iloc[0]['preco']):
        return None # Preço não encontrado ou nulo

    unit_price = float(price_info.iloc[0]['preco'])
    
    return unit_price * quantity


