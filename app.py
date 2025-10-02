import streamlit as st
import os
import re
import pandas as pd
from dotenv import load_dotenv
from modules.data_handler import load_data
from modules.core_logic import (
    find_product_by_name,
    recomendar_por_cultura,
    calcular_valor_total,
    find_alternatives_by_npk,
    find_similar_products_by_npk,
    extract_npk_from_text,
    find_vendor_by_cep,
    get_product_price,
)
from modules.llm_handler import ConversationalAgent

# --- Configuração Inicial ---
st.set_page_config(page_title="Agente Agrofel", page_icon="🤖")
st.title("🤖 Agente de Vendas Agrofel")
st.markdown("Bem-vindo! Sou seu assistente virtual para pedidos de fertilizantes.")

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("Chave de API do Google não encontrada! Por favor, configure o arquivo .env.")
    st.stop()

# Carregamento de dados
pedidos, precos, portfolio = load_data()
if portfolio is not None:
    culturas_disponiveis = portfolio['cultura'].dropna().unique().tolist()
else:
    culturas_disponiveis = []

# --- Inicialização do Estado da Sessão ---
if "agent" not in st.session_state:
    st.session_state.agent = ConversationalAgent(api_key=GOOGLE_API_KEY)
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Olá! Como posso ajudar você a encontrar o fertilizante ideal hoje?"}
    ]
if "carrinho" not in st.session_state:
    st.session_state.carrinho = []
if "aguardando_cep" not in st.session_state:
    st.session_state.aguardando_cep = False
if "aguardando_quantidade" not in st.session_state:
    st.session_state.aguardando_quantidade = False
if "aguardando_confirmacao_carrinho" not in st.session_state:
    st.session_state.aguardando_confirmacao_carrinho = False
if "vendedor_atual" not in st.session_state:
    st.session_state.vendedor_atual = None
if "ultimo_produto_cod_sku" not in st.session_state:
    st.session_state.ultimo_produto_cod_sku = None
if "ultimo_produto_nome" not in st.session_state:
    st.session_state.ultimo_produto_nome = None
if "ultimo_produto_quantidade" not in st.session_state:
    st.session_state.ultimo_produto_quantidade = None
if "ultimo_produto_valor" not in st.session_state:
    st.session_state.ultimo_produto_valor = None

# --- Exibição do Chat ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Funções Helper ---
def extract_quantity_from_text(text: str):
    """Extrai quantidade de um texto."""
    patterns = [
        r'(\d+)\s*(?:toneladas?|tons?|t\b)',
        r'(\d+)\s*(?:unidades?|bags?|caixas?|sacos?|kg)',
        r'(?:quero|preciso|gostaria)\s*(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None

def parse_order_request(text: str):
    """Tenta extrair quantidade e nome de produto."""
    patterns = [
        r'(\d+)\s*(?:unidades?|bags?|caixas?|sacos?|kg|toneladas?)\s*(?:de|do)\s*(.+)',
        r'(?:quero|preciso|gostaria|queria)\s*(?:de)?\s*(\d+)\s*(?:unidades?|bags?|caixas?|toneladas?|sacos?)\s*(?:de|do)?\s*(.+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            quantity = int(match.group(1))
            product_name = match.group(2).strip()
            product_name = re.sub(r'\s*(por favor|obrigado|obrigada)$', '', product_name, flags=re.IGNORECASE)
            if len(product_name) >= 3:
                return quantity, product_name
    
    return None, None

def is_positive_confirmation(text: str) -> bool:
    """Verifica se é uma confirmação positiva (sim, ok, pode, etc)."""
    confirmations = [
        'sim', 'yes', 'ok', 'pode', 'podes', 'confirmo', 'confirmar', 
        'isso', 'correto', 'certo', 'exato', 'perfeito', 'adicionar',
        'adicione', 'quero', 'aceito'
    ]
    text_lower = text.lower().strip()
    words = text_lower.split()
    if len(words) <= 5:
        return any(conf in text_lower for conf in confirmations)
    return False

def is_greeting(text: str) -> bool:
    """Verifica se a mensagem é uma saudação."""
    greetings = ['oi', 'olá', 'ola', 'bom dia', 'boa tarde', 'boa noite', 'hey', 'e ai', 'eai']
    text_lower = text.lower().strip()
    return any(greeting in text_lower for greeting in greetings)

def is_vendor_request(text: str) -> bool:
    """Verifica se o cliente está EXPLICITAMENTE pedindo para falar com vendedor."""
    vendor_keywords = [
        'falar com vendedor', 'falar com atendente', 'falar com humano',
        'quero vendedor', 'preciso vendedor', 'encaminhar para vendedor',
        'encaminhar pedido', 'finalizar pedido', 'fechar pedido',
        'falar com comercial', 'falar com suporte', 'encaminhar para o vendedor'
    ]
    text_lower = text.lower().strip()
    return any(keyword in text_lower for keyword in vendor_keywords)

def is_similar_products_request(text: str) -> bool:
    """Verifica se o cliente está pedindo produtos similares."""
    similar_keywords = [
        'similar', 'similares', 'parecido', 'parecidos', 'alternativa', 'alternativas',
        'outro', 'outros', 'mais opções', 'mais opcoes', 'outras opções', 'outras opcoes',
        'equivalente', 'equivalentes', 'substituto', 'substitutos', 'lista', 'liste', 'mostre'
    ]
    text_lower = text.lower().strip()
    return any(keyword in text_lower for keyword in similar_keywords)

def is_quantity_response(text: str) -> bool:
    """Verifica se o cliente está respondendo com uma quantidade."""
    quantity_patterns = [
        r'\d+\s*(?:toneladas?|tons?|unidades?|bags?|caixas?|sacos?|kg)',
        r'(?:quero|preciso|gostaria)\s*\d+',
    ]
    text_lower = text.lower().strip()
    return any(re.search(pattern, text_lower, re.IGNORECASE) for pattern in quantity_patterns)

def is_add_to_cart(text: str) -> bool:
    """Verifica se o cliente quer adicionar ao carrinho."""
    cart_keywords = ['adicionar', 'add', 'carrinho', 'incluir', 'colocar no carrinho', 'adicione']
    text_lower = text.lower().strip()
    return any(keyword in text_lower for keyword in cart_keywords)

def is_valid_cep(text: str) -> bool:
    """Verifica se o texto contém um CEP válido (8 dígitos)."""
    cep_cleaned = "".join(filter(str.isdigit, text))
    return len(cep_cleaned) == 8

def extract_cep(text: str) -> str:
    """Extrai o CEP de uma string."""
    cep_cleaned = "".join(filter(str.isdigit, text))
    if len(cep_cleaned) == 8:
        return cep_cleaned
    return None

def contains_cep(text: str) -> bool:
    """Verifica se o texto contém um CEP."""
    cep_pattern = r'\b\d{5}-?\d{3}\b'
    return re.search(cep_pattern, text) is not None

# --- LÓGICA DE CHAT APRIMORADA ---
if prompt := st.chat_input("Digite o nome de um produto, cultura ou sua dúvida..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analisando seu pedido..."):
            contexto_para_llm = "Contexto geral da conversa."
            
            # --- VERIFICA SE ESTÁ AGUARDANDO CONFIRMAÇÃO PARA ADICIONAR AO CARRINHO ---
            if st.session_state.aguardando_confirmacao_carrinho and is_positive_confirmation(prompt):
                item_info = {
                    'produto': st.session_state.ultimo_produto_nome,
                    'quantidade': st.session_state.ultimo_produto_quantidade,
                    'valor': st.session_state.ultimo_produto_valor,
                    'cod_sku': st.session_state.ultimo_produto_cod_sku
                }
                st.session_state.carrinho.append(item_info)
                
                # Monta resumo do carrinho
                resumo_carrinho = "Carrinho atualizado:\n"
                for i, item in enumerate(st.session_state.carrinho):
                    resumo_carrinho += f"{i+1}. {item['produto']} - {item['quantidade']} ton"
                    if item['valor']:
                        resumo_carrinho += f" (R$ {item['valor']:.2f})"
                    resumo_carrinho += "\n"
                
                contexto_para_llm = (
                    f"Cliente confirmou adição de {st.session_state.ultimo_produto_quantidade} toneladas "
                    f"de '{st.session_state.ultimo_produto_nome}' ao carrinho. "
                    f"\n\n{resumo_carrinho}\n"
                    f"Total de itens: {len(st.session_state.carrinho)}. "
                    "Confirme adição com sucesso, mostre resumo do carrinho, "
                    "pergunte se quer adicionar mais produtos. **NÃO oferecer vendedor**."
                )
                
                st.session_state.aguardando_confirmacao_carrinho = False
            
            # --- ADICIONAR AO CARRINHO EXPLICITAMENTE ---
            elif is_add_to_cart(prompt) and st.session_state.ultimo_produto_nome:
                item_info = {
                    'produto': st.session_state.ultimo_produto_nome,
                    'quantidade': st.session_state.ultimo_produto_quantidade,
                    'valor': st.session_state.ultimo_produto_valor,
                    'cod_sku': st.session_state.ultimo_produto_cod_sku
                }
                st.session_state.carrinho.append(item_info)
                
                contexto_para_llm = (
                    f"Cliente adicionou '{st.session_state.ultimo_produto_nome}' ao carrinho. "
                    f"Total: {len(st.session_state.carrinho)} itens. "
                    "Confirme e pergunte se quer mais. **NÃO oferecer vendedor**."
                )
            
            # --- VERIFICA SE ESTÁ AGUARDANDO QUANTIDADE ---
            elif st.session_state.aguardando_quantidade and is_quantity_response(prompt):
                quantity = extract_quantity_from_text(prompt)
                
                if quantity and st.session_state.ultimo_produto_cod_sku:
                    total_value, cod_sku, nome_real, unit_price = calcular_valor_total(
                        st.session_state.ultimo_produto_nome,
                        quantity,
                        portfolio,
                        precos
                    )
                    
                    if total_value is not None and unit_price is not None:
                        st.session_state.ultimo_produto_quantidade = quantity
                        st.session_state.ultimo_produto_valor = total_value
                        st.session_state.aguardando_confirmacao_carrinho = True
                        
                        similares = find_similar_products_by_npk(
                            st.session_state.ultimo_produto_cod_sku, 
                            portfolio, 
                            top_n=3
                        )
                        
                        contexto_para_llm = (
                            f"Cliente: {quantity} toneladas de '{st.session_state.ultimo_produto_nome}'. "
                            f"Preço unitário: R$ {unit_price:.2f}. Total: R$ {total_value:.2f}. "
                        )
                        
                        if similares:
                            contexto_para_llm += f"\n\nHá {len(similares)} similares:\n"
                            for s in similares:
                                npk_str = f"{s.get('N', 'N/A')}-{s.get('P', 'N/A')}-{s.get('K', 'N/A')}"
                                contexto_para_llm += f"- {s['sku_descricao']} (NPK: {npk_str})\n"
                        
                        contexto_para_llm += (
                            "\n\nConfirme produto/quantidade. "
                            f"Informe preço unitário R$ {unit_price:.2f} e total R$ {total_value:.2f}. "
                            "AVISE: valor SEM FRETE. "
                            "Pergunte se adiciona ao carrinho. "
                        )
                        
                        if similares:
                            contexto_para_llm += "Mencione similares disponíveis. "
                        
                        contexto_para_llm += "**NÃO oferecer vendedor**."
                    else:
                        st.session_state.ultimo_produto_quantidade = quantity
                        st.session_state.ultimo_produto_valor = None
                        st.session_state.aguardando_confirmacao_carrinho = True
                        
                        contexto_para_llm = (
                            f"Cliente: {quantity} toneladas de '{st.session_state.ultimo_produto_nome}'. "
                            "Sem preço - cotação personalizada. "
                            "Confirme, pergunte se adiciona ao carrinho. "
                            "**NÃO oferecer vendedor ainda**."
                        )
                    
                    st.session_state.aguardando_quantidade = False
            
            # --- VERIFICA SE CLIENTE PEDIU PRODUTOS SIMILARES ---
            elif is_similar_products_request(prompt):
                produto_referenciado = None
                text_lower = prompt.lower()
                
                # Procura produtos no carrinho mencionados explicitamente
                for item in st.session_state.carrinho:
                    produto_nome = item['produto'].lower()
                    palavras_chave = [p for p in re.split(r'[\s\-/]+', produto_nome) if len(p) > 3 and not p.isdigit()]
                    
                    for palavra in palavras_chave:
                        if palavra in text_lower:
                            produto_referenciado = item
                            break
                    
                    if produto_referenciado:
                        break
                
                if produto_referenciado:
                    cod_sku_ref = produto_referenciado['cod_sku']
                    nome_ref = produto_referenciado['produto']
                    
                    similares = find_similar_products_by_npk(cod_sku_ref, portfolio, top_n=5)
                    
                    if similares:
                        contexto_para_llm = (
                            f"Cliente pediu similares especificamente ao **{nome_ref}** (que está no carrinho). "
                            f"Encontrei {len(similares)} produtos similares:\n\n"
                        )
                        for s in similares:
                            npk_str = f"{s.get('N', 'N/A')}-{s.get('P', 'N/A')}-{s.get('K', 'N/A')}"
                            contexto_para_llm += f"- {s['sku_descricao']} (NPK: {npk_str})\n"
                        
                        contexto_para_llm += (
                            f"\n\n**CRÍTICO**: Cliente pediu similares ao **{nome_ref}**, NÃO ao último produto.\n"
                            "\nSua resposta deve:\n"
                            f"1. Deixar MUITO CLARO: 'Produtos similares ao **{nome_ref}**:'\n"
                            "2. Apresentar os produtos com NPKs\n"
                            "3. Perguntar se quer cotação\n"
                            "4. **NÃO oferecer vendedor**\n"
                            "5. NUNCA sugerir produtos fora da lista"
                        )
                    else:
                        contexto_para_llm = f"Sem similares ao '{nome_ref}'. Informe e ofereça outras opções."
                
                elif st.session_state.ultimo_produto_cod_sku:
                    similares = find_similar_products_by_npk(
                        st.session_state.ultimo_produto_cod_sku, 
                        portfolio, 
                        top_n=5
                    )
                    
                    if similares:
                        contexto_para_llm = (
                            f"Cliente pediu similares (ref: '{st.session_state.ultimo_produto_nome}'). "
                            f"Encontrei {len(similares)} produtos:\n\n"
                        )
                        for s in similares:
                            npk_str = f"{s.get('N', 'N/A')}-{s.get('P', 'N/A')}-{s.get('K', 'N/A')}"
                            contexto_para_llm += f"- {s['sku_descricao']} (NPK: {npk_str})\n"
                        
                        contexto_para_llm += "\n\nApresente produtos. **NÃO oferecer vendedor**."
                    else:
                        contexto_para_llm = "Sem similares. Sugira buscar por cultura."
                else:
                    contexto_para_llm = "Cliente pediu similares mas sem referência. Pergunte qual produto."
            
            # --- VERIFICA SE ESTÁ AGUARDANDO CEP ---
            elif st.session_state.aguardando_cep:
                if is_valid_cep(prompt):
                    cep = extract_cep(prompt)
                    vendedor = find_vendor_by_cep(cep, pedidos)
                    
                    if vendedor and vendedor != "Vendedor Padrão da Matriz":
                        st.session_state.vendedor_atual = vendedor
                        contexto_para_llm = f"CEP {cep}. Vendedor: **{vendedor}**. Confirme encaminhamento."
                    else:
                        st.session_state.vendedor_atual = "Equipe Comercial"
                        contexto_para_llm = f"CEP {cep} sem vendedor específico. Equipe comercial."
                    
                    st.session_state.aguardando_cep = False
                else:
                    contexto_para_llm = "CEP inválido. Peça 8 dígitos."
            
            # --- VERIFICA SE CLIENTE QUER VENDEDOR ---
            elif is_vendor_request(prompt):
                if contains_cep(prompt):
                    cep = extract_cep(prompt)
                    vendedor = find_vendor_by_cep(cep, pedidos)
                    if vendedor and vendedor != "Vendedor Padrão da Matriz":
                        st.session_state.vendedor_atual = vendedor
                        contexto_para_llm = f"Cliente quer vendedor, CEP {cep}. Vendedor: **{vendedor}**."
                    else:
                        contexto_para_llm = f"Cliente quer vendedor, CEP {cep}, sem específico."
                else:
                    contexto_para_llm = "Cliente quer vendedor. Peça CEP."
                    st.session_state.aguardando_cep = True
            
            # --- SAUDAÇÃO ---
            elif is_greeting(prompt) and len(prompt.split()) <= 3:
                contexto_para_llm = "Cliente cumprimentou. Responda amigavelmente."
            
            # --- PEDIDO COM QUANTIDADE ---
            else:
                quantity, product_name = parse_order_request(prompt)
                
                if quantity and product_name:
                    # Se há produto aguardando confirmação, adiciona automaticamente ao carrinho
                    if st.session_state.aguardando_confirmacao_carrinho and st.session_state.ultimo_produto_nome:
                        item_info = {
                            'produto': st.session_state.ultimo_produto_nome,
                            'quantidade': st.session_state.ultimo_produto_quantidade,
                            'valor': st.session_state.ultimo_produto_valor,
                            'cod_sku': st.session_state.ultimo_produto_cod_sku
                        }
                        st.session_state.carrinho.append(item_info)
                        st.session_state.aguardando_confirmacao_carrinho = False
                    
                    total_value, cod_sku, nome_real, unit_price = calcular_valor_total(
                        product_name, quantity, portfolio, precos
                    )
                    
                    if total_value is not None and unit_price is not None:
                        st.session_state.ultimo_produto_cod_sku = cod_sku
                        st.session_state.ultimo_produto_nome = nome_real
                        st.session_state.ultimo_produto_quantidade = quantity
                        st.session_state.ultimo_produto_valor = total_value
                        st.session_state.aguardando_confirmacao_carrinho = True
                        
                        contexto_para_llm = (
                            f"Cliente: {quantity} de '{product_name}'. Produto: '{nome_real}'. "
                            f"Preço: R$ {unit_price:.2f}. Total: R$ {total_value:.2f} (SEM FRETE). "
                            "Informe valores, pergunte se adiciona. **NÃO oferecer vendedor**."
                        )
                    elif nome_real:
                        st.session_state.ultimo_produto_cod_sku = cod_sku
                        st.session_state.ultimo_produto_nome = nome_real
                        st.session_state.ultimo_produto_quantidade = quantity
                        st.session_state.ultimo_produto_valor = None
                        st.session_state.aguardando_confirmacao_carrinho = True
                        contexto_para_llm = f"'{nome_real}' sem preço. Cotação personalizada. Pergunte se adiciona."
                    else:
                        produtos_similares = find_product_by_name(product_name, portfolio, similarity_threshold=0.4)
                        if produtos_similares:
                            contexto_para_llm = f"'{product_name}' não encontrado. Alternativas:\n"
                            for p in produtos_similares[:3]:
                                contexto_para_llm += f"- {p['sku_descricao']}\n"
                            contexto_para_llm += "Pergunte se é um desses."
                        else:
                            contexto_para_llm = "Produto não encontrado. Peça mais detalhes."
                
                else:
                    # Busca SEM quantidade
                    # Se há produto aguardando confirmação, adiciona ao carrinho primeiro
                    if st.session_state.aguardando_confirmacao_carrinho and st.session_state.ultimo_produto_nome:
                        item_info = {
                            'produto': st.session_state.ultimo_produto_nome,
                            'quantidade': st.session_state.ultimo_produto_quantidade,
                            'valor': st.session_state.ultimo_produto_valor,
                            'cod_sku': st.session_state.ultimo_produto_cod_sku
                        }
                        st.session_state.carrinho.append(item_info)
                        st.session_state.aguardando_confirmacao_carrinho = False
                    
                    produtos_encontrados = find_product_by_name(prompt, portfolio, similarity_threshold=0.5)
                    
                    if produtos_encontrados:
                        st.session_state.ultimo_produto_cod_sku = produtos_encontrados[0]['cod_sku']
                        st.session_state.ultimo_produto_nome = produtos_encontrados[0]['sku_descricao']
                        st.session_state.aguardando_quantidade = True
                        
                        # Informa que produto anterior foi adicionado
                        if len(st.session_state.carrinho) > 0:
                            ultimo_item = st.session_state.carrinho[-1]
                            contexto_para_llm = (
                                f"Adicionei automaticamente ao carrinho: "
                                f"{ultimo_item['produto']} ({ultimo_item['quantidade']} ton).\n\n"
                                f"Agora, cliente buscou '{prompt}'. Produtos encontrados:\n"
                            )
                        else:
                            contexto_para_llm = f"Cliente buscou '{prompt}'. Produtos:\n"
                        
                        for p in produtos_encontrados[:5]:
                            npk_str = f"{p.get('N', 'N/A')}-{p.get('P', 'N/A')}-{p.get('K', 'N/A')}"
                            contexto_para_llm += f"- {p['sku_descricao']} (NPK: {npk_str})\n"
                        contexto_para_llm += "\nPERGUNTAR quantidade. **NÃO oferecer vendedor**."
                    
                    else:
                        # Busca por cultura
                        cultura_encontrada = None
                        for cultura in culturas_disponiveis:
                            if str(cultura).lower() in prompt.lower():
                                cultura_encontrada = cultura
                                break
                        
                        if cultura_encontrada:
                            recomendacoes = recomendar_por_cultura(cultura_encontrada, portfolio)
                            if recomendacoes:
                                contexto_para_llm = f"Cultura '{cultura_encontrada}'. Produtos:\n"
                                for r in recomendacoes[:5]:
                                    contexto_para_llm += f"- {r['sku_descricao']}\n"
                                contexto_para_llm += "Apresente opções."
            
            # Envia para o LLM
            resposta_llm = st.session_state.agent.send_message(prompt, contexto_para_llm)
            st.markdown(resposta_llm)
    
    st.session_state.messages.append({"role": "assistant", "content": resposta_llm})

# --- Sidebar ---
with st.sidebar:
    st.header("ℹ️ Informações")
    
    if st.session_state.carrinho:
        st.header("🛒 Carrinho")
        total_geral = 0
        for i, item in enumerate(st.session_state.carrinho):
            produto = item['produto']
            quantidade = item.get('quantidade', 'N/A')
            valor = item.get('valor')
            
            st.write(f"**{i+1}. {produto}**")
            st.write(f"   Qtd: {quantidade} ton")
            if valor:
                st.write(f"   Valor: R$ {valor:.2f}")
                total_geral += valor
            else:
                st.write(f"   Valor: Cotação")
            st.write("---")
        
        if total_geral > 0:
            st.write(f"**Total (sem frete): R$ {total_geral:.2f}**")
        st.write(f"**{len(st.session_state.carrinho)} itens**")
    
    if st.session_state.ultimo_produto_nome:
        st.info(f"📦 Último: {st.session_state.ultimo_produto_nome}")
    
    if st.session_state.aguardando_quantidade:
        st.warning("⏳ Aguardando quantidade...")
    
    if st.session_state.aguardando_confirmacao_carrinho:
        st.warning("⏳ Aguardando confirmação...")
    
    if st.session_state.aguardando_cep:
        st.warning("⏳ Aguardando CEP...")
    
    if st.session_state.vendedor_atual:
        st.success(f"👤 Vendedor: {st.session_state.vendedor_atual}")
    
    if st.button("🗑️ Limpar tudo"):
        st.session_state.messages = [
            {"role": "assistant", "content": "Olá! Como posso ajudar você a encontrar o fertilizante ideal hoje?"}
        ]
        st.session_state.carrinho = []
        st.session_state.aguardando_cep = False
        st.session_state.aguardando_quantidade = False
        st.session_state.aguardando_confirmacao_carrinho = False
        st.session_state.vendedor_atual = None
        st.session_state.ultimo_produto_cod_sku = None
        st.session_state.ultimo_produto_nome = None
        st.session_state.ultimo_produto_quantidade = None
        st.session_state.ultimo_produto_valor = None
        st.rerun()

# import streamlit as st
# import os
# import re
# from dotenv import load_dotenv
# from modules.data_handler import load_data
# from modules.core_logic import (
#     find_product_by_name,
#     recomendar_por_cultura,
#     calcular_valor_total,
#     find_alternatives_by_npk,
#     find_similar_products_by_npk,
#     extract_npk_from_text,
#     find_vendor_by_cep,
# )
# from modules.llm_handler import ConversationalAgent

# # --- Configuração Inicial ---
# st.set_page_config(page_title="Agente Agrofel", page_icon="🤖")
# st.title("🤖 Agente de Vendas Agrofel")
# st.markdown("Bem-vindo! Sou seu assistente virtual para pedidos de fertilizantes.")

# load_dotenv()
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# if not GOOGLE_API_KEY:
#     st.error("Chave de API do Google não encontrada! Por favor, configure o arquivo .env.")
#     st.stop()

# # Carregamento de dados
# pedidos, precos, portfolio = load_data()
# if portfolio is not None:
#     culturas_disponiveis = portfolio['cultura'].dropna().unique().tolist()
# else:
#     culturas_disponiveis = []

# # --- Inicialização do Estado da Sessão ---
# if "agent" not in st.session_state:
#     st.session_state.agent = ConversationalAgent(api_key=GOOGLE_API_KEY)
# if "messages" not in st.session_state:
#     st.session_state.messages = [
#         {"role": "assistant", "content": "Olá! Como posso ajudar você a encontrar o fertilizante ideal hoje?"}
#     ]
# if "carrinho" not in st.session_state:
#     st.session_state.carrinho = []
# if "aguardando_cep" not in st.session_state:
#     st.session_state.aguardando_cep = False

# # --- Exibição do Chat ---
# for message in st.session_state.messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])

# # --- Função Helper para Parse do Pedido ---
# def parse_order_request(text: str):
#     """
#     Tenta extrair uma quantidade e um nome de produto de uma string.
#     Ex: "Quero 20 unidades de 09 25 15 C/MICRO" -> (20, "09 25 15 C/MICRO")
#     """
#     # Padrões comuns de pedido
#     patterns = [
#         r'(\d+)\s*(?:unidades?|bags?|caixas?|sacos?|kg)?\s*(?:de|do)?\s*(.+)',
#         r'(?:quero|preciso|gostaria)\s*(?:de)?\s*(\d+)\s*(?:unidades?|bags?|caixas?)?\s*(?:de|do)?\s*(.+)',
#     ]
    
#     for pattern in patterns:
#         match = re.search(pattern, text, re.IGNORECASE)
#         if match:
#             quantity = int(match.group(1))
#             product_name = match.group(2).strip()
#             # Remove palavras desnecessárias do final
#             product_name = re.sub(r'\s*(por favor|obrigado|obrigada)$', '', product_name, flags=re.IGNORECASE)
#             if len(product_name) >= 3:
#                 return quantity, product_name
    
#     return None, None

# def is_greeting(text: str) -> bool:
#     """Verifica se a mensagem é uma saudação."""
#     greetings = ['oi', 'olá', 'ola', 'bom dia', 'boa tarde', 'boa noite', 'hey', 'e ai', 'eai']
#     text_lower = text.lower().strip()
#     return any(greeting in text_lower for greeting in greetings)

# def is_vendor_request(text: str) -> bool:
#     """Verifica se o cliente está pedindo para falar com vendedor."""
#     vendor_keywords = [
#         'vendedor', 'atendente', 'humano', 'pessoa', 'representante',
#         'falar com alguém', 'falar com alguem', 'atendimento', 'suporte',
#         'comercial', 'vendas'
#     ]
#     text_lower = text.lower().strip()
#     return any(keyword in text_lower for keyword in vendor_keywords)

# def is_valid_cep(text: str) -> bool:
#     """Verifica se o texto contém um CEP válido (8 dígitos)."""
#     cep_cleaned = "".join(filter(str.isdigit, text))
#     return len(cep_cleaned) == 8

# def extract_cep(text: str) -> str:
#     """Extrai o CEP de uma string."""
#     cep_cleaned = "".join(filter(str.isdigit, text))
#     if len(cep_cleaned) == 8:
#         return cep_cleaned
#     return None

# # --- LÓGICA DE CHAT APRIMORADA ---
# if prompt := st.chat_input("Digite o nome de um produto, cultura ou sua dúvida..."):
#     st.session_state.messages.append({"role": "user", "content": prompt})
#     with st.chat_message("user"):
#         st.markdown(prompt)

#     with st.chat_message("assistant"):
#         with st.spinner("Analisando seu pedido..."):
#             contexto_para_llm = "Contexto geral da conversa."
            
#             # --- VERIFICA SE ESTÁ AGUARDANDO CEP ---
#             if st.session_state.aguardando_cep:
#                 if is_valid_cep(prompt):
#                     cep = extract_cep(prompt)
#                     vendedor = find_vendor_by_cep(cep, pedidos)
                    
#                     if vendedor and vendedor != "Vendedor Padrão da Matriz":
#                         contexto_para_llm = (
#                             f"O cliente forneceu o CEP {cep} e encontrei o vendedor responsável: '{vendedor}'. "
#                             "\n\nSua resposta deve:\n"
#                             "1. Informar o nome do vendedor responsável pela região\n"
#                             "2. Explicar que em breve o vendedor entrará em contato\n"
#                             "3. Perguntar se há mais alguma coisa que possa ajudar enquanto isso\n"
#                             "4. Agradecer pela preferência"
#                         )
#                     else:
#                         contexto_para_llm = (
#                             f"O cliente forneceu o CEP {cep}, mas não encontrei um vendedor específico para esta região. "
#                             "\n\nSua resposta deve:\n"
#                             "1. Informar que vamos encaminhar para o vendedor da matriz\n"
#                             "2. Explicar que um vendedor entrará em contato em breve\n"
#                             "3. Perguntar se há mais alguma informação que possa anotar para o vendedor\n"
#                             "4. Agradecer pela preferência"
#                         )
                    
#                     # Reseta o estado de aguardar CEP
#                     st.session_state.aguardando_cep = False
#                 else:
#                     contexto_para_llm = (
#                         "O cliente forneceu algo que não parece ser um CEP válido (deve ter 8 dígitos). "
#                         "\n\nSua resposta deve:\n"
#                         "1. Informar educadamente que o CEP precisa ter 8 dígitos\n"
#                         "2. Dar um exemplo: 01310-100 ou 01310100\n"
#                         "3. Pedir novamente o CEP correto"
#                     )
            
#             # --- VERIFICA SE CLIENTE QUER FALAR COM VENDEDOR ---
#             elif is_vendor_request(prompt):
#                 contexto_para_llm = (
#                     "O cliente pediu para falar com um vendedor. "
#                     "\n\nSua resposta deve:\n"
#                     "1. Confirmar que vai encaminhar para um vendedor\n"
#                     "2. Solicitar o CEP do cliente para identificar o vendedor responsável pela região\n"
#                     "3. Explicar que com o CEP você consegue direcionar para o vendedor correto\n"
#                     "4. Ser amigável e prestativo"
#                 )
#                 # Ativa o estado de aguardar CEP
#                 st.session_state.aguardando_cep = True
            
#             # --- FLUXO INTELIGENTE DE CONTEXTO (RESTANTE DO CÓDIGO) ---
            
#             # 1. Verifica se é uma saudação simples
#             elif is_greeting(prompt) and len(prompt.split()) <= 3:
#                 contexto_para_llm = (
#                     "O cliente acabou de cumprimentar você. "
#                     "Responda de forma amigável e pergunte como pode ajudar (ex: procura por um produto específico, "
#                     "uma cultura, ou cotação)."
#                 )
            
#             # 2. Tenta identificar um PEDIDO DE COTAÇÃO (ex: "20 unidades de...")
#             else:
#                 quantity, product_name = parse_order_request(prompt)
                
#                 if quantity and product_name:
#                     # Cliente está pedindo cotação
#                     total_value, cod_sku, nome_real = calcular_valor_total(product_name, quantity, portfolio, precos)
                    
#                     if total_value is not None:
#                         # SUCESSO: Produto encontrado e preço calculado
#                         contexto_para_llm = (
#                             f"O cliente pediu cotação de {quantity} unidades de '{product_name}'. "
#                             f"Encontrei o produto '{nome_real}' (código: {cod_sku}). "
#                             f"O valor total é R$ {total_value:.2f}. "
#                             "\n\nSua resposta deve:\n"
#                             "1. Confirmar o produto encontrado (nome correto)\n"
#                             "2. Informar o valor total calculado\n"
#                             "3. AVISAR CLARAMENTE que este valor NÃO INCLUI FRETE\n"
#                             "4. Perguntar se deseja adicionar ao carrinho ou falar com um vendedor para cotação completa"
#                         )
                    
#                     elif nome_real:
#                         # Produto encontrado mas SEM PREÇO
#                         contexto_para_llm = (
#                             f"O cliente pediu cotação de '{product_name}'. "
#                             f"Encontrei o produto '{nome_real}', mas não há preço disponível no sistema. "
#                             "\n\nSua resposta deve:\n"
#                             "1. Informar que o produto foi encontrado\n"
#                             "2. Explicar que o preço não está disponível no momento\n"
#                             "3. Oferecer conectar com um vendedor para obter cotação"
#                         )
                    
#                     else:
#                         # Produto NÃO ENCONTRADO - buscar alternativas
#                         produtos_similares = find_product_by_name(product_name, portfolio, similarity_threshold=0.4)
#                         alternativas_npk = find_alternatives_by_npk(product_name, portfolio)
                        
#                         if produtos_similares or alternativas_npk:
#                             # Encontrou produtos similares
#                             contexto_para_llm = (
#                                 f"O cliente pediu '{product_name}', mas não encontrei produto com este nome exato. "
#                                 "Porém, encontrei produtos similares:\n\n"
#                             )
                            
#                             if produtos_similares:
#                                 contexto_para_llm += "--- PRODUTOS COM NOME SIMILAR ---\n"
#                                 for p in produtos_similares[:3]:
#                                     contexto_para_llm += f"- {p['sku_descricao']} (NPK: {p.get('N', 'N/A')}-{p.get('P', 'N/A')}-{p.get('K', 'N/A')})\n"
                            
#                             if alternativas_npk:
#                                 contexto_para_llm += "\n--- PRODUTOS COM NPK SIMILAR ---\n"
#                                 for p in alternativas_npk[:3]:
#                                     contexto_para_llm += f"- {p['sku_descricao']} (NPK: {p.get('N', 'N/A')}-{p.get('P', 'N/A')}-{p.get('K', 'N/A')})\n"
                            
#                             contexto_para_llm += (
#                                 "\n\nSua resposta deve:\n"
#                                 "1. Informar que não encontrou produto com o nome exato\n"
#                                 "2. Apresentar as alternativas encontradas de forma clara e organizada\n"
#                                 "3. Perguntar se alguma dessas opções é o que o cliente procura\n"
#                                 "4. NÃO oferecer encaminhamento para vendedor ainda (deixe o cliente avaliar as opções primeiro)"
#                             )
#                         else:
#                             # Nenhuma alternativa encontrada
#                             contexto_para_llm = (
#                                 f"O cliente pediu '{product_name}', mas não encontrei este produto nem similares. "
#                                 "\n\nSua resposta deve:\n"
#                                 "1. Informar educadamente que não encontrou o produto\n"
#                                 "2. Pedir para verificar a escrita ou fornecer mais detalhes (ex: NPK, marca, aplicação)\n"
#                                 "3. Sugerir que pode buscar por cultura específica se ele souber\n"
#                                 "4. Oferecer ajuda para encontrar o produto ideal"
#                             )

#                 else:
#                     # 3. Não é cotação - verificar se é busca por PRODUTO direto
#                     produtos_encontrados = find_product_by_name(prompt, portfolio, similarity_threshold=0.5)
                    
#                     if produtos_encontrados:
#                         # Encontrou produto(s) com o nome
#                         contexto_para_llm = (
#                             f"O cliente procurou por '{prompt}' e encontrei os seguintes produtos:\n\n"
#                         )
#                         for p in produtos_encontrados[:5]:
#                             npk_str = f"{p.get('N', 'N/A')}-{p.get('P', 'N/A')}-{p.get('K', 'N/A')}"
#                             contexto_para_llm += f"- {p['sku_descricao']} (NPK: {npk_str})\n"
                        
#                         contexto_para_llm += (
#                             "\n\nSua resposta deve:\n"
#                             "1. Apresentar os produtos encontrados de forma clara\n"
#                             "2. Perguntar se o cliente quer informações sobre algum deles\n"
#                             "3. Perguntar se deseja fazer uma cotação"
#                         )
                    
#                     else:
#                         # 4. Verificar se é busca por CULTURA
#                         cultura_encontrada = None
#                         for cultura in culturas_disponiveis:
#                             if str(cultura).lower() in prompt.lower():
#                                 cultura_encontrada = cultura
#                                 break
                        
#                         if cultura_encontrada:
#                             recomendacoes = recomendar_por_cultura(cultura_encontrada, portfolio)
#                             if recomendacoes:
#                                 contexto_para_llm = (
#                                     f"O cliente perguntou sobre a cultura '{cultura_encontrada}'. "
#                                     f"Encontrei {len(recomendacoes)} produtos recomendados:\n\n"
#                                 )
#                                 for r in recomendacoes[:5]:
#                                     npk_str = f"{r.get('N', 'N/A')}-{r.get('P', 'N/A')}-{r.get('K', 'N/A')}"
#                                     contexto_para_llm += f"- {r['sku_descricao']} (NPK: {npk_str})\n"
                                
#                                 contexto_para_llm += (
#                                     "\n\nSua resposta deve:\n"
#                                     "1. Apresentar os produtos para esta cultura de forma organizada\n"
#                                     "2. Perguntar se o cliente quer mais detalhes sobre algum produto específico\n"
#                                     "3. Oferecer fazer uma cotação"
#                                 )
            
#             # Envia para o LLM com o contexto construído
#             resposta_llm = st.session_state.agent.send_message(prompt, contexto_para_llm)
#             st.markdown(resposta_llm)
    
#     st.session_state.messages.append({"role": "assistant", "content": resposta_llm})

# # --- Sidebar com informações úteis ---
# with st.sidebar:
#     st.header("ℹ️ Dicas de uso")
#     st.markdown("""
#     **Como usar o Agente:**
#     - Digite o nome do produto ou NPK (ex: "Aspire" ou "10 20 20")
#     - Peça cotação: "20 unidades de Aspire"
#     - Busque por cultura: "produtos para café"
#     - Fale com vendedor: "Quero falar com um vendedor"
    
#     **O agente pode:**
#     ✅ Encontrar produtos similares
#     ✅ Calcular valores (sem frete)
#     ✅ Recomendar por cultura
#     ✅ Sugerir alternativas
#     ✅ Encaminhar para vendedor por CEP
#     """)
    
#     if st.session_state.carrinho:
#         st.header("🛒 Carrinho")
#         for item in st.session_state.carrinho:
#             st.write(f"- {item}")
    
#     # Mostra status de aguardando CEP
#     if st.session_state.aguardando_cep:
#         st.warning("⏳ Aguardando CEP do cliente...")
    
#     if st.button("🗑️ Limpar conversa"):
#         st.session_state.messages = [
#             {"role": "assistant", "content": "Olá! Como posso ajudar você a encontrar o fertilizante ideal hoje?"}
#         ]
#         st.session_state.carrinho = []
#         st.session_state.aguardando_cep = False
#         st.rerun()


# import streamlit as st
# import os
# import re
# from dotenv import load_dotenv
# from modules.data_handler import load_data
# from modules.core_logic import (
#     find_product_by_name,
#     recomendar_por_cultura,
#     calcular_valor_total,
#     find_alternatives_by_npk,
#     find_similar_products_by_npk,
#     extract_npk_from_text,
# )
# from modules.llm_handler import ConversationalAgent

# # --- Configuração Inicial ---
# st.set_page_config(page_title="Agente Agrofel", page_icon="🤖")
# st.title("🤖 Agente de Vendas Agrofel")
# st.markdown("Bem-vindo! Sou seu assistente virtual para pedidos de fertilizantes.")

# load_dotenv()
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# if not GOOGLE_API_KEY:
#     st.error("Chave de API do Google não encontrada! Por favor, configure o arquivo .env.")
#     st.stop()

# # Carregamento de dados
# pedidos, precos, portfolio = load_data()
# if portfolio is not None:
#     culturas_disponiveis = portfolio['cultura'].dropna().unique().tolist()
# else:
#     culturas_disponiveis = []

# # --- Inicialização do Estado da Sessão ---
# if "agent" not in st.session_state:
#     st.session_state.agent = ConversationalAgent(api_key=GOOGLE_API_KEY)
# if "messages" not in st.session_state:
#     st.session_state.messages = [
#         {"role": "assistant", "content": "Olá! Como posso ajudar você a encontrar o fertilizante ideal hoje?"}
#     ]
# if "carrinho" not in st.session_state:
#     st.session_state.carrinho = []

# # --- Exibição do Chat ---
# for message in st.session_state.messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])

# # --- Função Helper para Parse do Pedido ---
# def parse_order_request(text: str):
#     """
#     Tenta extrair uma quantidade e um nome de produto de uma string.
#     Ex: "Quero 20 unidades de 09 25 15 C/MICRO" -> (20, "09 25 15 C/MICRO")
#     """
#     # Padrões comuns de pedido
#     patterns = [
#         r'(\d+)\s*(?:unidades?|bags?|caixas?|sacos?|kg)?\s*(?:de|do)?\s*(.+)',
#         r'(?:quero|preciso|gostaria)\s*(?:de)?\s*(\d+)\s*(?:unidades?|bags?|caixas?)?\s*(?:de|do)?\s*(.+)',
#     ]
    
#     for pattern in patterns:
#         match = re.search(pattern, text, re.IGNORECASE)
#         if match:
#             quantity = int(match.group(1))
#             product_name = match.group(2).strip()
#             # Remove palavras desnecessárias do final
#             product_name = re.sub(r'\s*(por favor|obrigado|obrigada)$', '', product_name, flags=re.IGNORECASE)
#             if len(product_name) >= 3:
#                 return quantity, product_name
    
#     return None, None

# def is_greeting(text: str) -> bool:
#     """Verifica se a mensagem é uma saudação."""
#     greetings = ['oi', 'olá', 'ola', 'bom dia', 'boa tarde', 'boa noite', 'hey', 'e ai', 'eai']
#     text_lower = text.lower().strip()
#     return any(greeting in text_lower for greeting in greetings)

# # --- LÓGICA DE CHAT APRIMORADA ---
# if prompt := st.chat_input("Digite o nome de um produto, cultura ou sua dúvida..."):
#     st.session_state.messages.append({"role": "user", "content": prompt})
#     with st.chat_message("user"):
#         st.markdown(prompt)

#     with st.chat_message("assistant"):
#         with st.spinner("Analisando seu pedido..."):
#             contexto_para_llm = "Contexto geral da conversa."
            
#             # --- FLUXO INTELIGENTE DE CONTEXTO ---
            
#             # 1. Verifica se é uma saudação simples
#             if is_greeting(prompt) and len(prompt.split()) <= 3:
#                 contexto_para_llm = (
#                     "O cliente acabou de cumprimentar você. "
#                     "Responda de forma amigável e pergunte como pode ajudar (ex: procura por um produto específico, "
#                     "uma cultura, ou cotação)."
#                 )
            
#             # 2. Tenta identificar um PEDIDO DE COTAÇÃO (ex: "20 unidades de...")
#             else:
#                 quantity, product_name = parse_order_request(prompt)
                
#                 if quantity and product_name:
#                     # Cliente está pedindo cotação
#                     total_value, cod_sku, nome_real = calcular_valor_total(product_name, quantity, portfolio, precos)
                    
#                     if total_value is not None:
#                         # SUCESSO: Produto encontrado e preço calculado
#                         contexto_para_llm = (
#                             f"O cliente pediu cotação de {quantity} unidades de '{product_name}'. "
#                             f"Encontrei o produto '{nome_real}' (código: {cod_sku}). "
#                             f"O valor total é R$ {total_value:.2f}. "
#                             "\n\nSua resposta deve:\n"
#                             "1. Confirmar o produto encontrado (nome correto)\n"
#                             "2. Informar o valor total calculado\n"
#                             "3. AVISAR CLARAMENTE que este valor NÃO INCLUI FRETE\n"
#                             "4. Perguntar se deseja adicionar ao carrinho ou falar com um vendedor para cotação completa"
#                         )
                    
#                     elif nome_real:
#                         # Produto encontrado mas SEM PREÇO
#                         contexto_para_llm = (
#                             f"O cliente pediu cotação de '{product_name}'. "
#                             f"Encontrei o produto '{nome_real}', mas não há preço disponível no sistema. "
#                             "\n\nSua resposta deve:\n"
#                             "1. Informar que o produto foi encontrado\n"
#                             "2. Explicar que o preço não está disponível no momento\n"
#                             "3. Oferecer conectar com um vendedor para obter cotação"
#                         )
                    
#                     else:
#                         # Produto NÃO ENCONTRADO - buscar alternativas
#                         produtos_similares = find_product_by_name(product_name, portfolio, similarity_threshold=0.4)
#                         alternativas_npk = find_alternatives_by_npk(product_name, portfolio)
                        
#                         if produtos_similares or alternativas_npk:
#                             # Encontrou produtos similares
#                             contexto_para_llm = (
#                                 f"O cliente pediu '{product_name}', mas não encontrei produto com este nome exato. "
#                                 "Porém, encontrei produtos similares:\n\n"
#                             )
                            
#                             if produtos_similares:
#                                 contexto_para_llm += "--- PRODUTOS COM NOME SIMILAR ---\n"
#                                 for p in produtos_similares[:3]:
#                                     contexto_para_llm += f"- {p['sku_descricao']} (NPK: {p.get('N', 'N/A')}-{p.get('P', 'N/A')}-{p.get('K', 'N/A')})\n"
                            
#                             if alternativas_npk:
#                                 contexto_para_llm += "\n--- PRODUTOS COM NPK SIMILAR ---\n"
#                                 for p in alternativas_npk[:3]:
#                                     contexto_para_llm += f"- {p['sku_descricao']} (NPK: {p.get('N', 'N/A')}-{p.get('P', 'N/A')}-{p.get('K', 'N/A')})\n"
                            
#                             contexto_para_llm += (
#                                 "\n\nSua resposta deve:\n"
#                                 "1. Informar que não encontrou produto com o nome exato\n"
#                                 "2. Apresentar as alternativas encontradas de forma clara e organizada\n"
#                                 "3. Perguntar se alguma dessas opções é o que o cliente procura\n"
#                                 "4. NÃO oferecer encaminhamento para vendedor ainda (deixe o cliente avaliar as opções primeiro)"
#                             )
#                         else:
#                             # Nenhuma alternativa encontrada
#                             contexto_para_llm = (
#                                 f"O cliente pediu '{product_name}', mas não encontrei este produto nem similares. "
#                                 "\n\nSua resposta deve:\n"
#                                 "1. Informar educadamente que não encontrou o produto\n"
#                                 "2. Pedir para verificar a escrita ou fornecer mais detalhes (ex: NPK, marca, aplicação)\n"
#                                 "3. Sugerir que pode buscar por cultura específica se ele souber\n"
#                                 "4. Oferecer ajuda para encontrar o produto ideal"
#                             )

#                 else:
#                     # 3. Não é cotação - verificar se é busca por PRODUTO direto
#                     produtos_encontrados = find_product_by_name(prompt, portfolio, similarity_threshold=0.5)
                    
#                     if produtos_encontrados:
#                         # Encontrou produto(s) com o nome
#                         contexto_para_llm = (
#                             f"O cliente procurou por '{prompt}' e encontrei os seguintes produtos:\n\n"
#                         )
#                         for p in produtos_encontrados[:5]:
#                             npk_str = f"{p.get('N', 'N/A')}-{p.get('P', 'N/A')}-{p.get('K', 'N/A')}"
#                             contexto_para_llm += f"- {p['sku_descricao']} (NPK: {npk_str})\n"
                        
#                         contexto_para_llm += (
#                             "\n\nSua resposta deve:\n"
#                             "1. Apresentar os produtos encontrados de forma clara\n"
#                             "2. Perguntar se o cliente quer informações sobre algum deles\n"
#                             "3. Perguntar se deseja fazer uma cotação"
#                         )
                    
#                     else:
#                         # 4. Verificar se é busca por CULTURA
#                         cultura_encontrada = None
#                         for cultura in culturas_disponiveis:
#                             if str(cultura).lower() in prompt.lower():
#                                 cultura_encontrada = cultura
#                                 break
                        
#                         if cultura_encontrada:
#                             recomendacoes = recomendar_por_cultura(cultura_encontrada, portfolio)
#                             if recomendacoes:
#                                 contexto_para_llm = (
#                                     f"O cliente perguntou sobre a cultura '{cultura_encontrada}'. "
#                                     f"Encontrei {len(recomendacoes)} produtos recomendados:\n\n"
#                                 )
#                                 for r in recomendacoes[:5]:
#                                     npk_str = f"{r.get('N', 'N/A')}-{r.get('P', 'N/A')}-{r.get('K', 'N/A')}"
#                                     contexto_para_llm += f"- {r['sku_descricao']} (NPK: {npk_str})\n"
                                
#                                 contexto_para_llm += (
#                                     "\n\nSua resposta deve:\n"
#                                     "1. Apresentar os produtos para esta cultura de forma organizada\n"
#                                     "2. Perguntar se o cliente quer mais detalhes sobre algum produto específico\n"
#                                     "3. Oferecer fazer uma cotação"
#                                 )
            
#             # Envia para o LLM com o contexto construído
#             resposta_llm = st.session_state.agent.send_message(prompt, contexto_para_llm)
#             st.markdown(resposta_llm)
    
#     st.session_state.messages.append({"role": "assistant", "content": resposta_llm})

# # --- Sidebar com informações úteis ---
# with st.sidebar:
#     st.header("ℹ️ Dicas de uso")
#     st.markdown("""
#     **Como usar o Agente:**
#     - Digite o nome do produto ou NPK (ex: "Aspire" ou "10 20 20")
#     - Peça cotação: "20 unidades de Aspire"
#     - Busque por cultura: "produtos para café"
    
#     **O agente pode:**
#     ✅ Encontrar produtos similares
#     ✅ Calcular valores (sem frete)
#     ✅ Recomendar por cultura
#     ✅ Sugerir alternativas
#     """)
    
#     if st.session_state.carrinho:
#         st.header("🛒 Carrinho")
#         for item in st.session_state.carrinho:
#             st.write(f"- {item}")
    
#     if st.button("🗑️ Limpar conversa"):
#         st.session_state.messages = [
#             {"role": "assistant", "content": "Olá! Como posso ajudar você a encontrar o fertilizante ideal hoje?"}
#         ]
#         st.session_state.carrinho = []
#         st.rerun()




# # app.py (versão com cálculo de valor)

# import streamlit as st
# import os
# import re # <-- IMPORTAMOS A BIBLIOTECA DE EXPRESSÕES REGULARES
# from dotenv import load_dotenv
# from modules.data_handler import load_data
# from modules.core_logic import (
#     find_product_by_name,
#     recomendar_por_cultura,
#     calcular_valor_total, # <-- IMPORTA A NOVA FUNÇÃO
# )
# from modules.llm_handler import ConversationalAgent

# # --- Configuração Inicial e Carregamento de Dados (sem alterações) ---
# st.set_page_config(page_title="Agente Agrofel", page_icon="🤖")
# st.title("🤖 Agente de Vendas Agrofel")
# st.markdown("Bem-vindo! Sou seu assistente virtual para pedidos de fertilizantes.")

# load_dotenv()
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# if not GOOGLE_API_KEY:
#     st.error("Chave de API do Google não encontrada! Por favor, configure o arquivo .env.")
#     st.stop()

# pedidos, precos, portfolio = load_data()
# if portfolio is not None:
#     culturas_disponiveis = portfolio['cultura'].dropna().unique().tolist()
# else:
#     culturas_disponiveis = []

# # --- Inicialização do Estado da Sessão (sem alterações) ---
# if "agent" not in st.session_state:
#     st.session_state.agent = ConversationalAgent(api_key=GOOGLE_API_KEY)
# if "messages" not in st.session_state:
#     st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar você a encontrar o fertilizante ideal hoje?"}]

# # --- Exibição do Chat (sem alterações) ---
# for message in st.session_state.messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])

# # --- NOVA FUNÇÃO HELPER PARA PARSE DO PEDIDO ---
# def parse_order_request(text: str):
#     """
#     Tenta extrair uma quantidade e um nome de produto de uma string.
#     Ex: "Quero 20 unidades de 09 25 15 C/MICRO" -> (20, "09 25 15 C/MICRO")
#     """
#     # Procura por um número (a quantidade)
#     match = re.search(r'(\d+)', text)
#     if not match:
#         return None, None
    
#     quantity = int(match.group(1))
    
#     # Pega o texto após o número e o trata como nome do produto
#     # Remove palavras comuns de pedido para isolar o nome
#     product_name = re.split(r'\d+\s*(unidades|caixas|bags|de)?\s*', text, maxsplit=1)[-1]
#     product_name = product_name.strip()
    
#     # Se o nome do produto for muito curto, provavelmente é um erro de parse
#     if len(product_name) < 3:
#         return None, None
        
#     return quantity, product_name

# # --- LÓGICA DE CHAT APRIMORADA ---
# if prompt := st.chat_input("Digite o nome de um produto, cultura ou sua dúvida..."):
#     st.session_state.messages.append({"role": "user", "content": prompt})
#     with st.chat_message("user"):
#         st.markdown(prompt)

#     with st.chat_message("assistant"):
#         with st.spinner("Analisando seu pedido..."):
#             contexto_para_llm = "Contexto geral da conversa."
            
#             # --- NOVA LÓGICA DE CONTEXTO INTELIGENTE ---
            
#             # 1. Tenta identificar um PEDIDO DE COTAÇÃO (ex: "20 unidades de...")
#             quantity, product_name = parse_order_request(prompt)
            
#             if quantity and product_name:
#                 total_value = calcular_valor_total(product_name, quantity, portfolio, precos)
#                 if total_value is not None:
#                     # Contexto de sucesso no cálculo
#                     contexto_para_llm = (
#                         f"O cliente pediu uma cotação para '{quantity}' unidades de '{product_name}'. "
#                         f"Eu calculei o valor total e deu R$ {total_value:.2f}. "
#                         "Sua tarefa é: 1. Informar este valor total para o cliente. "
#                         "2. Ressaltar de forma clara que este valor **NÃO INCLUI O FRETE**. "
#                         "3. Perguntar se ele deseja adicionar este item ao carrinho ou se gostaria de falar com um vendedor para obter uma cotação completa com frete."
#                     )
#                 else:
#                     # Contexto de falha no cálculo (produto não encontrado)
#                     contexto_para_llm = (
#                         f"O cliente pediu uma cotação para '{product_name}', mas não encontrei este produto ou seu preço em minha base de dados. "
#                         "Sua tarefa é: 1. Informar ao cliente que você não conseguiu encontrar o produto com o nome exato que ele forneceu. "
#                         "2. Pedir para ele verificar se o nome está correto ou se pode fornecer mais detalhes. "
#                         "3. Oferecer ajuda para encontrar o produto ou encaminhá-lo a um vendedor."
#                     )

#             else:
#                 # 2. Se não for cotação, tenta encontrar uma CULTURA
#                 cultura_encontrada = None
#                 for cultura in culturas_disponiveis:
#                     if str(cultura).lower() in prompt.lower():
#                         cultura_encontrada = cultura
#                         break
                
#                 if cultura_encontrada:
#                     recomendacoes = recomendar_por_cultura(cultura_encontrada, portfolio)
#                     if recomendacoes:
#                         # (Lógica de recomendação por cultura permanece a mesma)
#                         contexto_para_llm = f"O cliente perguntou sobre a cultura '{cultura_encontrada}'. Encontrei os seguintes produtos... Use ESTA LISTA..."
#                         contexto_para_llm += "\n\n--- PRODUTOS DISPONÍVEIS ---\n"
#                         for r in recomendacoes:
#                             contexto_para_llm += f"- Nome: {r['sku_descricao']}, NPK: {r.get('N', 'N/A')}-{r.get('P', 'N/A')}-{r.get('K', 'N/A')}\n"
            
#             # Se nenhuma lógica específica for acionada, o contexto padrão será usado pelo LLM
            
#             resposta_llm = st.session_state.agent.send_message(prompt, contexto_para_llm)
#             st.markdown(resposta_llm)
    
#     st.session_state.messages.append({"role": "assistant", "content": resposta_llm})




