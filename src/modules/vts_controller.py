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

    def __init__(self, host: str = "localhost", port: int = 8001, emotion_map: Dict[str, str] = None, signals = None):
        self.host = host
        self.port = port
        self.emotion_map = emotion_map or {}
        self.signals = signals
        self.connected = False
        self.authenticated = False
        self._vts: Optional[object] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._available_hotkeys: list = []
        self._available_expressions: list = []
        self._available_parameters: list = []
        self._current_params: Dict[str, float] = {}
        self._tracking_active = True # Bypass Head Tracking by default

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
            # Inicia o loop de tracking/alma se autenticado
            if self.authenticated:
                self._loop.create_task(self._wander_loop())
            self._loop.run_forever()
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

            # Carrega hotkeys, expressões e parâmetros
            await self._load_available_actions()

            logger.info(f"[VTS] Pronto! {len(self._available_hotkeys)} hotkeys, {len(self._available_expressions)} expressões, {len(self._available_parameters)} parâmetros.")

        except Exception as e:
            logger.error(f"[VTS] Erro ao conectar: {e}")
            self.connected = False

    async def _load_available_actions(self):
        """Carrega hotkeys, expressões e parâmetros do modelo atual."""
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

        try:
            # Requisita detalhes do modelo para pegar parâmetros
            request = self._vts.vts_request.BaseRequest("CurrentModelRequest", {})
            response = await self._vts.request(request)
            if response and "data" in response:
                self._available_parameters = response["data"].get("modelParameters", [])
        except Exception as e:
            logger.warning(f"[VTS] Erro ao carregar parâmetros: {e}")

    async def _disconnect(self):
        """Desconecta do VTube Studio."""
        try:
            if self._vts:
                await self._vts.close()
        except Exception:
            pass
        self.connected = False
        self.authenticated = False

    def set_parameter(self, name: str, value: float):
        """Define o valor de um parâmetro de forma assíncrona."""
        if not self.authenticated or not self._loop:
            return

        asyncio.run_coroutine_threadsafe(
            self._send_parameter(name, value),
            self._loop
        )

    async def _send_parameter(self, name: str, value: float):
        """Envia o comando de parâmetro para o VTS."""
        try:
            # Filtra parâmetros conhecidos que mudam rápido (não queremos logar eles)
            if name not in ["ParamAngleX", "ParamAngleY", "ParamAngleZ", "ParamBreath"]:
                logger.info(f"[VTS] Setting Parameter: {name} = {value}")
            
            # Request de parâmetro individual (usado para parâmetros que ficam salvos)
            request = self._vts.vts_request.requestSetParameterValue(name, value)
            await self._vts.request(request)
            self._current_params[name] = value
        except Exception as e:
            logger.error(f"[VTS] Erro ao definir parâmetro {name}: {e}")

    def trigger_emotion(self, emotion: str):
        """Dispara uma expressão via callback da EmotionEngine."""
        if not self.authenticated or not self._loop:
            return

        emotion_upper = emotion.upper()
        hotkey_name = self.emotion_map.get(emotion_upper)

        if not hotkey_name:
            logger.debug(f"[VTS] Sem mapeamento para emoção: {emotion_upper}")
            return

        asyncio.run_coroutine_threadsafe(self._send_hotkey(hotkey_name), self._loop)

    async def _send_hotkey(self, hotkey_name: str):
        """Envia um hotkey/expressão para o VTube Studio."""
        try:
            hotkey_id = None
            for hk in self._available_hotkeys:
                if hk.get("name", "").lower() == hotkey_name.lower():
                    hotkey_id = hk.get("hotkeyID")
                    break

            if hotkey_id:
                request = self._vts.vts_request.requestTriggerHotKey(hotkey_id)
                await self._vts.request(request)
                logger.info(f"[VTS] Hotkey disparada: {hotkey_name}")
                # Auto-reset após 5 segundos (comportamento da Neuro)
                asyncio.create_task(self._delayed_reset(5))
            else:
                await self._send_expression(hotkey_name)
        except Exception as e:
            logger.error(f"[VTS] Erro ao enviar hotkey '{hotkey_name}': {e}")

    async def _send_expression(self, expression_name: str):
        """Ativa uma expressão (pelo nome do arquivo .exp3.json)."""
        try:
            for expr in self._available_expressions:
                file_name = expr.get("name", "")
                if expression_name.lower() in file_name.lower():
                    request = self._vts.vts_request.requestExpressionActivation(file_name, active=True)
                    await self._vts.request(request)
                    logger.info(f"[VTS] Expressão ativada: {file_name}")
                    asyncio.create_task(self._delayed_reset(5, express_file=file_name))
                    return
            logger.warning(f"[VTS] Ação não encontrada (hotkey/expressão): {expression_name}")
        except Exception as e:
            logger.error(f"[VTS] Erro ao ativar expressão: {e}")

    async def _delayed_reset(self, delay: int, express_file: str = None):
        """Reseta expressões após um delay."""
        await asyncio.sleep(delay)
        try:
            if express_file:
                # Desativa expressão específica
                request = self._vts.vts_request.requestExpressionActivation(express_file, active=False)
                await self._vts.request(request)
            else:
                # Tenta achar o hotkey de reset global (Remove All Expressions)
                reset_hk = None
                for hk in self._available_hotkeys:
                    if hk.get("action") == "RemoveAllExpressions" or "RESET" in hk.get("name", "").upper():
                        reset_hk = hk.get("hotkeyID")
                        break
                if reset_hk:
                    await self._vts.request(self._vts.vts_request.requestTriggerHotKey(reset_hk))
        except Exception:
            pass

    async def _wander_loop(self):
        """Alma da Hana: Tracking Fantasma (Head Tracking Tracking Bypass)."""
        import math, random
        logger.info("[VTS] Iniciando 'Alma' (Tracking Tracking Bypass)...")
        t = 0.0
        target_x, target_y = 0, 0
        current_x, current_y = 0, 0
        
        while self.connected:
            if not self._tracking_active:
                await asyncio.sleep(0.5)
                continue
                
            t += 0.05
            if random.random() < 0.04:
                target_x = random.uniform(-15, 15)
                target_y = random.uniform(-10, 10)
                
            current_x += (target_x - current_x) * 0.1
            current_y += (target_y - current_y) * 0.1
            
            angle_z = math.sin(t * 0.5) * 4
            breath = (math.sin(t * 1.5) + 1) / 2
            
            # Se a Hana estiver falando (através de um sinal que podemos injetar no main), amplificamos o movimento
            # (Note: self.signals deve ser passado na inicialização se quisermos sincronia total)
            is_speaking = False
            if self.signals and getattr(self.signals, "HANA_SPEAKING", False):
                is_speaking = True
                
            if is_speaking:
                current_y += math.sin(t * 4) * 2
                current_x += math.cos(t * 2) * 1
                
            eye_open = 1.0
            if random.random() < 0.02 or (t % 4.0 < 0.15):
                eye_open = 0.0
                
            # Injeção em lote para performance (InjectParameterData)
            vts_params = [
                {"id": "ParamAngleX", "value": current_x, "weight": 1},
                {"id": "ParamAngleY", "value": current_y, "weight": 1},
                {"id": "ParamAngleZ", "value": angle_z, "weight": 1},
                {"id": "ParamBreath", "value": breath, "weight": 1},
                {"id": "ParamEyeLOpen", "value": eye_open, "weight": 1},
                {"id": "ParamEyeROpen", "value": eye_open, "weight": 1},
                {"id": "ParamEyeBallX", "value": current_x / 15.0, "weight": 1},
                {"id": "ParamEyeBallY", "value": current_y / 10.0, "weight": 1}
            ]
            
            request = self._vts.vts_request.BaseRequest(
                "InjectParameterDataRequest",
                {"faceFound": False, "mode": "set", "parameterValues": vts_params}
            )
            try:
                await self._vts.request(request)
            except Exception:
                pass
            await asyncio.sleep(0.05) # ~20 FPS

    def get_anatomy_detailed(self) -> str:
        """Retorna uma string descrevendo expressões e parâmetros para o prompt."""
        details = []
        if self._available_expressions:
            details.append(f"- Expressões: {', '.join([e.get('name') for e in self._available_expressions])}")
        
        p_list = []
        for p in self._available_parameters:
            name = p.get('name', p.get('id', ''))
            if not name.startswith("Param"): continue
            # Pula os básicos de tracking pois o wander_loop já cuida e mudam demais
            if name in ["ParamAngleX", "ParamAngleY", "ParamAngleZ", "ParamBreath", "ParamEyeLOpen", "ParamEyeROpen"]:
                continue
            p_list.append(f"{name} ({p.get('min')} a {p.get('max')})")
        
        if p_list:
            details.append(f"- Parâmetros Customizados: {', '.join(p_list)}")
        
        return "\n".join(details)


    def get_available_hotkeys(self) -> list:
        """Retorna lista de nomes de hotkeys disponíveis."""
        return [hk.get("name", "?") for hk in self._available_hotkeys]

    def get_available_expressions(self) -> list:
        """Retorna lista de nomes de expressões disponíveis."""
        return [expr.get("name", "?") for expr in self._available_expressions]
