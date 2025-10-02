import streamlit as st
import os
import re
from dotenv import load_dotenv
from modules.data_handler import load_data
from modules.core_logic import (
    find_product_by_name,
    recomendar_por_cultura,
    calcular_valor_total,
    find_alternatives_by_npk,
    find_similar_products_by_npk,
    extract_npk_from_text,
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

# --- Exibição do Chat ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Função Helper para Parse do Pedido ---
def parse_order_request(text: str):
    """
    Tenta extrair uma quantidade e um nome de produto de uma string.
    Ex: "Quero 20 unidades de 09 25 15 C/MICRO" -> (20, "09 25 15 C/MICRO")
    """
    # Padrões comuns de pedido
    patterns = [
        r'(\d+)\s*(?:unidades?|bags?|caixas?|sacos?|kg)?\s*(?:de|do)?\s*(.+)',
        r'(?:quero|preciso|gostaria)\s*(?:de)?\s*(\d+)\s*(?:unidades?|bags?|caixas?)?\s*(?:de|do)?\s*(.+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            quantity = int(match.group(1))
            product_name = match.group(2).strip()
            # Remove palavras desnecessárias do final
            product_name = re.sub(r'\s*(por favor|obrigado|obrigada)$', '', product_name, flags=re.IGNORECASE)
            if len(product_name) >= 3:
                return quantity, product_name
    
    return None, None

def is_greeting(text: str) -> bool:
    """Verifica se a mensagem é uma saudação."""
    greetings = ['oi', 'olá', 'ola', 'bom dia', 'boa tarde', 'boa noite', 'hey', 'e ai', 'eai']
    text_lower = text.lower().strip()
    return any(greeting in text_lower for greeting in greetings)

# --- LÓGICA DE CHAT APRIMORADA ---
if prompt := st.chat_input("Digite o nome de um produto, cultura ou sua dúvida..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analisando seu pedido..."):
            contexto_para_llm = "Contexto geral da conversa."
            
            # --- FLUXO INTELIGENTE DE CONTEXTO ---
            
            # 1. Verifica se é uma saudação simples
            if is_greeting(prompt) and len(prompt.split()) <= 3:
                contexto_para_llm = (
                    "O cliente acabou de cumprimentar você. "
                    "Responda de forma amigável e pergunte como pode ajudar (ex: procura por um produto específico, "
                    "uma cultura, ou cotação)."
                )
            
            # 2. Tenta identificar um PEDIDO DE COTAÇÃO (ex: "20 unidades de...")
            else:
                quantity, product_name = parse_order_request(prompt)
                
                if quantity and product_name:
                    # Cliente está pedindo cotação
                    total_value, cod_sku, nome_real = calcular_valor_total(product_name, quantity, portfolio, precos)
                    
                    if total_value is not None:
                        # SUCESSO: Produto encontrado e preço calculado
                        contexto_para_llm = (
                            f"O cliente pediu cotação de {quantity} unidades de '{product_name}'. "
                            f"Encontrei o produto '{nome_real}' (código: {cod_sku}). "
                            f"O valor total é R$ {total_value:.2f}. "
                            "\n\nSua resposta deve:\n"
                            "1. Confirmar o produto encontrado (nome correto)\n"
                            "2. Informar o valor total calculado\n"
                            "3. AVISAR CLARAMENTE que este valor NÃO INCLUI FRETE\n"
                            "4. Perguntar se deseja adicionar ao carrinho ou falar com um vendedor para cotação completa"
                        )
                    
                    elif nome_real:
                        # Produto encontrado mas SEM PREÇO
                        contexto_para_llm = (
                            f"O cliente pediu cotação de '{product_name}'. "
                            f"Encontrei o produto '{nome_real}', mas não há preço disponível no sistema. "
                            "\n\nSua resposta deve:\n"
                            "1. Informar que o produto foi encontrado\n"
                            "2. Explicar que o preço não está disponível no momento\n"
                            "3. Oferecer conectar com um vendedor para obter cotação"
                        )
                    
                    else:
                        # Produto NÃO ENCONTRADO - buscar alternativas
                        produtos_similares = find_product_by_name(product_name, portfolio, similarity_threshold=0.4)
                        alternativas_npk = find_alternatives_by_npk(product_name, portfolio)
                        
                        if produtos_similares or alternativas_npk:
                            # Encontrou produtos similares
                            contexto_para_llm = (
                                f"O cliente pediu '{product_name}', mas não encontrei produto com este nome exato. "
                                "Porém, encontrei produtos similares:\n\n"
                            )
                            
                            if produtos_similares:
                                contexto_para_llm += "--- PRODUTOS COM NOME SIMILAR ---\n"
                                for p in produtos_similares[:3]:
                                    contexto_para_llm += f"- {p['sku_descricao']} (NPK: {p.get('N', 'N/A')}-{p.get('P', 'N/A')}-{p.get('K', 'N/A')})\n"
                            
                            if alternativas_npk:
                                contexto_para_llm += "\n--- PRODUTOS COM NPK SIMILAR ---\n"
                                for p in alternativas_npk[:3]:
                                    contexto_para_llm += f"- {p['sku_descricao']} (NPK: {p.get('N', 'N/A')}-{p.get('P', 'N/A')}-{p.get('K', 'N/A')})\n"
                            
                            contexto_para_llm += (
                                "\n\nSua resposta deve:\n"
                                "1. Informar que não encontrou produto com o nome exato\n"
                                "2. Apresentar as alternativas encontradas de forma clara e organizada\n"
                                "3. Perguntar se alguma dessas opções é o que o cliente procura\n"
                                "4. NÃO oferecer encaminhamento para vendedor ainda (deixe o cliente avaliar as opções primeiro)"
                            )
                        else:
                            # Nenhuma alternativa encontrada
                            contexto_para_llm = (
                                f"O cliente pediu '{product_name}', mas não encontrei este produto nem similares. "
                                "\n\nSua resposta deve:\n"
                                "1. Informar educadamente que não encontrou o produto\n"
                                "2. Pedir para verificar a escrita ou fornecer mais detalhes (ex: NPK, marca, aplicação)\n"
                                "3. Sugerir que pode buscar por cultura específica se ele souber\n"
                                "4. Oferecer ajuda para encontrar o produto ideal"
                            )

                else:
                    # 3. Não é cotação - verificar se é busca por PRODUTO direto
                    produtos_encontrados = find_product_by_name(prompt, portfolio, similarity_threshold=0.5)
                    
                    if produtos_encontrados:
                        # Encontrou produto(s) com o nome
                        contexto_para_llm = (
                            f"O cliente procurou por '{prompt}' e encontrei os seguintes produtos:\n\n"
                        )
                        for p in produtos_encontrados[:5]:
                            npk_str = f"{p.get('N', 'N/A')}-{p.get('P', 'N/A')}-{p.get('K', 'N/A')}"
                            contexto_para_llm += f"- {p['sku_descricao']} (NPK: {npk_str})\n"
                        
                        contexto_para_llm += (
                            "\n\nSua resposta deve:\n"
                            "1. Apresentar os produtos encontrados de forma clara\n"
                            "2. Perguntar se o cliente quer informações sobre algum deles\n"
                            "3. Perguntar se deseja fazer uma cotação"
                        )
                    
                    else:
                        # 4. Verificar se é busca por CULTURA
                        cultura_encontrada = None
                        for cultura in culturas_disponiveis:
                            if str(cultura).lower() in prompt.lower():
                                cultura_encontrada = cultura
                                break
                        
                        if cultura_encontrada:
                            recomendacoes = recomendar_por_cultura(cultura_encontrada, portfolio)
                            if recomendacoes:
                                contexto_para_llm = (
                                    f"O cliente perguntou sobre a cultura '{cultura_encontrada}'. "
                                    f"Encontrei {len(recomendacoes)} produtos recomendados:\n\n"
                                )
                                for r in recomendacoes[:5]:
                                    npk_str = f"{r.get('N', 'N/A')}-{r.get('P', 'N/A')}-{r.get('K', 'N/A')}"
                                    contexto_para_llm += f"- {r['sku_descricao']} (NPK: {npk_str})\n"
                                
                                contexto_para_llm += (
                                    "\n\nSua resposta deve:\n"
                                    "1. Apresentar os produtos para esta cultura de forma organizada\n"
                                    "2. Perguntar se o cliente quer mais detalhes sobre algum produto específico\n"
                                    "3. Oferecer fazer uma cotação"
                                )
            
            # Envia para o LLM com o contexto construído
            resposta_llm = st.session_state.agent.send_message(prompt, contexto_para_llm)
            st.markdown(resposta_llm)
    
    st.session_state.messages.append({"role": "assistant", "content": resposta_llm})

# --- Sidebar com informações úteis ---
with st.sidebar:
    st.header("ℹ️ Dicas de uso")
    st.markdown("""
    **Como usar o Agente:**
    - Digite o nome do produto ou NPK (ex: "Aspire" ou "10 20 20")
    - Peça cotação: "20 unidades de Aspire"
    - Busque por cultura: "produtos para café"
    
    **O agente pode:**
    ✅ Encontrar produtos similares
    ✅ Calcular valores (sem frete)
    ✅ Recomendar por cultura
    ✅ Sugerir alternativas
    """)
    
    if st.session_state.carrinho:
        st.header("🛒 Carrinho")
        for item in st.session_state.carrinho:
            st.write(f"- {item}")
    
    if st.button("🗑️ Limpar conversa"):
        st.session_state.messages = [
            {"role": "assistant", "content": "Olá! Como posso ajudar você a encontrar o fertilizante ideal hoje?"}
        ]
        st.session_state.carrinho = []
        st.rerun()