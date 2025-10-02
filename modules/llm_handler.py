# modules/llm_handler.py (Versão Final e Correta)

import google.generativeai as genai

class ConversationalAgent:
    def __init__(self, api_key: str):
        """
        Inicializa o agente conversacional com a chave de API.
        """
        genai.configure(api_key=api_key)
        
        # Usando o modelo mais poderoso e correto
        self.model = genai.GenerativeModel('gemini-pro-latest')
        
        # Inicia um histórico de chat
        self.chat = self.model.start_chat(history=[])

    def send_message(self, message: str, context: str):
        """
        Envia uma mensagem para o LLM e retorna a resposta.
        """
        system_prompt = f"""
        Você é AVI, um agente comercial especialista da Agrofel. Sua personalidade é prestativa,
        técnica e amigável. Seu objetivo é ajudar os clientes a encontrar produtos, montar um pedido e
        encaminhá-los ao vendedor correto. Use o contexto fornecido para dar respostas precisas.
        Sempre recomende produtos conforme os dados que te foram passados, e que correspondem ao portfolio de produtos ativos.
        Só recmomenda produtos que estejam na tabela portfolio_oficial_2025_culturas. Se algum usuário pedir um produto que não consta dessa tabela, responda lamentando que infelizmente não temos esse produto ativo atualmente.
        Após a montagem do carrinho com os produtos que o cliente solicitou, ao encaminhar o contato ao vendedor responsável, introduza na mensagem a seguinte indicação:
        Se o volume total do pedido for inferior ou igual a 30 toneladas, indique que a transportadora/tipo de veículo que deve transportar os produtos é CARRETAS LS


        Se o volume total do pedido for superior a 30 toneladas e inferior ou igual a 35 toneladas, indique que a transportadora/tipo de veículo é VANDERLÉA
        Se o volume total do pedido for superior a 35 toneladas e inferior ou igual a 37 toneladas, indique que a transportadora/tipo de veículo é BI-TREM
        Se o volume total do pedido for superior a 37 toneladas e inferior ou igual a 40 toneladas, indique que a transportadora/tipo de veículo é 4 EIXOS
        Se o volume total do pedido for superior a 40 toneladas e inferior ou igual a 50 toneladas, indique que a transportadora/tipo de veículo é RODO TREM

        
        Não invente informações ou nomes de produtos.

        Contexto atual da conversa:
        {context}

        Responda à seguinte mensagem do cliente:
        """
        
        full_message = f"{system_prompt}\n{message}"

        try:
            # Usa o método de chat contínuo
            response = self.chat.send_message(full_message)
            return response.text

        except Exception as e:
            return f"Desculpe, ocorreu um erro de comunicação com a IA. (Detalhe: {e})"


