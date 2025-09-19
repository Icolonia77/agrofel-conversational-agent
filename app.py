# app.py (versão com cálculo de valor)

import streamlit as st
import os
import re # <-- IMPORTAMOS A BIBLIOTECA DE EXPRESSÕES REGULARES
from dotenv import load_dotenv
from modules.data_handler import load_data
from modules.core_logic import (
    find_product_by_name,
    recomendar_por_cultura,
    calcular_valor_total, # <-- IMPORTA A NOVA FUNÇÃO
)
from modules.llm_handler import ConversationalAgent

# --- Configuração Inicial e Carregamento de Dados (sem alterações) ---
st.set_page_config(page_title="Agente Agrofel", page_icon="🤖")
st.title("🤖 Agente de Vendas Agrofel")
st.markdown("Bem-vindo! Sou seu assistente virtual para pedidos de fertilizantes.")

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("Chave de API do Google não encontrada! Por favor, configure o arquivo .env.")
    st.stop()

pedidos, precos, portfolio = load_data()
if portfolio is not None:
    culturas_disponiveis = portfolio['cultura'].dropna().unique().tolist()
else:
    culturas_disponiveis = []

# --- Inicialização do Estado da Sessão (sem alterações) ---
if "agent" not in st.session_state:
    st.session_state.agent = ConversationalAgent(api_key=GOOGLE_API_KEY)
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar você a encontrar o fertilizante ideal hoje?"}]

# --- Exibição do Chat (sem alterações) ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- NOVA FUNÇÃO HELPER PARA PARSE DO PEDIDO ---
def parse_order_request(text: str):
    """
    Tenta extrair uma quantidade e um nome de produto de uma string.
    Ex: "Quero 20 unidades de 09 25 15 C/MICRO" -> (20, "09 25 15 C/MICRO")
    """
    # Procura por um número (a quantidade)
    match = re.search(r'(\d+)', text)
    if not match:
        return None, None
    
    quantity = int(match.group(1))
    
    # Pega o texto após o número e o trata como nome do produto
    # Remove palavras comuns de pedido para isolar o nome
    product_name = re.split(r'\d+\s*(unidades|caixas|bags|de)?\s*', text, maxsplit=1)[-1]
    product_name = product_name.strip()
    
    # Se o nome do produto for muito curto, provavelmente é um erro de parse
    if len(product_name) < 3:
        return None, None
        
    return quantity, product_name

# --- LÓGICA DE CHAT APRIMORADA ---
if prompt := st.chat_input("Digite o nome de um produto, cultura ou sua dúvida..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analisando seu pedido..."):
            contexto_para_llm = "Contexto geral da conversa."
            
            # --- NOVA LÓGICA DE CONTEXTO INTELIGENTE ---
            
            # 1. Tenta identificar um PEDIDO DE COTAÇÃO (ex: "20 unidades de...")
            quantity, product_name = parse_order_request(prompt)
            
            if quantity and product_name:
                total_value = calcular_valor_total(product_name, quantity, portfolio, precos)
                if total_value is not None:
                    # Contexto de sucesso no cálculo
                    contexto_para_llm = (
                        f"O cliente pediu uma cotação para '{quantity}' unidades de '{product_name}'. "
                        f"Eu calculei o valor total e deu R$ {total_value:.2f}. "
                        "Sua tarefa é: 1. Informar este valor total para o cliente. "
                        "2. Ressaltar de forma clara que este valor **NÃO INCLUI O FRETE**. "
                        "3. Perguntar se ele deseja adicionar este item ao carrinho ou se gostaria de falar com um vendedor para obter uma cotação completa com frete."
                    )
                else:
                    # Contexto de falha no cálculo (produto não encontrado)
                    contexto_para_llm = (
                        f"O cliente pediu uma cotação para '{product_name}', mas não encontrei este produto ou seu preço em minha base de dados. "
                        "Sua tarefa é: 1. Informar ao cliente que você não conseguiu encontrar o produto com o nome exato que ele forneceu. "
                        "2. Pedir para ele verificar se o nome está correto ou se pode fornecer mais detalhes. "
                        "3. Oferecer ajuda para encontrar o produto ou encaminhá-lo a um vendedor."
                    )

            else:
                # 2. Se não for cotação, tenta encontrar uma CULTURA
                cultura_encontrada = None
                for cultura in culturas_disponiveis:
                    if str(cultura).lower() in prompt.lower():
                        cultura_encontrada = cultura
                        break
                
                if cultura_encontrada:
                    recomendacoes = recomendar_por_cultura(cultura_encontrada, portfolio)
                    if recomendacoes:
                        # (Lógica de recomendação por cultura permanece a mesma)
                        contexto_para_llm = f"O cliente perguntou sobre a cultura '{cultura_encontrada}'. Encontrei os seguintes produtos... Use ESTA LISTA..."
                        contexto_para_llm += "\n\n--- PRODUTOS DISPONÍVEIS ---\n"
                        for r in recomendacoes:
                            contexto_para_llm += f"- Nome: {r['sku_descricao']}, NPK: {r.get('N', 'N/A')}-{r.get('P', 'N/A')}-{r.get('K', 'N/A')}\n"
            
            # Se nenhuma lógica específica for acionada, o contexto padrão será usado pelo LLM
            
            resposta_llm = st.session_state.agent.send_message(prompt, contexto_para_llm)
            st.markdown(resposta_llm)
    
    st.session_state.messages.append({"role": "assistant", "content": resposta_llm})




# # app.py (versão com contexto inteligente)

# import streamlit as st
# import os
# from dotenv import load_dotenv
# from modules.data_handler import load_data
# from modules.core_logic import (
#     find_product_by_name,
#     find_similar_products_by_npk,
#     get_product_price,
#     find_vendor_by_cep,
#     recomendar_por_cultura, # <-- IMPORTA A NOVA FUNÇÃO
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

# # --- Carregamento de Dados ---
# pedidos, precos, portfolio = load_data()
# # Criamos uma lista de culturas disponíveis para a busca
# if portfolio is not None:
#     culturas_disponiveis = portfolio['cultura'].dropna().unique().tolist()
# else:
#     culturas_disponiveis = []

# # --- Inicialização do Estado da Sessão ---
# if "agent" not in st.session_state:
#     st.session_state.agent = ConversationalAgent(api_key=GOOGLE_API_KEY)
# if "messages" not in st.session_state:
#     st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar você a encontrar o fertilizante ideal hoje?"}]
# if "cart" not in st.session_state:
#     st.session_state.cart = {}

# # --- Interface (sem alterações) ---
# # (O código da função display_cart() e do loop de exibição de mensagens continua o mesmo)
# def display_cart():
#     if st.session_state.cart:
#         st.sidebar.markdown("### 🛒 Carrinho de Compras")
#         # ... (código restante da função é o mesmo)

# display_cart()

# for message in st.session_state.messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])

# # --- LÓGICA DE CHAT APRIMORADA ---
# if prompt := st.chat_input("Digite o nome de um produto, cultura ou sua dúvida..."):
#     st.session_state.messages.append({"role": "user", "content": prompt})
#     with st.chat_message("user"):
#         st.markdown(prompt)

#     with st.chat_message("assistant"):
#         with st.spinner("Analisando seu pedido..."):
            
#             # ===== NOVA LÓGICA DE CONTEXTO INTELIGENTE =====
#             contexto_para_llm = "O carrinho de compras do cliente está vazio." # Contexto padrão

#             # 1. Tenta encontrar uma CULTURA na mensagem do usuário
#             cultura_encontrada = None
#             for cultura in culturas_disponiveis:
#                 if str(cultura).lower() in prompt.lower():
#                     cultura_encontrada = cultura
#                     break
            
#             if cultura_encontrada:
#                 recomendacoes = recomendar_por_cultura(cultura_encontrada, portfolio)
#                 if recomendacoes:
#                     # Se encontrarmos recomendações, criamos um contexto rico para o LLM
#                     contexto_para_llm = f"O cliente perguntou sobre a cultura '{cultura_encontrada}'. Encontrei os seguintes produtos em nosso portfólio para esta cultura. Use ESTA LISTA para basear sua resposta. Não invente nomes de produtos. Apresente as opções de forma natural e amigável."
#                     contexto_para_llm += "\n\n--- PRODUTOS DISPONÍVEIS ---\n"
#                     for r in recomendacoes:
#                         contexto_para_llm += f"- Nome do Produto: {r['sku_descricao']}, NPK: {r.get('N', 'N/A')}-{r.get('P', 'N/A')}-{r.get('K', 'N/A')}\n"
#                     contexto_para_llm += "--- FIM DA LISTA ---\n"

#             # 2. Se não for sobre cultura, tenta encontrar um NOME DE PRODUTO específico
#             else:
#                 produtos_encontrados = find_product_by_name(prompt, portfolio)
#                 if produtos_encontrados:
#                     # (A lógica anterior para busca por nome continua válida)
#                     contexto_para_llm = "Foram encontrados os seguintes produtos com base na busca do cliente. Apresente-os de forma amigável."
#                     contexto_para_llm += "\n\nProdutos:\n"
#                     for p in produtos_encontrados:
#                         contexto_para_llm += f"- {p['sku_descricao']}\n"
            
#             # (A lógica para CEP e outras conversas pode ser adicionada aqui como `elif`)

#             # =======================================================

#             resposta_llm = st.session_state.agent.send_message(prompt, contexto_para_llm)
#             st.markdown(resposta_llm)
    
#     st.session_state.messages.append({"role": "assistant", "content": resposta_llm})

