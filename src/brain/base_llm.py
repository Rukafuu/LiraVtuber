"""
Interface base para todos os modelos LLM.
Garante que todos os providers sigam a mesma estrutura para permitir hot-swap perfeito.
"""

from abc import ABC, abstractmethod

class BaseLLM(ABC):
    def __init__(self):
        self.config_valida = False

    @abstractmethod
    def gerar_resposta(self, chat_history: list, sistema_prompt: str, user_message: str, tools: list = None) -> str:
        """
        Gera uma resposta do modelo baseada no histórico de chat e na mensagem atual.
        
        Args:
            chat_history: Lista de dicionários com 'role' e 'content'
            sistema_prompt: Prompt de sistema consolidado (personalidade + regras)
            user_message: Mensagem mais recente do usuário
            tools: Lista opcional de ferramentas no padrão JSON das APIs
            
        Returns:
            String com a resposta gerada. Pode retornar um JSON em string se for um tool_call.
        """
        pass
