"""Lazy-loaded runtime state for WhatsApp API."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class WhatsAppState:
    def __init__(self):
        self.memory_manager = None
        self.llm_selector = None
        self._init_lock = asyncio.Lock()


async def ensure_state(state: WhatsAppState) -> WhatsAppState:
    async with state._init_lock:
        if state.llm_selector is None:
            from src.providers.provider_selector import ProviderSelector

            state.llm_selector = ProviderSelector()
            logger.info("[WHATSAPP API] LLM selector inicializado.")

        if state.memory_manager is None:
            from src.memory.memory_manager import LiraMemoryManager

            state.memory_manager = await asyncio.to_thread(LiraMemoryManager)
            logger.info("[WHATSAPP API] Memory manager inicializado.")
    return state