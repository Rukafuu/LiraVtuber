# Desenvolvimento — LiraVT

## Entrypoints

| Serviço | Comando | Porta |
|---------|---------|-------|
| VTuber (terminal) | `python apps/vtuber/main.py` | — |
| Control API + HUD | `python apps/control_api/main.py` | 8042 |
| WhatsApp API | `python apps/whatsapp_api/main.py` | 8043 |
| WhatsApp bridge | `cd whatsapp_bridge && node index.js` | — |
| Discord bot | `python -m src.modules.discord_bot` | — |
| Control Center (Tauri HUD) | `scripts\start_hud.bat` ou `cd control_panel && npm.cmd run tauri dev` | 1425 (Vite) |

## Control API — startup lento?

Por padrao `CONTROL_API_LIGHT_START=1` evita carregar Chroma/SentenceTransformer antes do servidor subir (isso podia parecer “travado” por varios minutos no log do RAG).

Para vetorial completo na API (em background): `CONTROL_API_RAG_CHROMA=1` no `.env`.

## Testes

```bash
pytest -q tests/
```

## Pacotes

- `packages/lira-core/` — memória, tools XML, utilitários compartilhados
- `src/modules/` — Discord, voz, visão, mídia, etc.
- `apps/` — processos deployáveis (VTuber, APIs)