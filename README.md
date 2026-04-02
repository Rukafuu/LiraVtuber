<div align="center">
  <img src="data/image/hana.png" alt="Hana Nakamura" width="auto" style="max-width: 100%; border-radius: 10px;" />
</div>

# HanaNakamura-VTuber-OSS

Projeto open source da **Hana Nakamura**, uma assistente VTuber com dois produtos conectados entre si:

- **Terminal runtime**: o cérebro principal, com STT, TTS, memória, visão opcional, ferramentas e automação de resposta por voz.
- **Hana Control Center**: a GUI em CustomTkinter, usada como painel de controle e como chat visual com anexos, renderização inline e configuração dos módulos.

Os dois lados **não são o mesmo produto**, mas compartilham os mesmos serviços centrais quando faz sentido:

- memória híbrida;
- configuração;
- providers LLM;
- geração de imagem;
- integração com VTube Studio;
- leitura de arquivos.

O foco atual do projeto é **Windows desktop**.

---

## Visão geral

A Hana foi pensada para ser mais do que um chatbot de texto. O projeto hoje combina:

- **voz para texto** com captura local;
- **texto para voz** com Google Cloud TTS;
- **múltiplos providers LLM**;
- **chat visual com anexos**;
- **memória curta + semântica + grafo de conhecimento**;
- **geração e edição de imagem** via tags XML;
- **leitura de PDF, DOCX, texto, áudio, vídeo e imagens**;
- **integração com VTube Studio**;
- **painel gráfico para operar o sistema sem depender só do terminal**.

---

## O que o projeto entrega hoje

### 1. Terminal runtime

O arquivo [main.py](main.py) é o loop principal do modo terminal.

Ele faz:

- captura de fala do usuário;
- montagem do prompt com persona, memória e contexto;
- streaming da resposta do LLM;
- filtragem de tags XML silenciosas;
- TTS em lote ao final da resposta;
- pós-processamento de ações como:
  - `<salvar_memoria>`
  - `<gerar_imagem>`
  - `<editar_imagem>`
  - `<analisar_youtube>`
  - `<ferramenta_web>`

### 2. Hana Control Center

A GUI principal fica em [src/gui/hana_gui.py](src/gui/hana_gui.py).

Ela expõe abas para:

- monitor geral;
- cérebro / providers;
- memória;
- mente / emoções;
- VTube Studio;
- chat do controle;
- persona;
- prompts;
- conexões;
- personalização;
- logs.

### 3. Chat da GUI

A aba do chat fica em [src/gui/frames/tab_chat.py](src/gui/frames/tab_chat.py).

Hoje ela já suporta:

- envio manual de mensagem;
- `Shift+Enter` para quebrar linha;
- drag and drop de arquivos;
- anexos inline no histórico;
- preview de imagem gerada no próprio chat;
- cards de áudio com botão de tocar;
- cards de arquivos com botão de abrir;
- prompt específico de GUI, separado do terminal;
- auto-roteamento de mídia pesada para modelo compatível;
- renderização melhor de markdown;
- botão `Parar` para interromper TTS e cancelar a geração ativa da GUI.

### 4. Memória híbrida

O gerenciador de memória está em [src/memory/memory_manager.py](src/memory/memory_manager.py).

Ele usa três camadas:

- **SQLite** para histórico cronológico;
- **RAG vetorial** para recuperação semântica;
- **Knowledge Graph** para fatos permanentes.

Na prática isso permite:

- recuperar conversas antigas por similaridade;
- guardar fatos estruturados;
- responder perguntas em primeira pessoa como “qual é meu aniversário?” com resolução melhor da entidade do usuário;
- cruzar memória curta com memória longa.

### 5. Providers LLM

O seletor principal está em [src/providers/provider_selector.py](src/providers/provider_selector.py).

Providers atualmente suportados:

- `google_cloud`
- `groq`
- `openrouter`
- `cerebras`

#### Google dual-mode

O provider do Google em [src/providers/google_provider.py](src/providers/google_provider.py) agora trabalha em arquitetura **dual-mode**:

- `gemini_api`
- `vertex_ai`
- `auto`

Ele já usa ou prepara suporte para:

- `max_output_tokens`;
- `thinking_config`;
- `response_mime_type`;
- `response_schema`;
- `count_tokens`;
- upload nativo de arquivos quando o backend/modelo suportam;
- roteamento de tarefa por contexto da requisição.

Observação importante:

- o projeto **não depende obrigatoriamente** de Vertex AI para funcionar;
- o backend `vertex_ai` só entra quando as credenciais e o projeto estão configurados.

### 6. Geração de imagem

A Hana gera e edita imagem via XML no fluxo do runtime e da GUI.

Exemplos:

```xml
<gerar_imagem>prompt em inglês para criar a imagem</gerar_imagem>
<editar_imagem>prompt em inglês para editar a última imagem</editar_imagem>
```

As tags são silenciosas:

- no terminal, o conteúdo interno não deve ser falado no TTS;
- na GUI, a imagem pode aparecer inline na própria conversa.

### 7. VTube Studio

O runtime da integração está em [src/modules/vts_controller.py](src/modules/vts_controller.py).

Hoje a integração trabalha com:

- conexão por `host` e `port`;
- autenticação por token;
- heartbeat;
- reconexão com backoff;
- estado persistido em `data/vts_state.json`;
- leitura de hotkeys, expressões e parâmetros;
- tentativa de lipsync usando o parâmetro de boca detectado;
- animação idle + animação durante fala;
- exibição do estado real na aba VTube da GUI.

---

## Arquitetura resumida

### Fluxo do terminal

1. usuário fala;
2. STT transcreve;
3. memória monta contexto;
4. provider gera resposta em stream;
5. `SentenceDivider` separa frases visíveis e bloqueia XML silencioso;
6. emoção e VTS são acionados;
7. TTS fala só o texto limpo;
8. XML é processado no final como ação.

### Fluxo do chat da GUI

1. usuário digita ou arrasta arquivos;
2. a GUI classifica a tarefa;
3. decide se mantém o modelo atual ou se auto-roteia mídia pesada;
4. monta prompt específico de GUI;
5. envia request com perfil explícito de canal;
6. renderiza resposta com markdown e anexos;
7. executa ações XML;
8. salva interação na memória compartilhada.

### Perfis de canal

Os perfis de canal estão em [src/core/request_profiles.py](src/core/request_profiles.py).

Hoje o projeto diferencia explicitamente:

- `terminal_voice`
- `control_center_chat`

Isso evita que a GUI herde comportamento de terminal e vice-versa.

---

## Requisitos

### Sistema

- Windows 10 ou 11
- Python 3.10 recomendado
- Git
- microfone, se quiser usar STT
- VTube Studio, se quiser avatar ao vivo

### Dependências principais

Instaladas por:

```bash
pip install -r requirements.txt
```

O `requirements.txt` já inclui os blocos principais do projeto, como:

- `google-genai`
- `groq`
- `openai`
- `customtkinter`
- `tkinterdnd2`
- `pygame`
- `chromadb`
- `sentence-transformers`
- `networkx`

### Dependências opcionais que podem ser necessárias

Alguns recursos dependem de libs que hoje podem precisar de instalação manual, dependendo do seu uso:

```bash
pip install pyvts pypdf PyPDF2 youtube-transcript-api
```

Esses pacotes são úteis para:

- `pyvts`: integração com VTube Studio;
- `pypdf` / `PyPDF2`: leitura de PDF;
- `youtube-transcript-api`: análise de vídeos do YouTube.

---

## Instalação

### 1. Clone o projeto

```bash
git clone https://github.com/NakamuraIA/HanaNakamura-VTuber-OSS.git
cd HanaNakamura-VTuber-OSS
```

### 2. Crie um ambiente virtual

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

Se você for usar PDF, VTS ou YouTube transcript, instale também:

```bash
pip install pyvts pypdf PyPDF2 youtube-transcript-api
```

### 4. Configure o `.env`

Existe um arquivo [.env.example](.env.example). Copie para `.env`:

```bash
copy .env.example .env
```

Preencha as variáveis de ambiente que você realmente vai usar.

#### Mínimo para começar com Gemini API

```env
GEMINI_API_KEY=sua_chave
GOOGLE_APPLICATION_CREDENTIALS=src/config/service_account.json
```

#### Outras variáveis suportadas

```env
GROQ_API_KEY=sua_chave
OPENROUTER_API_KEY=sua_chave
CEREBRAS_API_KEY=sua_chave
TAVILY_API_KEY=sua_chave
GOOGLE_APPLICATION_CREDENTIALS=caminho\\para\\service_account.json
GOOGLE_CLOUD_PROJECT=seu_projeto
GOOGLE_CLOUD_LOCATION=global
```

### 5. Configure credenciais do Google TTS

O TTS do projeto usa `google-cloud-texttospeech`.

Você precisa de um arquivo JSON de service account e apontar para ele em:

```env
GOOGLE_APPLICATION_CREDENTIALS=src/config/service_account.json
```

Se quiser usar o backend `vertex_ai`, o mesmo caminho de credenciais pode ser reutilizado junto com:

```env
GOOGLE_CLOUD_PROJECT=seu_projeto
GOOGLE_CLOUD_LOCATION=global
```

---

## Como executar

### Terminal runtime

```bash
python main.py
```

Esse modo é o mais próximo do runtime “ao vivo” da Hana:

- escuta no microfone;
- responde em texto e voz;
- usa memória compartilhada;
- dispara VTS e ferramentas;
- processa tags XML no final.

### Hana Control Center

```bash
python -m src.gui.hana_gui
```

Esse modo abre o painel gráfico.

O chat da GUI hoje é o melhor lugar para:

- mandar mensagens grandes;
- arrastar arquivos;
- anexar áudio, PDF, DOCX, imagens e outros documentos;
- ver geração de imagem inline;
- acompanhar provider/model/backend usado em cada resposta.

---

## Configuração principal

O arquivo principal é [src/config/config.json](src/config/config.json).

### Blocos mais importantes

#### Provider principal do terminal

```json
"LLM_PROVIDER": "google_cloud"
```

#### Providers disponíveis

```json
"LLM_PROVIDERS": {
  "groq": { ... },
  "cerebras": { ... },
  "openrouter": { ... },
  "google_cloud": {
    "backend": "auto",
    "modelo": "...",
    "modelo_vision": "...",
    "modelo_chat": "..."
  }
}
```

#### Configuração do chat da GUI

```json
"CHAT": {
  "LLM_PROVIDER": "google_cloud",
  "LLM_MODEL": "gemini-3.1-pro-preview",
  "LLM_TEMPERATURE": 0.85,
  "usa_mesmo_prompt_terminal": false,
  "response_mode": "adaptive",
  "auto_route_media": true,
  "media_model": "gemini-2.5-flash",
  "max_output_tokens_normal": 2048,
  "max_output_tokens_media": 8192,
  "markdown_enabled": true
}
```

#### TTS

```json
"TTS_PROVIDER": "google",
"GOOGLE_TTS_VOICE": "pt-BR-Neural2-C",
"GOOGLE_TTS_LANG": "pt-BR"
```

#### VTube Studio

```json
"VTUBE_STUDIO": {
  "host": "localhost",
  "port": 8001,
  "emotion_map": {
    "HAPPY": "happy"
  }
}
```

#### Inbox / mídia

```json
"HANA_INBOX_ROOT": "",
"HANA_INBOX_MODEL": "gemini-2.5-flash"
```

Se `HANA_INBOX_ROOT` estiver vazio, a pasta padrão é:

```text
%USERPROFILE%\Desktop\hana_inbox
```

---

## Como usar a Hana Inbox

O resolvedor fica em [src/modules/tools/inbox_manager.py](src/modules/tools/inbox_manager.py).

Estrutura esperada:

```text
hana_inbox/
  imagem/
  pdf/
  docs/
  code/
  audio/
  video/
```

A Hana consegue:

- procurar o arquivo mais recente por categoria;
- ler `.txt`, `.md`, `.json`, `.xml`, `.yaml`, `.csv`, `.log`, `.docx`;
- extrair texto de PDF;
- rastrear “arquivo ativo” por categoria.

Na GUI, você também pode **arrastar o arquivo direto no chat** sem depender da inbox.

---

## Como configurar o VTube Studio

### No VTube Studio

1. abra o app;
2. ative o **Plugin API**;
3. confirme que a porta está em `8001` ou ajuste o `config.json`;
4. permita a autenticação quando a Hana pedir acesso.

### No projeto

Ative:

```json
"VTUBESTUDIO_ATIVO": true
```

E configure:

```json
"VTUBE_STUDIO": {
  "host": "localhost",
  "port": 8001,
  "emotion_map": {
    "HAPPY": "happy",
    "SAD": "sad",
    "ANGRY": "angry"
  }
}
```

### Estado em runtime

O estado mais recente fica em:

- [data/vts_state.json](data/vts_state.json)

Ele registra:

- `status`
- `connected`
- `authenticated`
- `last_heartbeat_at`
- `reconnect_attempts`
- `mouth_parameter`
- `tracking_mode`
- `last_error`

---

## Providers e roteamento

### Terminal

O terminal usa o provider configurado em `LLM_PROVIDER`.

### GUI

A GUI pode usar um provider diferente do terminal.

Além disso, quando `CHAT.auto_route_media = true`, a GUI pode:

- manter o modelo atual em conversa normal;
- trocar automaticamente para o modelo de mídia quando detectar áudio, vídeo ou PDF pesado;
- exibir na própria resposta qual provider/model/backend foi usado.

### Google / Vertex

O provider `google_cloud` pode operar assim:

- `gemini_api`: usa `GEMINI_API_KEY`;
- `vertex_ai`: usa `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT` e `GOOGLE_CLOUD_LOCATION`;
- `auto`: tenta `vertex_ai` quando o ambiente está pronto, e cai para `gemini_api` quando não está.

---

## Estrutura de diretórios

Resumo das pastas mais importantes:

```text
src/
  brain/          -> base do pipeline LLM e tools
  config/         -> persona, prompt, config principal
  core/           -> perfis de request e capabilities
  gui/            -> painel gráfico e abas
  memory/         -> SQLite, RAG, grafo
  modules/
    tools/        -> inbox, tools auxiliares
    vision/       -> visão e geração de imagem
    voice/        -> STT / TTS
  providers/      -> adapters dos LLMs
  utils/          -> limpeza de texto, console, streaming

data/
  image/          -> assets visuais
  memory/         -> base do Chroma / vetores
  vts_state.json  -> estado do VTS
```

---

## Situação atual do projeto

Pontos fortes do estado atual:

- GUI e terminal agora têm canais diferentes;
- chat da GUI aceita anexos e suporta respostas mais estruturadas;
- provider Google já tem base para Gemini API e Vertex AI;
- filtro de stream evita vazamento de XML silencioso;
- VTS tem heartbeat e reconexão em vez de status fake simples;
- memória híbrida já está integrada ao fluxo principal.

Limitações e observações honestas:

- o projeto ainda é mais estável em **Windows** do que em outras plataformas;
- recursos como VTube Studio dependem do modelo Live2D expor parâmetros compatíveis;
- `vertex_ai` precisa de credenciais reais para funcionar;
- alguns recursos opcionais exigem dependências extras ainda não listadas no `requirements.txt`;
- a qualidade de resumo de mídia depende bastante do provider/modelo escolhido e do tipo de arquivo.

---

## Comandos úteis

### Rodar terminal

```bash
python main.py
```

### Rodar GUI

```bash
python -m src.gui.hana_gui
```

### Reinstalar dependências principais

```bash
pip install -r requirements.txt
```

### Instalar dependências opcionais

```bash
pip install pyvts pypdf PyPDF2 youtube-transcript-api
```

### Compilar o projeto para smoke check

```bash
python -m compileall main.py src
```

---

## Contribuição

Se for contribuir, o mais importante é manter coerência entre:

- runtime do terminal;
- chat da GUI;
- memória compartilhada;
- providers;
- filtros de XML silencioso;
- estado do VTS.

Se você mudar comportamento de prompt, provider ou canal, ajuste também a documentação e o `config.json`.

---

## Licença

Consulte a licença do repositório e os termos dos providers externos que você decidir usar.

<div align="center">
  <img src="https://count.getloli.com/get/@Rukafuu?theme=booru-lewd" alt="Moe Counter" />
</div>