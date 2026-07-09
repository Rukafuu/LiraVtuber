import asyncio
import logging
from fastapi import APIRouter, HTTPException

from apps.control_api.service_manager import service_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("")
async def list_services():
    return service_manager.status_all()


@router.get("/whatsapp_bridge/session")
async def whatsapp_bridge_session():
    """QR WhatsApp dinâmico + código de pareamento (poll ~1–2s na HUD)."""
    return service_manager.whatsapp_session()


@router.post("/whatsapp_bridge/reset-session")
async def whatsapp_reset_session():
    """Apaga auth Baileys e QR — use quando loggedOut / device_removed / QR some rápido."""
    return await asyncio.to_thread(service_manager.reset_whatsapp_session)


@router.get("/{service_id}")
async def get_service_status(service_id: str):
    data = service_manager.status_one(service_id)
    if not data:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    return data


@router.post("/{service_id}/start")
async def start_service(service_id: str):
    return await asyncio.to_thread(service_manager.start, service_id)


@router.post("/{service_id}/stop")
async def stop_service(service_id: str):
    return await asyncio.to_thread(service_manager.stop, service_id)


@router.get("/{service_id}/logs")
async def get_service_logs(service_id: str, limit: int = 80):
    if service_manager.status_one(service_id) is None:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    return {"logs": service_manager.logs(service_id, limit=limit)}
