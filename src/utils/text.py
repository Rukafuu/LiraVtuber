"""
Utilitários de processamento de texto compartilhados por toda a Nyra/Hana.

Centraliza limpeza de texto para TTS, remoção de emojis, formatação etc.
"""

import re
import sys
import time

def limpar_texto_tts(texto: str) -> str:
    """
    Remove formatação oculta antes de envio ao sintetizador de voz.
    
    ⚠️ FUNÇÃO CRÍTICA: ÚLTIMA ETAPA antes de pronunciar.
    Aqui removemos APENAS o que não deve ser lido.
    
    NOVO SISTEMA (2026):
    - 【 】 (Marcador Fantasma): REMOVE COMPLETAMENTE (pensamentos ocultos)
    - 《 》 (Marcador Visual): Remove colchetes mas MANTÉM conteúdo (links, código, fontes)
    - * * (Ênfase): Remove asteriscos mas MANTÉM texto
    - **negrito** MARKDOWN: PRESERVA (será lido normalmente como "negrito")
    - Backticks: Remove mas mantém texto
    - Emojis, links, código: Remove
    
    PIPELINE ESPERADO:
    Nyra/Hana responde → Terminal (COM formatação 《》【】**) → Memória (completo)
    ↓ (AQUI na TTS)
    limpar_texto_tts() remove APENAS canais silenciosos
    ↓
    Síntese de Voz (natural)
    """
    if not texto:
        return ""

    # PRÉ-LIMPEZA: Marcar seções para remover
    # 1. Tags <think>...</think> (DeepSeek/R1)
    texto_limpo = re.sub(r'<think>.*?</think>', '', texto, flags=re.DOTALL)

    # 1b. Tags XML de habilidades da Hana (NÃO devem ser lidas pelo TTS)
    texto_limpo = re.sub(r'<pensamento>.*?</pensamento>', '', texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r'<thought>.*?</thought>', '', texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r'<salvar_memoria>.*?</salvar_memoria>', '', texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r'<gerar_imagem>.*?</gerar_imagem>', '', texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r'<editar_imagem>.*?</editar_imagem>', '', texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r'<analisar_youtube>.*?</analisar_youtube>', '', texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r'<bypass>.*?</bypass>', '', texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r'<resumo_imagem>.*?</resumo_imagem>', '', texto_limpo, flags=re.DOTALL)

    # 2. Proteção de Emergência: Remove blocos de código
    texto_limpo = re.sub(r'<tool_code>.*?</tool_code>', '', texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r'```.*?```', '', texto_limpo, flags=re.DOTALL)

    # 2b. Remove citações do Google Search Grounding [INDEX_X.Y]
    texto_limpo = re.sub(r'\[INDEX_\d+\.\d+(?:,\s*INDEX_\d+\.\d+)*\]', '', texto_limpo)
    
    # === NOVO SISTEMA DE MARCADORES (2026) ===
    
    # 3. MARCADOR FANTASMA 【 】: REMOVE COMPLETAMENTE (totalmente invisível)
    texto_limpo = re.sub(r'【.*?】', '', texto_limpo, flags=re.DOTALL)
    
    # 4. MARCADOR VISUAL 《 》: REMOVE COMPLETAMENTE NA VOZ (Silencioso na Voz)
    texto_limpo = re.sub(r'《.*?》', '', texto_limpo, flags=re.DOTALL)
    
    # 5. Emojis (Unicode range abrangente)
    emoji_pattern = re.compile(
        '['
        '\U0001F600-\U0001F64F'  # Emoticons
        '\U0001F300-\U0001F5FF'  # Misc Symbols and Pictographs
        '\U0001F680-\U0001F6FF'  # Transport and Map Symbols
        '\U0001F1E6-\U0001F1FF'  # Flags (Regional Indicator Symbols)
        '\U0001F900-\U0001F9FF'  # Supplemental Symbols and Pictographs
        '\u2600-\u26FF'          # Misc Symbols (like ✨)
        '\u2700-\u27BF'          # Dingbats
        '\U00020000-\U0003FFFF'  # Surrogates/Planes
        ']+', flags=re.UNICODE
    )
    texto_limpo = emoji_pattern.sub('', texto_limpo)

    # 6. Remove marcadores de sistema [SISTEMA...] e labels [NYRA]/[HANA]:
    texto_limpo = re.sub(r'\[SISTEMA[^\]]*\]', '', texto_limpo)
    texto_limpo = re.sub(r'\[([^\]]+)\]:', '', texto_limpo)

    # 7. Remove function call artifacts
    texto_limpo = re.sub(r'function.*?function', '', texto_limpo, flags=re.DOTALL | re.IGNORECASE)

    # 8. Remove <> residuais
    texto_limpo = re.sub(r'<[^>]*>', '', texto_limpo)

    # 9. REMOVER CARACTERES ESPECIAIS QUE TEIMAM A SER LIDOS PELA TTS
    # Removemos: *, `, ~, (), [], {}, ^, aspas, e outros símbolos estranhos
    for char in ['*', '**', '** **', '`', '~', '(', ')', '[', ']', '{', '}', '^', '«', '»', '"', "'", '‹', '›', '„', '“', '”']:
        texto_limpo = texto_limpo.replace(char, '')
        texto_limpo = texto_limpo.replace('_', '').replace('__', '').replace('___', '').replace('#', '').replace('##', '').replace('###', '')

    # 10. Normaliza espaços múltiplos e linhas em branco
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo).strip()

    # 11. Escape de caracteres XML para SSML (Evita Erro 400 Google TTS)
    texto_limpo = texto_limpo.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    return texto_limpo

# Utility to format terminal output with colors and aligned columns
class ConsoleUI:
    # ANSI Color Codes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Colors
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    GRAY = "\033[90m"

    # NOVAS CORES GLOBAIS (Fase 13.8)
    C_SYS = "\033[96m"     # Ciano -> [SISTEMA]
    C_STT = "\033[96m"     # Ciano -> [STT]
    C_NYRA = "\033[95m"    # Magenta/Roxa -> [NYRA] / [HANA]
    C_TTS = "\033[95m"     # Roxa -> [TTS]
    C_MEM = "\033[94m"     # Azul -> [MEMÓRIA]
    C_VIS = "\033[92m"     # Verde -> [VISÃO]
    C_USER = "\033[93m"    # Amarelo -> Minha fala
    C_TEMP = "\033[96m"    # Ciano -> [TEMPERAMENTO]
    C_MOTOR = "\033[95m"   # Roxa -> [MOTOR / LLM]
    C_ERR = "\033[41;97m"  # Fundo Vermelho -> [ERRO] / [HEALTH]
    C_RST = "\033[0m"      # Reset

    def __init__(self, prefix="[HANA\\]"):
        self.prefix = prefix
        self.turno_atual = 1
        self.tempo_inicio_turno = 0.0

    def novo_turno(self):
        self.turno_atual += 1
        self.tempo_inicio_turno = time.time()

    def get_tempo_decorrido(self) -> str:
        if self.tempo_inicio_turno == 0:
            return "0s"
        return f"{int(time.time() - self.tempo_inicio_turno)}s"

    def _obter_hora(self) -> str:
        return time.strftime("[%H:%M:%S\\]")

    def print_linha(self, estado: str, cor: str, modulo_dir: str, icone_esq: str, icone_dir: str):
        """
        Gera uma linha formatada no estilo:
        [HANA\] [HH:MM:SS\] 👂 OUVINDO      | Turno: 21 |  0s | 🎤 ASR
        """
        hora = self._obter_hora()
        
        # Coluna 1: Prefixo, Hora, Ícone, Estado (Tamanho fixo approx 35 chars)
        col1 = f"{self.C_NYRA}{self.prefix}{self.C_RST} {self.GRAY}{hora}{self.C_RST} {icone_esq} {cor}{self.BOLD}{estado.ljust(12)}{self.C_RST}"
        
        # Coluna 2: Turno e Tempo
        tempo_str = self.get_tempo_decorrido()
        col2 = f"{self.GRAY}|{self.C_RST} Turno: {str(self.turno_atual).ljust(2)} {self.GRAY}|{self.C_RST} {tempo_str.rjust(3)} {self.GRAY}|{self.C_RST}"
        
        # Coluna 3: Ícone e Módulo
        col3 = f"{icone_dir} {cor}{modulo_dir}{self.C_RST}"

        # Monta a linha completa e limpa a linha atual do terminal (útil se estivermos sobrescrevendo mensagens)
        sys.stdout.write(f"\r\033[K{col1} {col2} {col3}\n")
        sys.stdout.flush()

    def print_ouvindo(self):
        self.print_linha("OUVINDO", self.C_SYS, "HUMANO", "👂", "👤")

    def print_pensando(self, provedor: str = "LLM_PROVIDER"):
        mod = provedor.upper()
        if len(mod) > 10: mod = mod[:10]
        self.print_linha("PENSANDO", self.C_MOTOR, mod, "🧠", "🎭")

    def print_falando(self, tts_provider: str = "TTS"):
        mod = tts_provider.upper()
        if len(mod) > 10: mod = mod[:10]
        self.print_linha("FALANDO", self.C_NYRA, mod, "🗣️", "🔊")

    def print_executando(self, tool_name: str):
        mod = tool_name.upper()
        if len(mod) > 10: mod = mod[:10]
        self.print_linha("EXECUTANDO", self.C_VIS, mod, "⚙️", "🔧")

    def print_erro(self, msg: str):
        hora = self._obter_hora()
        sys.stdout.write(f"\r\033[K{self.C_ERR}{self.prefix}{self.C_RST} {self.GRAY}{hora}{self.C_RST} [ERROR] {self.C_ERR}{self.BOLD}ERRO: {msg}{self.C_RST}\n")
        sys.stdout.flush()

    def print_info_livre(self, msg: str):
        # Aplicar cores baseadas em tags específicas para manter o padrão visual
        if msg.startswith("Você:"):
            msg = f"{self.C_USER}{msg}"
        elif "[STT]" in msg:
            msg = msg.replace("[STT]", f"{self.C_STT}[STT]{self.C_RST}")
        elif "[TTS]" in msg:
            msg = msg.replace("[TTS]", f"{self.C_TTS}[TTS]{self.C_RST}")
        elif "[TEMPERAMENTO]" in msg:
            msg = msg.replace("[TEMPERAMENTO]", f"{self.C_TEMP}[TEMPERAMENTO]{self.C_RST}")
        elif "[MOTOR" in msg:
            msg = msg.replace("[MOTOR", f"{self.C_MOTOR}[MOTOR")
            if "]" in msg:
                msg = msg.replace("]", f"]{self.C_RST}", 1) # Fecha a cor no primeiro ]
        
        hora = self._obter_hora()
        sys.stdout.write(f"\r\033[K{self.GRAY}{self.prefix} {hora} ℹ️ {msg}{self.C_RST}\n")
        sys.stdout.flush()

    def set_banner(self, stt_info: str, tts_info: str, provider_info: str = "", model_info: str = ""):
        """Imprime o banner de boot da Hana com STT, TTS, Provider e Modelo."""
        border = f"{self.BOLD}{self.C_NYRA}======================================================={self.C_RST}"
        
        print("\n" + border)
        print(f" {self.C_SYS}✨ HANA ONLINE E PRONTA PARA OUVIR ✨{self.C_RST}")
        print(f" {self.GRAY}STT: {self.BOLD}{stt_info}{self.C_RST}{self.GRAY} | TTS: {self.BOLD}{tts_info}{self.C_RST}")
        if provider_info:
            print(f" {self.GRAY}PROVEDOR: {self.BOLD}{provider_info}{self.C_RST}{self.GRAY} | LLM: {self.BOLD}{model_info}{self.C_RST}")
        print(f" {self.GRAY}Pressiona e segura a tecla configurada para falar.")
        print(f" Diz/Digite 'Desligar sistema' para encerrar.{self.C_RST}")
        print(border + "\n")

# Instância global para ser importada onde precisar (ex: no main.py)
ui = ConsoleUI()
