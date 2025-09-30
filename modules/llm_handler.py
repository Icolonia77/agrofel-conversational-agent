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


