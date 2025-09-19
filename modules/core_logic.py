# modules/core_logic.py

import pandas as pd
from sklearn.metrics.pairwise import euclidean_distances

# Carrega os dados uma vez para serem usados pelas funções
# (Isso será melhorado no app.py passando os dataframes como argumentos)
# Por enquanto, é uma simplificação para manter o foco na lógica.

def find_product_by_name(product_name: str, portfolio: pd.DataFrame):
    """
    Busca um produto pelo nome no portfólio.
    Retorna uma lista de dicionários com os detalhes dos produtos encontrados.
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
    Obtém o preço de um produto específico.
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
    (Baseado na nossa premissa da seção de alinhamento)
    """
    if pedidos is None:
        return None
        
    # Limpa o CEP para conter apenas dígitos
    cep_cleaned = "".join(filter(str.isdigit, str(cep)))
    
    # Busca por correspondência exata no histórico
    vendor_info = pedidos[pedidos['cep'] == cep_cleaned]
    
    if not vendor_info.empty:
        # Pega o vendedor mais recorrente para aquele CEP
        vendedor = vendor_info['Cod_Vendedor_Nome'].mode()[0]
        return vendedor
        
    return "Vendedor Padrão da Matriz" # Fallback caso não encontre um vendedor para o CEP


# Adicione esta nova função em modules/core_logic.py

def recomendar_por_cultura(cultura: str, portfolio: pd.DataFrame):
    """
    Busca e retorna uma lista de produtos recomendados para uma cultura específica.
    """
    if portfolio is None:
        return []
    
    # Usamos .str.contains() para uma busca flexível (ex: "canola" na mensagem)
    # e case=False para não diferenciar maiúsculas de minúsculas.
    recomendados = portfolio[portfolio['cultura'].str.contains(cultura, case=False, na=False)]
    
    if not recomendados.empty:
        # Retorna os detalhes dos produtos encontrados como uma lista de dicionários
        return recomendados[['sku_descricao', 'N', 'P', 'K', 'segmento']].to_dict('records')
        
    return []


# Adicione esta nova função em modules/core_logic.py

def calcular_valor_total(product_name: str, quantity: int, portfolio: pd.DataFrame, precos: pd.DataFrame):
    """
    Calcula o valor total de um item do pedido.
    Retorna o valor total ou None se o produto ou preço não for encontrado.
    """
    if portfolio is None or precos is None:
        return None

    # Encontra o produto no portfólio para obter o cod_sku
    # Usamos uma busca mais exata para evitar ambiguidades no momento do cálculo
    product_info = portfolio[portfolio['sku_descricao'].str.strip().lower() == product_name.strip().lower()]
    
    if product_info.empty:
        return None # Produto não encontrado no portfólio

    cod_sku = product_info.iloc[0]['cod_sku']
    
    # Usa o cod_sku para buscar o preço
    price_info = precos[precos['cod_sku'] == cod_sku]
    
    if price_info.empty or pd.isna(price_info.iloc[0]['preco']):
        return None # Preço não encontrado ou nulo

    unit_price = float(price_info.iloc[0]['preco'])
    
    return unit_price * quantity


# Adicione esta nova função em modules/core_logic.py

def get_client_info_by_cpf_cnpj(cpf_cnpj: str, pedidos: pd.DataFrame):
    """
    Busca o nome e o último pedido de um cliente pelo CPF/CNPJ.
    """
    if pedidos is None or cpf_cnpj is None:
        return None

    # Limpa o CPF/CNPJ para conter apenas dígitos
    cpf_cnpj_cleaned = "".join(filter(str.isdigit, str(cpf_cnpj)))
    
    client_orders = pedidos[pedidos['crf_tratado'] == cpf_cnpj_cleaned]
    
    if not client_orders.empty:
        # Pega o nome do cliente (deve ser o mesmo em todos os pedidos)
        client_name = client_orders.iloc[0]['Nome_tratado']
        return client_name
        
    return None # Retorna None se o cliente não for encontrado