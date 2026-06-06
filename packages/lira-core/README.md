# lira-core

Biblioteca compartilhada do monorepo LiraVT.

## Conteúdo (Sprint 1)

- `config` — carregamento de `src/config/config.json` e variáveis de ambiente
- `memory` — SQLite, RAG (Chroma), knowledge graph
- `providers` — LLM providers e selector
- `brain` — `BaseLLM`
- `core` — catálogo de modelos, capabilities, request profiles
- `utils` — tags XML (`lira_tags`), UI mínima de terminal

## Instalação (desenvolvimento)

Na raiz do repositório:

```bash
pip install -e packages/lira-core
```

## Variável de ambiente

- `LIRA_PROJECT_ROOT` — caminho absoluto da raiz do monorepo (opcional; auto-detecta `main.py` / `src/config/config.example.json`)