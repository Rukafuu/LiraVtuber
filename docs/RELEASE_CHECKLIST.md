# Release Checklist

Use esta lista antes de publicar uma versao no GitHub.

## Seguranca

- [ ] `.env` nao esta rastreado.
- [ ] `src/config/config.json` nao esta rastreado.
- [ ] credenciais JSON privadas nao estao rastreadas.
- [ ] memoria local em `data/` nao esta rastreada.
- [ ] logs e caches nao estao rastreados.
- [ ] README/docs nao contem chaves reais, bucket privado ou caminho local pessoal.

## Setup publico

- [ ] `src/config/config.example.json` existe e e valido.
- [ ] `src/config/persona.example.txt` existe e o runtime usa fallback se `persona.txt` local nao existir.
- [ ] `.env.example` so contem variaveis publicas/necessarias.
- [ ] Setup minimo documentado com `GROQ_API_KEY` + `edge`.
- [ ] `docs/INSTALL.md` explica instalacao do zero.
- [ ] `docs/INSTALL.md` menciona Python, Node.js e Rust para a GUI Tauri.
- [ ] `docs/CONFIG.md` explica config local.
- [ ] `docs/PROVIDERS.md` explica providers opcionais.
- [ ] `docs/TROUBLESHOOTING.md` explica erros comuns.

## GUI Tauri

- [ ] `control_panel` esta rastreado com `package.json`, `package-lock.json`, `src-tauri/Cargo.toml` e `Cargo.lock`.
- [ ] Nome do produto e identificador Tauri nao estao como template `control_panel`.
- [ ] Assets padrao Vite/Tauri nao usados foram removidos.
- [ ] `control_panel/node_modules`, `control_panel/dist` e `control_panel/src-tauri/target` nao estao rastreados.

## Video

- [ ] Prompts nao ensinam `<gerar_video>`.
- [ ] Runtime nao executa `<gerar_video>`.
- [ ] GUI nao executa `<gerar_video>`.
- [ ] Anexos de video continuam funcionando para analise.

## Validacao

- [ ] `python -m compileall main.py src`
- [ ] `python -m pytest -q`
- [ ] Teste manual do terminal com Groq + Edge.
- [ ] Teste manual da GUI.
- [ ] Teste manual de anexos no chat.
- [ ] Teste manual de stop `F8`.

