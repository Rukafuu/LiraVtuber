# Lira WhatsApp API

FastAPI dedicada ao bridge Baileys (separada do Control Center na porta 8042).

```bash
python apps/whatsapp_api/main.py
```

Bridge: `cd whatsapp_bridge && node index.js` — configure `WHATSAPP_API_URL=http://127.0.0.1:8043` no `.env`.

HUD: aba **Plataformas** no `control_panel` (liga API + bridge, QR dinâmico).