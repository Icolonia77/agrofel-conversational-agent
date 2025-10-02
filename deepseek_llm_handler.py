import google.generativeai as genai
import streamlit as st

class ConversationalAgent:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
    def send_message(self, user_message: str, context: str = ""):
        """
        Envia mensagem para o LLM com contexto específico.
        MELHORIA: Prompt engineering para melhor comportamento do agente.
        """
        system_prompt = f"""
        Você é um assistente de vendas especializado em fertilizantes da AgroFel.
        
        CONTEXTO ESPECÍFICO:
        {context}
        
        REGRAS IMPORTANTES:
        1. SEMPRE busque resolver a dúvida do cliente antes de sugerir encaminhamento
        2. Quando um produto não for encontrado exatamente, SUGIRA alternativas similares
        3. NUNCA sugira encaminhamento para vendedor como primeira opção
        4. Seja proativo em ajudar a encontrar o produto correto
        5. Use informações técnicas (NPK, culturas) para dar recomendações precisas
        6. Mantenha tom profissional mas amigável
        7. Responda em português brasileiro natural
        
        COMPORTAMENTO ESPERADO:
        - Produto não encontrado: "Não encontrei exatamente '{produto}', mas tenho estas alternativas similares..."
        - Dúvida técnica: Explique com informações sobre NPK e culturas
        - Pedido de cotação: Calcule valores claramente e mencione que frete não está incluído
        - Encaminhamento: Só sugira quando realmente necessário após tentar ajudar
        
        RESPOSTA ATUAL:
        """
        
        try:
            full_prompt = f"{system_prompt}\n\nCliente: {user_message}\nAssistente:"
            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente. Erro: {str(e)}"