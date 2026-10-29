# Providers

## Minimo publico

Para rodar a Lira no modo minimo, use apenas:

```env
GROQ_API_KEY=sua_chave
```

Isso cobre:

- LLM via Groq.
- STT via Groq Whisper.
- TTS via Edge sem chave.

## LLM

| Provider | Variavel | Observacao |
| --- | --- | --- |
| Groq | `GROQ_API_KEY` | Obrigatorio no setup publico. Tambem usado no STT. |
| Google | `GEMINI_API_KEY` ou credencial Google | Opcional para Gemini e recursos de midia. |
| OpenRouter | `OPENROUTER_API_KEY` | Opcional para gateway de modelos. |
| DemonRoute | `DEMONROUTE_API_KEY` | Opcional. Gateway OpenAI-compatible com modelos de roleplay. |
| OpenAI | `OPENAI_API_KEY` | Opcional para modelos OpenAI e TTS OpenAI. |
| Cerebras | `CEREBRAS_API_KEY` | Opcional. |

## TTS

| Provider | Chave | Default publico |
| --- | --- | --- |
| Edge | nenhuma | Sim |
| Google | credenciais Google locais | Nao |
| Azure | `AZURE_SPEECH_KEY`, `AZURE_REGION` | Nao |
| OpenAI | `OPENAI_API_KEY` | Nao |
| ElevenLabs | `ELEVENLABS_API_KEY` | Nao |

## ElevenLabs

Na GUI, configure manualmente:

- `voice_id`
- `model_id`
- `rate`
- `stability`
- `similarity_boost`
- `style`
- `speaker_boost`

## Google

Use `GEMINI_API_KEY` para Gemini API. Recursos Google Cloud opcionais devem usar credenciais privadas configuradas fora do repositorio.

## OpenRouter

Use sua chave do OpenRouter no `.env`. Se receber `401 User not found`, confira se a linha do `.env` nao ficou colada com outra variavel.

## DemonRoute

Gateway OpenAI-compatible com modelos open-weight, incluindo fine-tunes de roleplay.

```env
DEMONROUTE_API_KEY=sua_chave
```

Depois defina `LLM_PROVIDER=demonroute` (ou `CHAT.LLM_PROVIDER`) no `src/config/config.json`.
Rotacao de keys extras funciona com `DEMONROUTE_API_KEY_1..N`.

- Modelo padrao: `TheDrummer/Cydonia-24B-v4.1` (131K contexto).
- Fallback padrao: `NousResearch/Hermes-3-Llama-3.1-8B` e `mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated` (lane free, exige deposito confirmado no gateway).
- Timeouts do provider: 90s de cliente, 60s por requisicao e por stream. Os limites globais continuam valendo (`CHAT_SYNTHESIS_TIMEOUT=45`, `WHATSAPP_LLM_TIMEOUT=90`); aumente-os junto se precisar de respostas longas.
- Visao nao vem configurada: defina `LLM_PROVIDERS.demonroute.modelo_vision` com um modelo de visao do catalogo do gateway.
- Modelos "uncensored" nao tem as travas dos provedores grandes. Revise o que a Lira pode responder em canais publicos (Discord, WhatsApp, chat da live).

