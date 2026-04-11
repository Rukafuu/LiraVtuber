# Configuracao da Hana

Os defaults publicos ficam em `src/config/config.example.json`. O arquivo real do usuario e `src/config/config.json`.

## Ordem de carregamento

1. `src/config/config.example.json`
2. `src/config/config.json`, se existir
3. variaveis do `.env`

Isso permite manter configs locais fora do Git.

## LLM

O setup publico usa:

```json
"LLM_PROVIDER": "groq"
```

Providers selecionaveis:

- `groq`
- `google_cloud`
- `openrouter`
- `openai`
- `cerebras`

## STT

O STT usa Groq Whisper:

```json
"STT_MODEL": "whisper-large-v3",
"STT_LANGUAGE": "pt"
```

Variavel obrigatoria:

```env
GROQ_API_KEY=sua_chave
```

## TTS

Default publico:

```json
"TTS_PROVIDER": "edge"
```

TTS disponiveis na GUI:

- `edge`: sem chave.
- `google`: exige credenciais Google configuradas localmente.
- `azure`: exige `AZURE_SPEECH_KEY` e `AZURE_REGION`.
- `openai`: exige `OPENAI_API_KEY`.
- `elevenlabs`: exige `ELEVENLABS_API_KEY` e `voice_id`.

## GUI

Config principal:

```json
"GUI": {
  "ptt_key": "F2",
  "ptt_enabled": false,
  "stop_hotkey_enabled": true,
  "stop_hotkey": "F8"
}
```

## Controle do PC

A tool `<acao_pc>` vem ligada com guardrails. Acoes perigosas continuam exigindo confirmacao e geram log de auditoria.

Exemplo:

```xml
<acao_pc>{"action":"open_url","url":"https://github.com"}</acao_pc>
```

## Midia

Ativo nesta release:

- gerar imagem;
- editar imagem;
- gerar musica;
- anexar/analisar video no chat.

Removido nesta release:

- gerar video por Veo;
- tag `<gerar_video>`.

## Arquivos locais que nao devem ir para Git

- `.env`
- `src/config/config.json`
- credenciais JSON privadas
- bancos em `data/`
- logs
- arquivos de audio, imagem, musica e cache gerados localmente

