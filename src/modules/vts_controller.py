"""
VTube Studio Controller — Controla expressões do avatar via WebSocket (pyvts).

Conecta na API do VTube Studio (porta 8001 por padrão) e permite:
  - Autenticação automática (salva token em data/vts_token.txt)
  - Disparar expressões/hotkeys baseadas em emoções
  - Enviar parâmetros customizados (ex: HanaMood)
"""

import asyncio
import logging
import os
import threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# pyvts é importado no momento de uso para evitar crash se não estiver instalado
try:
    import pyvts
    PYVTS_OK = True
except ImportError:
    PYVTS_OK = False
    logger.warning("[VTS] pyvts não instalado. VTube Studio desabilitado.")


class VTSController:
    """Controller assíncrono para o VTube Studio via pyvts."""

    PLUGIN_NAME = "HanaAI"
    DEVELOPER_NAME = "Nakamura"
    TOKEN_PATH = os.path.abspath("data/vts_token.txt")

    def __init__(self, host: str = "localhost", port: int = 8001, emotion_map: Dict[str, str] = None):
        self.host = host
        self.port = port
        self.emotion_map = emotion_map or {}
        self.connected = False
        self.authenticated = False
        self._vts: Optional[object] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._available_hotkeys: list = []
        self._available_expressions: list = []

    def start(self):
        """Inicia o controller em uma thread separada com seu próprio event loop."""
        if not PYVTS_OK:
            logger.error("[VTS] pyvts não está instalado. Execute: pip install pyvts")
            return False

        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="VTS-Controller")
        self._thread.start()
        return True

    def stop(self):
        """Para o controller e fecha a conexão."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._disconnect(), self._loop)
        self.connected = False
        self.authenticated = False

    def _run_loop(self):
        """Thread principal do controller com event loop próprio."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_and_auth())
        except Exception as e:
            logger.error(f"[VTS] Erro no loop: {e}")
            self.connected = False

    async def _connect_and_auth(self):
        """Conecta e autentica com o VTube Studio."""
        try:
            plugin_info = {
                "plugin_name": self.PLUGIN_NAME,
                "developer": self.DEVELOPER_NAME,
                "authentication_token_path": self.TOKEN_PATH
            }

            self._vts = pyvts.vts(plugin_info=plugin_info)

            # Conecta ao WebSocket
            await self._vts.connect()
            self.connected = True
            logger.info(f"[VTS] Conectado ao VTube Studio em {self.host}:{self.port}")

            # Tenta ler token salvo
            token = None
            if os.path.exists(self.TOKEN_PATH):
                try:
                    with open(self.TOKEN_PATH, "r") as f:
                        token = f.read().strip()
                except Exception:
                    pass

            if token:
                # Tenta autenticar com token existente
                try:
                    await self._vts.request_authenticate(token)
                    self.authenticated = True
                    logger.info("[VTS] Autenticado com token salvo.")
                except Exception:
                    logger.info("[VTS] Token expirado, solicitando novo...")
                    token = None

            if not token:
                # Solicita novo token (popup no VTS para o usuário clicar Allow)
                try:
                    response = await self._vts.request_authenticate_token()
                    # pyvts pode retornar o token de formas diferentes
                    if isinstance(response, str):
                        token = response
                    elif isinstance(response, dict):
                        token = response.get("data", {}).get("authenticationToken")
                    
                    if not token:
                        logger.error("[VTS] Token de autenticação não recebido. Clique 'Allow' no popup do VTube Studio.")
                        self.authenticated = False
                        return

                    # Salva o token
                    os.makedirs(os.path.dirname(self.TOKEN_PATH), exist_ok=True)
                    with open(self.TOKEN_PATH, "w") as f:
                        f.write(str(token))
                    # Autentica com o novo token
                    await self._vts.request_authenticate(token)
                    self.authenticated = True
                    logger.info("[VTS] Novo token obtido e autenticado com sucesso.")
                except Exception as e:
                    logger.error(f"[VTS] Falha na autenticação: {e}")
                    self.authenticated = False
                    return

            # Carrega hotkeys e expressões disponíveis
            await self._load_available_actions()

            logger.info(f"[VTS] Pronto! {len(self._available_hotkeys)} hotkeys, {len(self._available_expressions)} expressões disponíveis.")

        except Exception as e:
            logger.error(f"[VTS] Erro ao conectar: {e}")
            self.connected = False

    async def _load_available_actions(self):
        """Carrega hotkeys e expressões disponíveis do modelo atual."""
        try:
            response = await self._vts.request(self._vts.vts_request.requestHotKeyList())
            if response and "data" in response:
                self._available_hotkeys = response["data"].get("availableHotkeys", [])
        except Exception as e:
            logger.warning(f"[VTS] Erro ao carregar hotkeys: {e}")

        try:
            response = await self._vts.request(self._vts.vts_request.requestExpressionState())
            if response and "data" in response:
                self._available_expressions = response["data"].get("expressions", [])
        except Exception as e:
            logger.warning(f"[VTS] Erro ao carregar expressões: {e}")

    async def _disconnect(self):
        """Desconecta do VTube Studio."""
        try:
            if self._vts:
                await self._vts.close()
        except Exception:
            pass
        self.connected = False
        self.authenticated = False

    def trigger_emotion(self, emotion: str):
        """
        Dispara uma expressão/hotkey baseada na emoção.
        Chamado pela EmotionEngine via callback.
        """
        if not self.authenticated or not self._loop:
            return

        emotion_upper = emotion.upper()
        hotkey_name = self.emotion_map.get(emotion_upper)

        if not hotkey_name:
            logger.debug(f"[VTS] Sem mapeamento para emoção: {emotion_upper}")
            return

        try:
            asyncio.run_coroutine_threadsafe(
                self._send_hotkey(hotkey_name),
                self._loop
            )
        except Exception as e:
            logger.error(f"[VTS] Erro ao disparar emoção {emotion_upper}: {e}")

    async def _send_hotkey(self, hotkey_name: str):
        """Envia um hotkey para o VTube Studio."""
        try:
            # Procura o hotkey pelo nome
            hotkey_id = None
            for hk in self._available_hotkeys:
                if hk.get("name", "").lower() == hotkey_name.lower():
                    hotkey_id = hk.get("hotkeyID")
                    break

            if hotkey_id:
                request = self._vts.vts_request.requestTriggerHotKey(hotkey_id)
                await self._vts.request(request)
                logger.info(f"[VTS] Hotkey disparada: {hotkey_name}")
            else:
                # Tenta como expressão
                await self._send_expression(hotkey_name)

        except Exception as e:
            logger.error(f"[VTS] Erro ao enviar hotkey '{hotkey_name}': {e}")

    async def _send_expression(self, expression_name: str):
        """Ativa uma expressão no VTube Studio."""
        try:
            for expr in self._available_expressions:
                file_name = expr.get("name", "")
                if expression_name.lower() in file_name.lower():
                    request = self._vts.vts_request.requestExpressionActivation(
                        file_name, active=True
                    )
                    await self._vts.request(request)
                    logger.info(f"[VTS] Expressão ativada: {file_name}")
                    return
            logger.warning(f"[VTS] Expressão não encontrada: {expression_name}")
        except Exception as e:
            logger.error(f"[VTS] Erro ao ativar expressão: {e}")

    def get_available_hotkeys(self) -> list:
        """Retorna lista de nomes de hotkeys disponíveis."""
        return [hk.get("name", "?") for hk in self._available_hotkeys]

    def get_available_expressions(self) -> list:
        """Retorna lista de nomes de expressões disponíveis."""
        return [expr.get("name", "?") for expr in self._available_expressions]
