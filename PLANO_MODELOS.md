# Plano de Atualizacao de Modelos e Dropdowns

Data de referencia: 30 de marco de 2026

## Objetivo

Atualizar os catalogos de modelos exibidos nas telas:

- `src/gui/frames/tab_llm.py`
- `src/gui/frames/tab_chat.py`

Sem alterar ainda a arquitetura principal da Hana.

## Contexto da Hana

A Hana hoje opera em dois modos principais:

### 1. Modo Terminal

Fluxo principal em `main.py`.

Responsabilidades:

- Receber entrada via STT
- Montar contexto com persona, prompt, memoria e visao opcional
- Enviar tudo para a LLM
- Receber resposta com tags XML
- Executar acoes silenciosas a partir dessas tags

Esse modo e o nucleo operacional da Hana.

### 2. Modo GUI

Fluxo principal nas abas da interface, em especial:

- `src/gui/frames/tab_chat.py`
- `src/gui/frames/tab_llm.py`

Responsabilidades:

- Hot reload de configuracoes
- Painel de controle
- Troca de provider e modelo
- Envio de arquivos
- Consulta a memoria
- Conversa por chat visual
- Ativacao e desativacao de funcoes

Esse modo e o painel interativo e visual da Hana, separado do fluxo terminal.

## Diagnostico Atual

### tab_llm.py

Funcao afetada:

- `TabLLM._on_provedor_change(self, provedor)`

Problemas encontrados:

- Lista de modelos desatualizada em varios providers
- Alguns IDs aparentam estar antigos ou incompletos
- OpenRouter mistura familias que nao sao mais desejadas
- Modelos de visao e chat precisam de curadoria separada

### tab_chat.py

Funcao afetada:

- `TabChat._on_chat_prov_change(self, provedor)`

Problemas encontrados:

- Lista de modelos tambem esta desatualizada
- IDs antigos do Google/Vertex AI
- Lista do OpenRouter esta mais ampla do que o desejado
- O chat GUI precisa manter independencia do terminal, mas com catalogo consistente

## Diretriz de Curadoria

### OpenRouter

Manter apenas familias:

- GPT
- Gemini
- Grok
- Claude

Remover da dropdown:

- DeepSeek
- Meta/Llama
- outras familias fora desse escopo

### Vertex AI / Google Cloud

Priorizar a linha `Gemini 2.5` como base principal por estabilidade atual.

Modelos preview `Gemini 3` podem entrar, desde que os IDs finais sejam confirmados para o SDK e endpoint usados no projeto.

### Groq

Trocar IDs antigos/incompletos por nomes oficiais atuais.

### Cerebras

Limpar modelos que nao aparecem mais no catalogo oficial atual.

## Catalogo Proposto

## Google Cloud / Vertex AI

### Chat

- `gemini-2.5-pro`
- `gemini-2.5-flash`
- `gemini-2.5-flash-lite`
- `gemini-2.0-flash`
- `Outro...`

### Visao

- `gemini-2.5-flash`
- `gemini-2.5-pro`
- `gemini-2.5-flash-lite`
- `Outro...`

### Observacao

`Gemini 3 Flash Preview` e `Gemini 3 Pro Preview` ficaram mapeados como candidatos, mas devem entrar apenas depois da confirmacao final dos IDs aceitos pelo fluxo atual do projeto.

## Groq

### Chat

- `llama-3.1-8b-instant`
- `meta-llama/llama-4-scout-17b-16e-instruct`
- `moonshotai/kimi-k2-instruct-0905`
- `Outro...`

### Visao

- `meta-llama/llama-4-scout-17b-16e-instruct`
- `Outro...`

## Cerebras

### Chat

- `qwen-3-235b-a22b-instruct-2507`
- `llama3.1-8b`
- `gpt-oss-120b`
- `zai-glm-4.7`
- `Outro...`

### Visao

- sem suporte no provider atual

## OpenRouter

### Chat

- `openai/gpt-5.4`
- `openai/gpt-5.4-mini`
- `google/gemini-3.1-flash-lite-preview`
- `google/gemini-3.1-pro-preview`
- `google/gemini-2.5-pro`
- `google/gemini-2.5-flash`
- `google/gemini-2.5-flash-lite`
- `x-ai/grok-4.20-beta`
- `x-ai/grok-4.1-fast`
- `x-ai/grok-4`
- `anthropic/claude-opus-4.6`
- `anthropic/claude-sonnet-4.6`
- `anthropic/claude-haiku-4.5`
- `Outro...`

### Visao

Curadoria sugerida para a tela do terminal:

- `google/gemini-3.1-pro-preview`
- `google/gemini-2.5-flash`
- `google/gemini-2.5-pro`
- `x-ai/grok-4.1-fast`
- `Outro...`

## Plano de Execucao

### Etapa 1

Atualizar `src/gui/frames/tab_llm.py`:

- Revisar a lista `chat`
- Revisar a lista `visao`
- Garantir que o valor salvo no `CONFIG` continue funcionando

### Etapa 2

Atualizar `src/gui/frames/tab_chat.py`:

- Revisar a lista de modelos do chat
- Manter a independencia da GUI em relacao ao terminal
- Garantir consistencia de nomenclatura entre telas

### Etapa 3

Validar comportamento real:

- troca de provider
- troca de modelo
- persistencia no `config.json`
- inicializacao do provider correspondente

### Etapa 4

Revisar depois a camada funcional:

- Web Search no Google Provider
- alinhamento entre GUI e terminal
- execucao de tools/XML no chat visual, se desejado

## Fora do Escopo Desta Atualizacao

Ainda nao faz parte desta etapa:

- refatorar o pipeline XML do chat GUI
- unificar terminal e GUI em um unico motor
- implementar novas tools
- corrigir toda a arquitetura de Web Search

## Fontes Oficiais Consultadas

- Vertex AI models: `https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models`
- Vertex AI grounding / Google Search: `https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/grounding`
- Groq models: `https://console.groq.com/docs/models`
- Groq Llama 4 Scout: `https://console.groq.com/docs/model/llama-4-scout-17b-16e-instruct`
- Cerebras models overview: `https://inference-docs.cerebras.ai/models/overview`
- Cerebras Qwen 3 235B: `https://inference-docs.cerebras.ai/models/qwen-3-235b-2507`
- OpenRouter OpenAI: `https://openrouter.ai/openai/`
- OpenRouter Google: `https://openrouter.ai/google`
- OpenRouter xAI: `https://openrouter.ai/x-ai/`
- OpenRouter Anthropic: `https://openrouter.ai/anthropic`

