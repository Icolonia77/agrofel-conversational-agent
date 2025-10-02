import streamlit as st
import os
import re
from dotenv import load_dotenv
from modules.data_handler import load_data
from modules.core_logic import (
    find_product_by_name_or_npk,
    find_similar_products_by_npk_vector,
    calcular_valor_total,
    recomendar_por_cultura,
)
from modules.llm_handler import ConversationalAgent

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

if "agent" not in st.session_state:
    st.session_state.agent = ConversationalAgent(api_key=GOOGLE_API_KEY)
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar você a encontrar o fertilizante ideal hoje?"}]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

def parse_order_request(text: str):
    match = re.search(r'(\d+)', text)
    if not match:
        return None, None
    quantity = int(match.group(1))
    product_name = re.split(r'\d+\s*(unidades|caixas|bags|de)?\s*', text, maxsplit=1)[-1].strip()
    if len(product_name) < 3:
        return None, None
    return quantity, product_name

if prompt := st.chat_input("Digite o nome de um produto, cultura ou sua dúvida..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analisando seu pedido..."):
            contexto_para_llm = "Contexto geral da conversa."
            
            # --- NOVA LÓGICA PRINCIPAL ---
            quantity, product_query = parse_order_request(prompt)
            if not product_query:
                product_query = prompt  # Usa o prompt inteiro se não for pedido com quantidade

            # 1. Busca por nome ou NPK
            produtos_encontrados = find_product_by_name_or_npk(product_query, portfolio)
            
            if produtos_encontrados:
                # Produto(s) encontrado(s)
                if len(produtos_encontrados) == 1:
                    prod = produtos_encontrados[0]
                    if quantity:
                        total = calcular_valor_total(prod['cod_sku'], quantity, precos)
                        if total is not None:
                            contexto_para_llm = (
                                f"O cliente solicitou {quantity} unidades de '{product_query}'. "
                                f"Encontrei o produto: {prod['sku_descricao']} (NPK: {prod['N']}-{prod['P']}-{prod['K']}). "
                                f"O valor total é R$ {total:.2f} (sem frete). "
                                "Informe o valor, destaque que é sem frete, e pergunte se deseja prosseguir."
                            )
                        else:
                            contexto_para_llm = (
                                f"Encontrei o produto '{prod['sku_descricao']}' (NPK: {prod['N']}-{prod['P']}-{prod['K']}), "
                                "mas não consegui recuperar o preço. Ofereça ajuda ou sugira contato com vendedor."
                            )
                    else:
                        contexto_para_llm = (
                            f"Encontrei o produto: {prod['sku_descricao']} (NPK: {prod['N']}-{prod['P']}-{prod['K']}). "
                            "Pergunte quantas unidades deseja ou se precisa de mais informações."
                        )
                else:
                    # Múltiplos produtos (fuzzy match)
                    lista = "\n".join([f"- {p['sku_descricao']} (NPK: {p['N']}-{p['P']}-{p['K']})" for p in produtos_encontrados])
                    contexto_para_llm = (
                        f"Encontrei algumas opções para '{product_query}':\n{lista}\n\n"
                        "Peça para o cliente confirmar qual deseja."
                    )
            else:
                # 2. Produto NÃO encontrado → tenta extrair NPK e sugerir similares
                npk_tuple = core_logic.normalize_npk_string(product_query)
                if npk_tuple:
                    n, p, k = npk_tuple
                    similares = find_similar_products_by_npk_vector(n, p, k, portfolio, top_k=3)
                    if similares:
                        lista_sim = "\n".join([f"- {s['sku_descricao']} (NPK: {s['N']}-{s['P']}-{s['K']})" for s in similares])
                        contexto_para_llm = (
                            f"Não encontrei um produto com a formulação exata '{n}-{p}-{k}', "
                            f"mas tenho estas opções similares:\n{lista_sim}\n\n"
                            "Ofereça essas alternativas antes de sugerir atendimento humano."
                        )
                    else:
                        contexto_para_llm = (
                            f"Não encontrei produtos com a formulação '{n}-{p}-{k}' nem similares. "
                            "Peça para verificar os dados ou ofereça contato com vendedor."
                        )
                else:
                    # 3. Busca por cultura
                    cultura_encontrada = None
                    for cultura in culturas_disponiveis:
                        if str(cultura).lower() in prompt.lower():
                            cultura_encontrada = cultura
                            break
                    if cultura_encontrada:
                        recomendacoes = recomendar_por_cultura(cultura_encontrada, portfolio)
                        if recomendacoes:
                            lista_rec = "\n".join([f"- {r['sku_descricao']} (NPK: {r['N']}-{r['P']}-{r['K']})" for r in recomendacoes])
                            contexto_para_llm = (
                                f"Para a cultura '{cultura_encontrada}', recomendo:\n{lista_rec}\n\n"
                                "Pergunte qual deseja ou se precisa de ajuda."
                            )
                        else:
                            contexto_para_llm = f"Não tenho recomendações específicas para '{cultura_encontrada}' no momento."
                    else:
                        contexto_para_llm = (
                            "Não entendi sua solicitação. Você pode informar o nome do produto, a formulação NPK (ex: 10-20-20) "
                            "ou a cultura para a qual precisa de fertilizante?"
                        )

            resposta_llm = st.session_state.agent.send_message(prompt, contexto_para_llm)
            st.markdown(resposta_llm)
    
    st.session_state.messages.append({"role": "assistant", "content": resposta_llm})