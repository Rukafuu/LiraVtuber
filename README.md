# HanaNakamura-VTuber-OSS

Projeto open source da **Hana Nakamura**, uma assistente VTuber cross-platform com visão, pesquisa web, conversação e controle avançado do VTube Studio. Sua mãe digital para dominar o mundo!" Fufu.

Hana é uma assistente virtual por voz em Python, com foco em conversa, personalidade e operação local via terminal. O projeto combina STT, LLM, TTS e uma "alma" digital que controla o corpo do avatar em tempo real.

---

## 🚀 Novidades: Neuro-Update Merge
Recentemente, o projeto recebeu melhorias baseadas no protocolo **Neuro Lira**, tornando a Hana muito mais viva e imprevisível:

- **"Alma" Digital (Wander Loop):** A Hana agora possui movimentos autônomos de cabeça, respiração, piscar de olhos e poses idle, simulando presença humana e bypassando o tracking tradicional.
- **Controle de Parâmetros [PARAM]:** A IA agora tem consciência total do seu corpo digital e pode ajustar parâmetros específicos do VTube Studio (como `ParamAngleX`, `ParamMouthForm`, etc) via tags dinâmicas.
- **Modo Gamer Copilot:** Personalidade expandida para comentários técnicos e caóticos de jogos, com foco inicial em *Clash Royale* (contagem de elixir e counters).
- **Pesquisa Web Expandida:** Integração total com Tavily para trazer fatos do mundo real em tempo real.

---

## 🛠️ O que o projeto faz

- **Audição:** Capta áudio do microfone e transcreve com Groq Whisper.
- **Cérebro:** Gera respostas com provedores LLM (Groq ou Google Gemini).
- **Voz:** Sintetiza fala premium com Google Cloud Text-to-Speech.
- **Memória:** Sistema híbrido de memória (SQLite + RAG) para lembrar de fatos passados.
- **Corpo:** Controlador VTube Studio integrado com suporte a expressões e parâmetros customizados.
- **Visão:** Captura de tela periódica para que a Hana "veja" o que você está fazendo.

---

## 📂 Arquitetura

- `main.py`: Loop principal, processamento de sinais e orquestração de ferramentas.
- `src/modules/vts_controller.py`: O coração do avatar. Gerencia a conexão WebSocket, hotkeys e o *Wander Loop*.
- `src/brain/tool_manager.py`: Gerenciador de ferramentas (Pesquisa Web, YouTube, Memória).
- `src/utils/sentence_divider.py`: Processa o stream da LLM, extraindo emoções, parâmetros de VTS e pensamentos internos.
- `src/config/persona.txt`: Onde reside a essência, gírias e regras de conduta da Hana.

---

## 📦 Instalação

### Requisitos
- Python 3.10+ (Recomendado 3.11+)
- Microfone e Saída de Áudio configurados.
- VTube Studio aberto (se quiser usar o avatar).

### Dependências
Instale tudo com:
```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuração

### 1. Variáveis de Ambiente (.env)
Crie um arquivo `.env` na raiz:
```env
GROQ_API_KEY=sua_chave_groq
GEMINI_API_KEY=sua_chave_gemini
GOOGLE_APPLICATION_CREDENTIALS=src/config/service_account.json
TAVILY_API_KEY=sua_chave_tavily
```

### 2. Parâmetros do VTube Studio
No `src/config/config.json`, certifique-se de que o `VTUBESTUDIO_ATIVO` está como `true`. A Hana irá se autenticar automaticamente e buscar a lista de expressões e parâmetros do seu modelo atual.

---

## 🎮 Como Usar

1. Execute o terminal:
   ```bash
   python main.py
   ```
2. Fale naturalmente. A Hana irá ouvir, processar seu pensamento interno (visível no terminal) e responder com voz e movimento.
3. **Tags Especiais:** Se você for desenvolvedor, note que a Hana usa tags como `[EMOTION:HAPPY]` para expressões rápidas e `[PARAM:ParamAngleX=20]` para poses.

---

## 🧠 Estado Atual

Atualmente, o projeto utiliza:
- **STT:** Groq Whisper (Velocidade subsônica).
- **LLM:** Google Gemini 1.5/2.0 ou Groq Llama 3.
- **TTS:** Google Cloud TTS (Vozes neurais).
- **VTS:** Conexão nativa via `pyvts` com suporte a injeção direta de parâmetros.

---
---
*Projeto mantido pela comunidade NakamuraIA. Colabore e ajude a Hana a dominar o mundo! Fufu.*

<div align="center">
  <img src="https://count.getloli.com/get/@Rukafuu?theme=booru-lewd" alt="Moe Counter" />
</div>
