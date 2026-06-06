"""FastAPI app dedicada ao bridge WhatsApp."""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.whatsapp_api.service import handle_chat, synthesize_tts
from apps.whatsapp_api.state import WhatsAppState, ensure_state

load_dotenv(encoding="utf-8-sig")
logger = logging.getLogger(__name__)

app = FastAPI(title="Lira WhatsApp API", version="1.0.0")
app.state.whatsapp = WhatsAppState()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "whatsapp-api",
        "port": int(os.getenv("WHATSAPP_API_PORT", "8043")),
    }


@app.post("/api/whatsapp/chat")
async def whatsapp_chat(payload: dict):
    state = await ensure_state(app.state.whatsapp)
    return await handle_chat(payload, state)


@app.post("/api/whatsapp/tts")
async def whatsapp_tts(payload: dict):
    return await synthesize_tts(payload)