import streamlit as st
import os
import re
from dotenv import load_dotenv
from modules.data_handler import load_data, validate_data_integrity
from modules.core_logic import (
    find_product_by_name,
    find_products_by_flexible_search,
    find_similar_products_by_npk,
    recomendar_por_cultura,
    calcular_valor_total,
    suggest_alternative_products,
    get_product_price
)
from modules.llm_handler import ConversationalAgent

# --- Configuração Inicial ---
st.set_page_config(
    page_title="Agente Agrofel - Inteligente", 
    page_icon="🤖",
    layout="wide"
)
st.title("🌱 Agente de Vendas Agrofel - Inteligente")
st.markdown("Bem-vindo! Sou seu assistente virtual especializado em fertilizantes.")

# --- Carregamento de Dados com Validação ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("❌ Chave de API do Google não encontrada! Configure o arquivo .env.")
    st.stop()

with st.spinner("🔄 Carregando dados e validando integridade..."):
    pedidos, precos, portfolio = load_data()
    
    # Validação de dados
    if portfolio is not None:
        data_issues = validate_data_integrity(pedidos, precos, portfolio)
        if data_issues:
            for issue in data_issues:
                st.warning(issue)
    
    if portfolio is not None:
        culturas_disponiveis = portfolio['cultura'].dropna().unique().tolist()
        # Log de produtos disponíveis para debug
        st.success(f"📦 Total de produtos no portfólio: {len(portfolio)}")
    else:
        culturas_disponiveis = []
        st.error("❌ Não foi possível carregar o portfólio de produtos.")

# --- Inicialização do Estado da Sessão ---
if "agent" not in st.session_state:
    st.session_state.agent = ConversationalAgent(api_key=GOOGLE_API_KEY)
if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant", 
        "content": "Olá! Sou seu assistente especializado em fertilizantes. Posso ajudar você a encontrar o produto ideal, calcular cotações ou tirar dúvidas técnicas. Como posso ajudá-lo hoje?"
    }]
if "cart" not in st.session_state:
    st.session_state.cart = []

# --- Exibição do Histórico do Chat ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Funções Auxiliares Melhoradas ---
def parse_order_request(text: str):
    """
    Tenta extrair uma quantidade e um nome de produto de uma string.
    MELHORIA: Parse mais inteligente e flexível.
    """
    # Padrões mais flexíveis para quantidades
    quantity_patterns = [
        r'(\d+)\s*(unidades?|caixas?|bags?|sacos?|kg|toneladas?)',
        r'(\d+)\s*',
        r'qtd\s*[:\-]?\s*(\d+)',
        r'quantidade\s*[:\-]?\s*(\d+)'
    ]
    
    quantity = None
    product_name = text.strip()
    
    for pattern in quantity_patterns:
        match = re.search(pattern, text.lower())
        if match:
            quantity = int(match.group(1))
            # Remove a parte da quantidade do texto para isolar o nome do produto
            product_name = re.sub(pattern, '', text, flags=re.IGNORECASE).strip()
            break
    
    # Limpeza do nome do produto
    product_name = re.sub(r'^(de|do|da|dos|das)\s+', '', product_name).strip()
    product_name = re.sub(r'\s+', ' ', product_name)
    
    return quantity, product_name if product_name else None

def format_product_suggestions(suggestions):
    """Formata sugestões de produtos para exibição."""
    if not suggestions:
        return "Não encontrei produtos similares."
    
    formatted = "**Aqui estão algumas alternativas que podem atender sua necessidade:**\n\n"
    for i, product in enumerate(suggestions, 1):
        price_info = f" - 💰 R$ {product.get('preco', 'N/A')}" if product.get('preco') else ""
        formatted += f"{i}. **{product['sku_descricao']}** (NPK: {product['N']}-{product['P']}-{product['K']}){price_info}\n"
        if product.get('cultura'):
            formatted += f"   🌱 Para: {product['cultura']}\n"
        formatted += "\n"
    
    return formatted

# --- Lógica Principal do Chat (MELHORADA) ---
if prompt := st.chat_input("Digite o nome do produto, formulação NPK, cultura ou sua dúvida..."):
    # Adiciona mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Analisando sua solicitação..."):
            contexto_para_llm = "Contexto geral da conversa."
            
            # --- LÓGICA INTELIGENTE DE BUSCA MELHORADA ---
            
            # 1. Tenta identificar um PEDIDO DE COTAÇÃO
            quantity, product_name = parse_order_request(prompt)
            
            if quantity and product_name:
                # Busca FLEXÍVEL pelo produto
                product_matches = find_products_by_flexible_search(product_name, portfolio, top_n=1)
                
                if product_matches:
                    # Produto ENCONTRADO - calcular valor
                    product_match = product_matches[0]
                    total_value = calcular_valor_total(product_name, quantity, portfolio, precos)
                    
                    if total_value is not None:
                        contexto_para_para_llm = (
                            f"O cliente pediu uma cotação para '{quantity}' unidades de '{product_name}'. "
                            f"ENCONTREI o produto: {product_match['sku_descricao']}. "
                            f"Valor total calculado: R$ {total_value:.2f}. "
                            "SUA TAREFA: 1. Informar o valor total claramente. "
                            "2. Mencionar que o valor NÃO INCLUI FRETE. "
                            "3. Oferecer adicionar ao carrinho OU falar com vendedor para cotação completa."
                        )
                    else:
                        contexto_para_llm = (
                            f"O cliente pediu '{quantity}' unidades de '{product_name}'. "
                            f"ENCONTREI o produto mas NÃO ENCONTREI o preço. "
                            "SUA TAREFA: Informar que encontrou o produto mas precisa consultar preço com vendedor."
                        )
                else:
                    # Produto NÃO ENCONTRADO - sugerir alternativas
                    alternative_suggestions = suggest_alternative_products(product_name, portfolio, precos, max_suggestions=3)
                    
                    if alternative_suggestions:
                        suggestions_text = format_product_suggestions(alternative_suggestions)
                        contexto_para_llm = (
                            f"O cliente pediu '{quantity}' unidades de '{product_name}'. "
                            f"NÃO ENCONTREI o produto exato, mas TENHO ALTERNATIVAS SIMILARES. "
                            f"SUGESTÕES DISPONÍVEIS:\n{suggestions_text}\n"
                            "SUA TAREFA: 1. Informar que não encontrou o produto exato. "
                            "2. Apresentar as alternativas similares. "
                            "3. Perguntar se alguma das alternativas atende ou se precisa de mais opções."
                        )
                    else:
                        contexto_para_llm = (
                            f"O cliente pediu '{quantity}' unidades de '{product_name}'. "
                            f"NÃO ENCONTREI o produto exato e NÃO TENHO ALTERNATIVAS SIMILARES. "
                            "SUA TAREFA: 1. Informar educadamente que não encontrou o produto. "
                            "2. Pedir para verificar o nome ou fornecer mais detalhes. "
                            "3. Oferecer ajuda para buscar por outras características (NPK, cultura)."
                        )

            else:
                # 2. Busca por PRODUTO (sem quantidade específica)
                product_search_results = find_products_by_flexible_search(prompt, portfolio, top_n=3)
                
                if product_search_results:
                    suggestions_text = format_product_suggestions(product_search_results)
                    contexto_para_llm = (
                        f"O cliente perguntou sobre '{prompt}'. "
                        f"ENCONTREI {len(product_search_results)} produto(s) relacionados. "
                        f"PRODUTOS ENCONTRADOS:\n{suggestions_text}\n"
                        "SUA TAREFA: 1. Apresentar os produtos encontrados. "
                        "2. Oferecer mais informações técnicas sobre algum produto específico. "
                        "3. Perguntar se deseja calcular cotação para algum deles."
                    )
                
                # 3. Busca por CULTURA
                else:
                    cultura_encontrada = None
                    for cultura in culturas_disponiveis:
                        if cultura and str(cultura).lower() in prompt.lower():
                            cultura_encontrada = cultura
                            break
                    
                    if cultura_encontrada:
                        recomendacoes = recomendar_por_cultura(cultura_encontrada, portfolio)
                        if recomendacoes:
                            contexto_para_llm = f"O cliente perguntou sobre a cultura '{cultura_encontrada}'. ENCONTREI produtos recomendados. SUA TAREFA: Listar os produtos e oferecer ajuda para escolher o mais adequado."
                            contexto_para_llm += "\n\n--- PRODUTOS RECOMENDADOS ---\n"
                            for r in recomendacoes[:5]:  # Limita a 5 recomendações
                                contexto_para_llm += f"- {r['sku_descricao']} (NPK: {r.get('N', 'N/A')}-{r.get('P', 'N/A')}-{r.get('K', 'N/A')})\n"
            
            # Se nenhuma lógica específica for acionada, o contexto padrão será usado
            resposta_llm = st.session_state.agent.send_message(prompt, contexto_para_llm)
            st.markdown(resposta_llm)
    
    st.session_state.messages.append({"role": "assistant", "content": resposta_llm})

# --- Sidebar com Informações Úteis ---
with st.sidebar:
    st.header("📊 Informações do Sistema")
    
    if portfolio is not None:
        st.metric("Produtos no Portfólio", len(portfolio))
    
    st.header("🛒 Carrinho de Cotação")
    if st.session_state.cart:
        for item in st.session_state.cart:
            st.write(f"- {item['product']}: {item['quantity']} unidades")
    else:
        st.write("Carrinho vazio")
    
    st.header("🔍 Dicas de Busca")
    st.info("""
    Você pode buscar por:
    - Nome do produto (ex: "Aspire")
    - Formulação NPK (ex: "10.20.20" ou "10-20-20")
    - Cultura (ex: "soja", "milho")
    - Pedido com quantidade (ex: "20 unidades de 09 25 15")
    """)
    
    if st.button("🔄 Reiniciar Conversa"):
        st.session_state.messages = [{
            "role": "assistant", 
            "content": "Olá! Sou seu assistente especializado em fertilizantes. Como posso ajudá-lo hoje?"
        }]
        st.session_state.cart = []
        st.rerun()