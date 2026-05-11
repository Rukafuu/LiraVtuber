import logging
import re
import json
from typing import List, Dict, Any, Optional, Callable

from src.utils.lira_tags import extract_xml_actions, strip_xml_tags
from src.modules.tools.pc_control import execute_pc_action

logger = logging.getLogger(__name__)

# Ferramentas que retornam dados e devem disparar um novo turno da LLM automaticamente
ACTIVE_TOOLS = {
    "ferramenta_web",
    "analisar_youtube",
    "ler_tela_ocr",
    "acao_pc"
}

class LiraAgency:
    def __init__(self, llm_selector, tool_manager, memory_manager):
        self.llm_selector = llm_selector
        self.tool_manager = tool_manager
        self.memory_manager = memory_manager
        self.max_steps = 3 # Evita loops infinitos

    def process_turn(
        self,
        user_message: str,
        chat_history: List[Dict[str, str]],
        sistema_prompt: str,
        image_b64: Optional[str] = None,
        request_context: Optional[Dict[str, Any]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[str], None]] = None,
        on_tool_done: Optional[Callable[[str, str], None]] = None
    ) -> str:
        """
        Executa um loop de pensamento autônomo (ReAct).
        """
        current_user_input = user_message
        current_history = list(chat_history)
        final_response = ""
        
        for step in range(self.max_steps):
            logger.info(f"[AGENCY] Iniciando passo {step + 1}/{self.max_steps}")
            
            llm = self.llm_selector.get_provider()
            full_text = ""
            
            # 1. Geração da LLM (Stream)
            token_stream = llm.gerar_resposta_stream(
                chat_history=current_history,
                sistema_prompt=sistema_prompt,
                user_message=current_user_input,
                image_b64=image_b64 if step == 0 else None, # Só manda imagem no primeiro passo
                request_context=request_context
            )
            
            for token in token_stream:
                if on_chunk:
                    on_chunk(token)
                full_text += token
            
            # 2. Extração de Ações
            actions = extract_xml_actions(full_text, tuple(ACTIVE_TOOLS) | ("salvar_memoria", "gerar_imagem", "gerar_musica"))
            
            # Se não houver ferramentas ATIVAS, terminamos o loop aqui
            active_actions = {k: v for k, v in actions.items() if k in ACTIVE_TOOLS and v}
            if not active_actions:
                final_response = full_text
                break
            
            # 3. Execução de Ferramentas Ativas
            tool_results = []
            
            # Processar pesquisa web
            for query in actions.get("ferramenta_web", []):
                if on_tool_start: on_tool_start("pesquisa_web")
                res_sis, res_tts = self.tool_manager.executar_tool("pesquisa_web", {"query": query})
                tool_results.append(f"[RESULTADO PESQUISA WEB]: {res_sis}")
                if on_tool_done: on_tool_done("pesquisa_web", res_tts)

            # Processar YouTube
            for url in actions.get("analisar_youtube", []):
                if on_tool_start: on_tool_start("analisar_youtube")
                res_sis, res_tts = self.tool_manager.executar_tool("analisar_youtube", {"url": url})
                tool_results.append(f"[RESULTADO ANALISE YOUTUBE]: {res_sis}")
                if on_tool_done: on_tool_done("analisar_youtube", res_tts)

            # Processar OCR
            if actions.get("ler_tela_ocr"):
                if on_tool_start: on_tool_start("ler_tela_ocr")
                res_sis, res_tts = self.tool_manager.executar_tool("ler_tela_ocr", {})
                tool_results.append(f"[RESULTADO LEITURA DE TELA]: {res_sis}")
                if on_tool_done: on_tool_done("ler_tela_ocr", res_tts)

            # Processar Ações de PC (apenas as que retornam dados úteis)
            for payload in actions.get("acao_pc", []):
                if on_tool_start: on_tool_start("acao_pc")
                res = execute_pc_action(payload)
                # Se a ação retornou conteúdo (ex: leu arquivo ou listou processos), injetamos no loop
                data_return = ""
                if res.get("content"): data_return = str(res["content"])
                elif res.get("stdout"): data_return = str(res["stdout"])
                
                if data_return:
                    tool_results.append(f"[RESULTADO ACAO PC - {res.get('action')}]: {data_return[:5000]}")
                
                if on_tool_done: on_tool_done("acao_pc", res.get("message", "Ação concluída."))

            if not tool_results:
                final_response = full_text
                break

            # 4. Preparar próximo passo
            # Adicionamos o que a IA disse e o que as ferramentas retornaram ao histórico
            current_history.append({"role": "user", "content": current_user_input})
            current_history.append({"role": "assistant", "content": full_text})
            
            # O novo "input" do usuário é na verdade o resultado das ferramentas
            current_user_input = "[SISTEMA]: Ferramentas executadas. Resultados abaixo:\n\n" + "\n\n".join(tool_results)
            current_user_input += "\n\nAnalise esses dados e finalize sua resposta para o usuario."
            
        return final_response
