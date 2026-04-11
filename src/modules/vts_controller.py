"""
VTube Studio controller via pyvts com heartbeat, reconexão e estado real.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import pyvts

    PYVTS_OK = True
except ImportError:
    PYVTS_OK = False
    logger.warning("[VTS] pyvts não instalado. VTube Studio desabilitado.")


class VTSController:
    PLUGIN_NAME = "HanaAI"
    DEVELOPER_NAME = "Nakamura"
    TOKEN_PATH = os.path.abspath("data/vts_token.txt")
    STATE_PATH = os.path.abspath("data/vts_state.json")
    HEARTBEAT_SECONDS = 4.0
    ANIMATION_SECONDS = 0.05

    def __init__(self, host: str = "localhost", port: int = 8001, emotion_map: Dict[str, str] = None, signals=None):
        self.host = host
        self.port = int(port)
        self.emotion_map = emotion_map or {}
        self.signals = signals

        self.connected = False
        self.authenticated = False
        self.status = "idle"
        self.last_heartbeat_at = 0.0
        self.reconnect_attempts = 0
        self.tracking_mode = "injected_face_tracking"
        self.mouth_parameter = ""
        self._last_error = ""
        self._last_expression = ""
        self._mouth_level = 0.0

        self._vts: Optional[object] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._supervisor_task: Optional[asyncio.Task] = None
        self._animation_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        self._available_hotkeys: list = []
        self._available_expressions: list = []
        self._available_parameters: list = []
        self._supported_param_ids: set[str] = set()
        self._current_params: Dict[str, float] = {}
        self._tracking_active = True
        self._should_run = True
        self._write_state(status="idle")

    def _state_payload(self, status: str | None = None, last_error: str | None = None):
        return {
            "status": status or self.status,
            "connected": self.connected,
            "authenticated": self.authenticated,
            "host": self.host,
            "port": self.port,
            "hotkeys": len(self._available_hotkeys),
            "expressions": len(self._available_expressions),
            "updated_at": time.time(),
            "last_heartbeat_at": self.last_heartbeat_at,
            "reconnect_attempts": self.reconnect_attempts,
            "mouth_parameter": self.mouth_parameter,
            "tracking_mode": self.tracking_mode,
            "last_error": last_error if last_error is not None else self._last_error,
            "last_expression": self._last_expression,
        }

    def _write_state(self, status: str | None = None, last_error: str | None = None):
        if status is not None:
            self.status = status
        if last_error is not None:
            self._last_error = last_error
        payload = self._state_payload(status=status, last_error=last_error)
        os.makedirs(os.path.dirname(self.STATE_PATH), exist_ok=True)
        with open(self.STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def start(self):
        if not PYVTS_OK:
            self._write_state(status="error", last_error="pyvts não instalado")
            logger.error("[VTS] pyvts não está instalado. Execute: pip install pyvts")
            return False

        if self._thread and self._thread.is_alive():
            return True

        self._should_run = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="VTS-Controller")
        self._thread.start()
        return True

    def stop(self):
        self._should_run = False

        if self._loop and self._loop.is_running():
            if self._supervisor_task:
                self._loop.call_soon_threadsafe(self._supervisor_task.cancel)
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=4)

        self.connected = False
        self.authenticated = False
        self._write_state(status="stopped")

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._supervisor_task = self._loop.create_task(self._supervisor_loop())
        try:
            self._loop.run_forever()
        except Exception as e:
            self.connected = False
            self.authenticated = False
            self._write_state(status="error", last_error=str(e))
            logger.error("[VTS] Erro fatal no loop: %s", e)
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                try:
                    self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
            try:
                self._loop.close()
            except Exception:
                pass

    async def _supervisor_loop(self):
        backoff = 1.0
        while self._should_run:
            try:
                await self._connect_and_auth()
                await self._load_available_actions()
                self._detect_mouth_parameter()
                self.reconnect_attempts = 0
                self._write_state(status="ready", last_error="")
                backoff = 1.0

                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="VTS-heartbeat")
                self._animation_task = asyncio.create_task(self._animation_loop(), name="VTS-animation")

                done, pending = await asyncio.wait(
                    [self._heartbeat_task, self._animation_task],
                    return_when=asyncio.FIRST_EXCEPTION,
                )
                for task in pending:
                    task.cancel()
                for task in done:
                    exc = task.exception()
                    if exc:
                        raise exc

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.connected = False
                self.authenticated = False
                self.reconnect_attempts += 1
                self._write_state(status="reconnecting", last_error=str(e))
                logger.warning("[VTS] Conexão perdida, reconectando: %s", e)
                await self._safe_disconnect()
                if not self._should_run:
                    break
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 15.0)
                continue
            finally:
                await self._safe_disconnect()

        self.connected = False
        self.authenticated = False
        self._write_state(status="stopped")
        if self._loop and self._loop.is_running():
            self._loop.stop()

    async def _connect_and_auth(self):
        self._write_state(status="connecting", last_error="")
        plugin_info = {
            "plugin_name": self.PLUGIN_NAME,
            "developer": self.DEVELOPER_NAME,
            "authentication_token_path": self.TOKEN_PATH,
        }
        api_info = {
            "version": "1.0",
            "name": "VTubeStudioPublicAPI",
            "host": self.host,
            "port": self.port,
        }

        self._vts = pyvts.vts(plugin_info=plugin_info, vts_api_info=api_info)
        await self._vts.connect()
        self.connected = True
        self._write_state(status="connected", last_error="")
        logger.info("[VTS] Conectado ao VTube Studio em %s:%s", self.host, self.port)

        token = self._read_token_file()
        if token:
            try:
                await self._vts.request_authenticate(token)
                self.authenticated = True
                self._write_state(status="authenticated", last_error="")
                logger.info("[VTS] Autenticado com token salvo.")
                return
            except Exception as e:
                logger.warning("[VTS] Token salvo inválido, solicitando novo: %s", e)
                token = None

        self._write_state(status="awaiting_auth", last_error="")
        response = await self._vts.request_authenticate_token(force=True)
        if isinstance(response, str):
            token = response
        elif isinstance(response, dict):
            token = response.get("data", {}).get("authenticationToken")

        if not token:
            raise RuntimeError("token de autenticação não recebido")

        self._write_token_file(token)
        await self._vts.request_authenticate(token)
        self.authenticated = True
        self._write_state(status="authenticated", last_error="")
        logger.info("[VTS] Novo token obtido e autenticado com sucesso.")

    def _read_token_file(self):
        if not os.path.exists(self.TOKEN_PATH):
            return None
        try:
            with open(self.TOKEN_PATH, "r", encoding="utf-8") as f:
                return f.read().strip() or None
        except Exception:
            return None

    def _write_token_file(self, token: str):
        os.makedirs(os.path.dirname(self.TOKEN_PATH), exist_ok=True)
        with open(self.TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(str(token))

    async def _load_available_actions(self):
        self._available_hotkeys = []
        self._available_expressions = []
        self._available_parameters = []
        self._supported_param_ids = set()

        try:
            response = await self._vts.request(self._vts.vts_request.requestHotKeyList())
            if response and "data" in response:
                self._available_hotkeys = response["data"].get("availableHotkeys", [])
        except Exception as e:
            logger.warning("[VTS] Erro ao carregar hotkeys: %s", e)

        try:
            response = await self._vts.request(self._vts.vts_request.requestExpressionState())
            if response and "data" in response:
                self._available_expressions = response["data"].get("expressions", [])
        except Exception as e:
            logger.warning("[VTS] Erro ao carregar expressões: %s", e)

        for request in (
            self._vts.vts_request.requestTrackingParameterList(),
            self._vts.vts_request.BaseRequest("CurrentModelRequest", {}),
        ):
            try:
                response = await self._vts.request(request)
            except Exception:
                continue
            if not response or "data" not in response:
                continue
            for key in ("modelParameters", "parameters", "trackingParameters", "availableParameters"):
                values = response["data"].get(key)
                if isinstance(values, list):
                    self._available_parameters.extend(values)

        for item in self._available_parameters:
            if isinstance(item, dict):
                candidate = item.get("id") or item.get("name")
            else:
                candidate = str(item)
            if candidate:
                self._supported_param_ids.add(candidate)

    def _detect_mouth_parameter(self):
        priorities = [
            "ParamMouthOpenY",
            "ParamMouthOpen",
            "ParamMouthSmile",
            "ParamMouthA",
            "ParamJawOpen",
        ]
        self.mouth_parameter = ""
        for candidate in priorities:
            if candidate in self._supported_param_ids:
                self.mouth_parameter = candidate
                break
        if not self.mouth_parameter:
            self.mouth_parameter = "ParamMouthOpenY"

    async def _heartbeat_loop(self):
        while self._should_run and self.connected and self.authenticated:
            try:
                await self._vts.request(self._vts.vts_request.requestHotKeyList())
                self.last_heartbeat_at = time.time()
                self._write_state(status="ready", last_error="")
            except Exception as e:
                raise RuntimeError(f"heartbeat falhou: {e}") from e
            await asyncio.sleep(self.HEARTBEAT_SECONDS)

    async def _animation_loop(self):
        import math
        import random

        t = 0.0
        target_x, target_y = 0.0, 0.0
        current_x, current_y = 0.0, 0.0

        while self._should_run and self.connected and self.authenticated:
            t += 0.05
            if random.random() < 0.04:
                target_x = random.uniform(-15, 15)
                target_y = random.uniform(-10, 10)

            current_x += (target_x - current_x) * 0.1
            current_y += (target_y - current_y) * 0.1
            angle_z = math.sin(t * 0.5) * 4
            breath = (math.sin(t * 1.5) + 1) / 2
            is_speaking = bool(self.signals and getattr(self.signals, "HANA_SPEAKING", False))

            eye_open = 1.0
            if random.random() < 0.02 or (t % 4.0 < 0.15):
                eye_open = 0.0

            mouth_target = 0.72 if is_speaking else 0.0
            self._mouth_level += (mouth_target - self._mouth_level) * 0.25
            mouth_value = self._mouth_level
            if is_speaking:
                mouth_value = max(0.0, min(1.0, mouth_value + ((math.sin(t * 10) + 1) / 2) * 0.12))

            params = {
                "ParamAngleX": current_x,
                "ParamAngleY": current_y + (math.sin(t * 4) * 1.2 if is_speaking else 0.0),
                "ParamAngleZ": angle_z,
                "ParamBreath": breath,
                "ParamEyeLOpen": eye_open,
                "ParamEyeROpen": eye_open,
                "ParamEyeBallX": current_x / 15.0,
                "ParamEyeBallY": current_y / 10.0,
            }
            if self.mouth_parameter:
                params[self.mouth_parameter] = mouth_value

            await self._send_multi_parameters(params)
            await asyncio.sleep(self.ANIMATION_SECONDS)

    async def _send_multi_parameters(self, params: Dict[str, float]):
        if not self._vts:
            return

        supported = {key: value for key, value in params.items() if not self._supported_param_ids or key in self._supported_param_ids}
        if not supported:
            return

        request = self._vts.vts_request.requestSetMultiParameterValue(
            list(supported.keys()),
            list(supported.values()),
            face_found=True,
            mode="set",
        )
        await self._vts.request(request)
        self._current_params.update(supported)

    async def _safe_disconnect(self):
        for task in (self._animation_task, self._heartbeat_task):
            if task and not task.done():
                task.cancel()
        self._animation_task = None
        self._heartbeat_task = None

        if self._vts:
            try:
                await self._vts.close()
            except Exception:
                pass
        self._vts = None
        self.connected = False
        self.authenticated = False

    def set_parameter(self, name: str, value: float):
        if not self.authenticated or not self._loop:
            return
        asyncio.run_coroutine_threadsafe(self._send_parameter(name, value), self._loop)

    async def _send_parameter(self, name: str, value: float):
        try:
            if self._supported_param_ids and name not in self._supported_param_ids:
                return
            request = self._vts.vts_request.requestSetParameterValue(name, value, face_found=True, mode="set")
            await self._vts.request(request)
            self._current_params[name] = value
        except Exception as e:
            logger.error("[VTS] Erro ao definir parâmetro %s: %s", name, e)

    def trigger_emotion(self, emotion: str):
        if not self.authenticated or not self._loop:
            return
        hotkey_name = self.emotion_map.get(str(emotion or "").upper())
        if not hotkey_name:
            return
        asyncio.run_coroutine_threadsafe(self._send_hotkey(hotkey_name), self._loop)

    async def _send_hotkey(self, hotkey_name: str):
        hotkey_id = None
        for hk in self._available_hotkeys:
            if hk.get("name", "").lower() == hotkey_name.lower():
                hotkey_id = hk.get("hotkeyID")
                break

        try:
            if hotkey_id:
                await self._vts.request(self._vts.vts_request.requestTriggerHotKey(hotkey_id))
                self._last_expression = hotkey_name
                self._write_state(status="ready", last_error="")
                return
            await self._send_expression(hotkey_name)
        except Exception as e:
            logger.error("[VTS] Erro ao disparar hotkey '%s': %s", hotkey_name, e)

    async def _send_expression(self, expression_name: str):
        try:
            for expr in self._available_expressions:
                file_name = expr.get("name", "")
                if expression_name.lower() in file_name.lower():
                    request = self._vts.vts_request.requestExpressionActivation(file_name, active=True)
                    await self._vts.request(request)
                    self._last_expression = file_name
                    self._write_state(status="ready", last_error="")
                    asyncio.create_task(self._delayed_reset(5, express_file=file_name))
                    return
        except Exception as e:
            logger.error("[VTS] Erro ao ativar expressão: %s", e)

    async def _delayed_reset(self, delay: int, express_file: str = None):
        await asyncio.sleep(delay)
        try:
            if express_file:
                request = self._vts.vts_request.requestExpressionActivation(express_file, active=False)
                await self._vts.request(request)
        except Exception:
            pass

    def get_anatomy_detailed(self) -> str:
        details = []
        if self._available_expressions:
            details.append(f"- Expressoes: {', '.join([e.get('name') for e in self._available_expressions])}")
        if self.mouth_parameter:
            details.append(f"- Parametro de boca: {self.mouth_parameter}")

        p_list = []
        for p in self._available_parameters:
            if isinstance(p, dict):
                name = p.get("name") or p.get("id", "")
                min_val = p.get("min")
                max_val = p.get("max")
            else:
                name = str(p)
                min_val = "?"
                max_val = "?"
            if not str(name).startswith("Param"):
                continue
            if name in {"ParamAngleX", "ParamAngleY", "ParamAngleZ", "ParamBreath", "ParamEyeLOpen", "ParamEyeROpen"}:
                continue
            p_list.append(f"{name} ({min_val} a {max_val})")

        if p_list:
            details.append(f"- Parametros customizados: {', '.join(p_list)}")

        return "\n".join(details)
