# Lira Control Center (HUD Tauri)

## Abrir a HUD

**Opção 1 — script na raiz do projeto:**

```bat
scripts\start_hud.bat
```

**Opção 2 — manual:**

```bat
cd control_panel
npm.cmd install
npm.cmd run tauri dev
```

A janela **LIRA — Control Center** deve abrir em ~30s (primeira vez pode levar alguns minutos por causa do build Rust).

## Requisitos

- Node.js 20+
- [WebView2](https://developer.microsoft.com/microsoft-edge/webview2/) (já vem no Windows 11; no 10 instale se a janela não abrir)
- Rust (instalado automaticamente na primeira vez que o Tauri compila)
- Control API rodando: `python apps/control_api/main.py` (porta 8042)

## Só tela preta ou “não abre”?

1. Não use só `npm run dev` — isso abre o site no navegador, não a HUD.
2. Use `npm run tauri dev` ou `scripts\start_hud.bat`.
3. Se a transparência do tema estiver em 0, reabra a HUD (corrigido no código; opacidade mínima 35%).
4. Confira se a porta **1425** está livre (feche outro `tauri dev` antigo).

## Build instalável

```bat
cd control_panel
npm.cmd run tauri build
```

O `.exe` fica em `src-tauri\target\release\`.