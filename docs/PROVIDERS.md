# Providers

## Minimo publico

Para rodar a Hana no modo minimo, use apenas:

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

