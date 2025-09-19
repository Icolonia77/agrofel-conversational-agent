# modules/llm_handler.py

import google.generativeai as genai

class ConversationalAgent:
    def __init__(self, api_key: str):
        """
        Inicializa o agente conversacional com a API do Gemini.
        """
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        self.chat = self.model.start_chat(history=[])

    def send_message(self, message: str, context: str):
        """
        Envia uma mensagem para o LLM e retorna a resposta.
        Inclui o contexto do sistema para guiar o comportamento do agente.
        """
        # --- ALTERAÇÃO AQUI ---
        # Adicionamos a identidade "AVI" diretamente nas instruções do agente.
        system_prompt = f"""
        Você é um agente comercial especialista da Agrofel, uma empresa de fertilizantes.
        Sua personalidade é prestativa, técnica e amigável.
        Seu nome é AVI. Ao se apresentar, diga que você é o AVI, o assistente virtual especialista da Agrofel.
        Seu objetivo é ajudar os clientes a encontrar produtos, montar um pedido e encaminhá-los ao vendedor correto.
        Responda em português do Brasil.

        Contexto atual da conversa:
        {context}

        Responda à seguinte mensagem do cliente:
        """
        
        full_message = f"{system_prompt}\n{message}"

        try:
            response = self.chat.send_message(full_message)
            return response.text
        except Exception as e:
            return f"Desculpe, ocorreu um erro de comunicação com a IA. (Detalhe: {e})"


# # modules/llm_handler.py

# import google.generativeai as genai

# class ConversationalAgent:
#     def __init__(self, api_key: str):
#         """
#         Inicializa o agente conversacional com a API do Gemini.
#         """
#         genai.configure(api_key=api_key)
#         self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
#         self.chat = self.model.start_chat(history=[])

#     def send_message(self, message: str, context: str):
#         """
#         Envia uma mensagem para o LLM e retorna a resposta.
#         Inclui o contexto do sistema para guiar o comportamento do agente.
#         """
#         system_prompt = f"""
#         Você é um agente comercial especialista da Agrofel, uma empresa de fertilizantes.
#         Sua personalidade é prestativa, técnica e amigável.
#         Seu objetivo é ajudar os clientes a encontrar produtos, montar um pedido e encaminhá-los ao vendedor correto.
#         Responda em português do Brasil.

#         Contexto atual da conversa:
#         {context}

#         Responda à seguinte mensagem do cliente:
#         """
        
#         full_message = f"{system_prompt}\n{message}"

#         try:
#             response = self.chat.send_message(full_message)
#             return response.text
#         except Exception as e:
#             return f"Desculpe, ocorreu um erro de comunicação com a IA. (Detalhe: {e})"