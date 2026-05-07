# Plano de limpeza para release publico

Este documento registra o estado atual da Lira antes do push publico e define a ordem segura de limpeza. Ele nao substitui o checklist final em `docs/RELEASE_CHECKLIST.md`.

## Objetivo

- Publicar a versao nova com GUI Tauri sem vazar config local, memoria, persona privada ou artefatos de build.
- Manter a instalacao facil para outro PC, com `.env.example`, `config.example.json` e docs claras.
- A GUI antiga em CustomTkinter foi removida do runtime publico depois de extrair o popup de confirmacao do controle do PC.

## Achados criticos

- Resolvido na fase 5: `src/config/persona.txt` saiu do indice e `src/config/persona.example.txt` foi criado como persona publica.
- Resolvido na fase 5: `data/emotion_state.json` saiu do indice; continua local e ignorado.
- Resolvido na fase 5: `test_image_b64.py`, `test_part.py` e `test_upload.py` sairam do indice e ficam ignorados como scripts locais.
- Resolvido na fase 4: `src/modules/tools/pc_control.py` nao depende mais de `src.gui`; o popup foi movido para `src/modules/tools/pc_action_popup.py`.
- A GUI Tauri nova esta em `control_panel/`, mas ainda nao esta preparada como release publico: nome do produto, icone, launch mode e configuracao de backend ainda estao em modo dev/local.

## Bloqueadores de codigo antes do push

1. Higiene Git e segredos

- Resolvido na fase 5: `src/config/persona.txt`, `data/emotion_state.json` e scripts locais de teste na raiz sairam do indice sem apagar do disco.
- Conferir se `src/config/config.json`, `src/config/service_account.json`, `.env`, `data/memory/`, `temp/`, `node_modules/` e targets Tauri nao entram no commit.
- Criar ou revisar arquivos publicos de exemplo: `.env.example`, `src/config/config.example.json` e persona publica padrao. Persona publica criada em `src/config/persona.example.txt`.

2. GUI antiga CustomTkinter

- Resolvido na fase 4.
- `pc_action_popup.py` foi extraido para `src/modules/tools/pc_action_popup.py`.
- `src/gui/` foi removido do codigo rastreado.
- `customtkinter`, `tkinterdnd2` e `pywinstyles` foram removidos de `requirements.txt`.

3. Chat Tauri e pipeline da LLM

- Separar o contexto do chat visual do contexto do terminal com voz. Hoje `/ws/chat` usa `get_terminal_context_state`, o que favorece confusao entre canal GUI e terminal.
- Parar de mutar o objeto retornado por `llm_selector.get_provider()` dentro de `src/api/server.py`. O provider/modelo do chat deve ser resolvido por config de forma explicita, sem alterar objeto compartilhado indevidamente.
- Usar o `task_type` correto no `request_context`; hoje o prompt classifica a tarefa, mas a chamada da LLM envia `task_type="chat_normal"`.
- Enviar imagem anexada no formato esperado pelo provider, removendo prefixo `data:image/...;base64,` quando necessario.
- Processar `editar_imagem` e `editar_imagem_personagem` no backend do chat; atualmente essas tags sao extraidas, mas nao executadas.
- Salvar no historico apenas texto visivel e resultado do turno atual, sem XML silencioso, e evitar que tags antigas sejam reaproveitadas.
- Para markdown, evitar quebrar a resposta por `SentenceDivider` se isso corromper listas, titulos e blocos de codigo no ReactMarkdown.

4. Frontend Tauri

- Em `TabChat.tsx`, persistir provider/modelo selecionados antes de enviar ou mandar provider/modelo no payload do websocket.
- Adicionar limpar conversa/historico visual e limitar renderizacao de mensagens longas para nao travar o chat.
- Suportar anexos alem de imagens quando o backend estiver pronto, mas priorizar imagem/analise/edicao primeiro.
- Em `TabMemoria.tsx`, adicionar `ver mais`, criar, editar e apagar com confirmacao clara.
- Em `TabLLM.tsx`, mover o botao `SALVAR ALTERACOES` para dentro do fluxo da pagina, sem `fixed`, para nao cobrir filtros/campos.
- Substituir catalogo estatico duplicado do frontend por endpoint backend ou por um catalogo gerado. Hoje `providerCatalog.ts` e `src/core/provider_catalog.py` podem divergir.

5. Catalogo de modelos

- Atualizar Gemini: tratar `gemini-3-pro-preview` como obsoleto se o endpoint real agora for `gemini-3.1-pro-preview`.
- Permitir modelos customizados persistidos por provider, com adicionar/remover pela GUI.
- Manter modelos padrao e modelos do usuario separados para nao depender de atualizacao de codigo quando a Vertex/OpenRouter mudarem nomes.

## Nao bloqueadores

- GPU/VRAM no monitor geral. Pode entrar depois via `nvidia-smi`, `GPUtil` ou WMI, com fallback quando nao houver GPU NVIDIA.
- Instalador `.bat`/PowerShell guiado. E importante para usuario leigo, mas deve vir depois que o release base estiver limpo.
- Compilacao/empacotamento final. Por enquanto, manter como codigo executavel e documentado e suficiente.

## Ordem recomendada

1. Fazer higiene Git e proteger segredos.
2. Corrigir backend do chat Tauri: canal, anexos, imagem/edicao, task_type e salvamento seguro.
3. Corrigir telas Tauri pequenas: memoria, botao salvar, catalogo customizado.
4. Extrair popup de `pc_control.py` e remover GUI antiga. Concluido na fase 4.
5. Rodar validacao: `python -m compileall main.py src`, build do `control_panel`, testes selecionados e teste manual da GUI.
6. Atualizar README/docs para instalacao publica.

## Validacao rodada em 2026-04-29

- `python -m compileall main.py src`: passou.
- `npm run build` em `control_panel`: passou.
- `python -m pytest tests/test_lira_tags.py tests/test_media_jobs.py tests/test_pc_control.py tests/test_smoke.py -q`: passou com 35 testes.

## Progresso da fase 2 em 2026-04-29

- `/ws/chat` foi reconstruido para usar provider, modelo e historico enviados pela GUI Tauri.
- O chat visual deixou de depender do historico cronologico do terminal para montar o contexto imediato.
- O backend agora remove prefixo `data:image/...;base64,` dos anexos antes de enviar ao provider de LLM.
- Imagens anexadas tambem sao salvas temporariamente em `temp/gui_chat_uploads/` para permitir edicao via `<editar_imagem>`.
- `editar_imagem` e `editar_imagem_personagem` passaram a ser executadas pelo backend do chat.
- O streaming da GUI passou a esconder tags XML silenciosas preservando Markdown, sem fatiar a resposta por frases.
- Cancelamento do chat agora ignora acoes XML tardias e nao salva a resposta cancelada.
- Pendencia tecnica: remover a implementacao legacy `_websocket_chat_legacy` quando a fase de limpeza final remover codigo morto.

## Progresso da fase 3 em 2026-04-29

- `TabMemoria.tsx` ganhou criacao e edicao de fatos do Knowledge Graph.
- `TabMemoria.tsx` ganhou criacao, edicao, exclusao e `ver mais/ver menos` para memorias RAG longas.
- O backend ganhou endpoints para criar/atualizar memoria RAG e criar fatos no grafo.
- O backend ganhou `/api/catalog` para a GUI consumir provedores, vozes, modelos base e modelos customizados.
- A GUI agora permite adicionar/remover modelo LLM customizado por provider sem editar codigo.
- `TabLLM.tsx` passou a carregar catalogo do backend e deixou o botao `SALVAR ALTERACOES` no fluxo da pagina, sem overlay fixo.
- Validacao da fase 3: `python -m compileall main.py src`, `npm run build` em `control_panel` e `python -m pytest tests/test_lira_tags.py tests/test_media_jobs.py tests/test_pc_control.py tests/test_smoke.py -q` passaram.
- Pendencia tecnica: os retornos da API de memoria/catalogo ainda usam payload `{status: "error"}` com HTTP 200 em alguns casos; antes do release final, vale padronizar status HTTP e mensagens de erro.

## Progresso da fase 4 em 2026-04-29

- O popup de confirmacao de acoes de PC foi movido para `src/modules/tools/pc_action_popup.py`.
- `src/modules/tools/pc_control.py` deixou de importar `src.gui.widgets.pc_action_popup`.
- Os arquivos rastreados de `src/gui/` foram removidos do codigo publico.
- `requirements.txt` deixou de depender de `customtkinter`, `tkinterdnd2` e `pywinstyles`.
- README, INSTALL e TROUBLESHOOTING foram atualizados para o fluxo atual: `python main.py` inicia runtime, API e GUI Tauri.
- Validacao da fase 4: `python -m compileall main.py src`, `npm run build` em `control_panel` e `python -m pytest tests/test_lira_tags.py tests/test_media_jobs.py tests/test_pc_control.py tests/test_smoke.py -q` passaram.

## Progresso da fase 5 em 2026-04-29

- `data/characters/` foi limpo: os assets locais de personagem/Live2D foram removidos do workspace.
- `.gitignore` agora ignora `data/characters/**`, mantendo apenas `data/characters/.gitkeep`.
- `src/config/persona.txt`, `data/emotion_state.json`, `test_image_b64.py`, `test_part.py` e `test_upload.py` foram removidos do indice do Git sem apagar os arquivos locais.
- `src/config/persona.example.txt` foi criado como persona publica padrao.
- `src/core/prompt_builder.py` passou a usar `persona.example.txt` como fallback quando `persona.txt` local ainda nao existir.
- README e INSTALL foram ajustados para documentar o fluxo Tauri/React e a copia opcional da persona local.
- O Control Center Tauri deixou de usar o nome/template `control_panel` nos metadados publicos.
- Assets padrao Vite/Tauri nao usados foram removidos do frontend.
- Validacao da fase 5: `python -m compileall main.py src`, `npm run build` em `control_panel` e `python -m pytest tests/test_lira_tags.py tests/test_media_jobs.py tests/test_pc_control.py tests/test_smoke.py -q` passaram.
