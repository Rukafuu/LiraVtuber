# HanaNakamura-VTuber-OSS

Projeto open source da **Hana Nakamura**, uma assistente VTuber cross-platform com visão, pesquisa web, conversação e controle do VTube Studio. Sua mãe digital para dominar o mundo!" Fufu.

Hana é uma assistente virtual por voz em Python, com foco em conversa, personalidade e operação local via terminal. O projeto combina STT, LLM, TTS e memória persistente em uma arquitetura modular.

## O que o projeto faz

- Capta áudio do microfone e transcreve com Groq Whisper
- Gera respostas com provedor LLM configurável
- Sintetiza voz com Google Cloud Text-to-Speech
- Salva histórico da conversa em SQLite
- Exibe status em tempo real no terminal
- Pode pesquisar na web, mas apenas quando o usuário pedir explicitamente ou autorizar

## Arquitetura

- `main.py`: loop principal de conversa, controle de ferramentas e consentimento para pesquisa
- `src/modules/voice/stt_whisper.py`: captura de áudio e transcrição
- `src/providers/provider_selector.py`: seleção do provedor LLM
- `src/providers/groq_provider.py`: integração com Groq
- `src/providers/google_provider.py`: integração com Google Gemini
- `src/modules/voice/tts_selector.py`: seleção de TTS
- `src/modules/voice/tts_google.py`: síntese de voz com Google Cloud TTS
- `src/brain/tool_manager.py`: ferramentas auxiliares, incluindo pesquisa web
- `src/memory/sqlite.py`: persistência de mensagens

## Requisitos

- Python 3.10+
- Microfone configurado no sistema
- Dispositivo de áudio para reprodução local de voz
- Credenciais válidas para os serviços que você quiser usar

## Dependências principais

Instale tudo com:

```bash
pip install -r requirements.txt
```

## Configuração

### 1. Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto com as chaves que pretende usar.

Exemplo:

```env
GROQ_API_KEY=sua_chave_groq
GEMINI_API_KEY=sua_chave_gemini
GOOGLE_APPLICATION_CREDENTIALS=src/config/service_account.json
TAVILY_API_KEY=sua_chave_tavily
```

Observações:

- `GROQ_API_KEY` é usada no STT e no provedor Groq
- `GEMINI_API_KEY` é usada se você escolher `google_cloud` como LLM
- `GOOGLE_APPLICATION_CREDENTIALS` aponta para o JSON de service account do Google Cloud TTS
- `TAVILY_API_KEY` é usada para pesquisa na web

### 2. Arquivo de configuração

Edite `src/config/config.json`.

Campos mais importantes:

- `LLM_PROVIDER`: `groq` ou `google_cloud`
- `TTS_PROVIDER`: atualmente o fluxo está preparado para `google`
- `GOOGLE_TTS_VOICE`: voz do Google TTS
- `GOOGLE_TTS_LANG`: idioma da voz
- `GOOGLE_TTS_RATE`: velocidade da fala
- `GOOGLE_TTS_PITCH`: tom da fala

## Como executar

```bash
python main.py
```

Fluxo esperado:

- A Hana inicializa no terminal
- Ela entra em modo de escuta
- Você fala pelo microfone
- A resposta aparece no console e é reproduzida por voz

Para encerrar:

- diga `Desligar sistema`
- ou use `Ctrl+C`

## Pesquisa na web

O projeto possui uma ferramenta de pesquisa online via Tavily, mas ela foi restringida para evitar pesquisas automáticas indevidas.

Comportamento atual:

- Hana só deve pesquisar quando você pedir explicitamente
- Se o modelo quiser pesquisar por conta própria, ela deve pedir sua permissão antes
- Se você responder algo como `pode pesquisar`, a busca é autorizada
- Se você responder `não` ou equivalente, ela segue sem pesquisa

## Armazenamento

O histórico da conversa é salvo em:

- `data/hana_memory.db`

O último áudio sintetizado é salvo em:

- `data/last_response.mp3`

## Observações importantes

- O terminal no Windows foi ajustado para UTF-8 para evitar erro de encoding no banner
- Se o mixer de áudio do `pygame` não iniciar, o TTS continua podendo sintetizar, mas a reprodução local pode falhar
- O projeto ainda depende de serviços externos; sem credenciais válidas algumas partes não funcionarão
- Python 3.11+ é recomendado para maior longevidade das dependências do Google

## Estado atual

Hoje o projeto está alinhado com este comportamento:

- STT: Groq Whisper
- LLM: Groq ou Google Gemini, conforme `config.json`
- TTS: Google Cloud TTS
- Memória: SQLite
- Pesquisa web: Tavily, com consentimento do usuário
