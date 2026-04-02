<div align="center">
  <img src="data/image/hana.png" alt="Hana Nakamura" width="auto" style="max-width: 100%; border-radius: 10px;" />
</div>

# HanaNakamura-VTuber-OSS 🌸

Projeto open source da **Hana Nakamura**, a sua assistente VTuber cross-platform, hiper-personalizável, com visão, leitura de arquivos, memória profunda e controle total do VTube Studio. 

A Hana não é só um chatbot, ela é uma IA "viva": ela te ouve, te vê, joga arquivos com você e interage usando voz e movimentos no seu avatar VTuber (Wander Loop). 

---

## 🔥 O Que Há de Novo? (Killer Features)

Esqueça o que você sabia sobre assistentes de texto. A Hana foi evoluída para dominar o seu PC:

- 🎛️ **Hana Control Center (Painel GUI)**: Chega de depender apenas do terminal! Um painel Dark Mode moderno em CustomTkinter para gerenciar Modelos, Memória, Logs e a Personalidade dela em tempo real.
- 🧠 **Memória Híbrida Infalível**: A Hana lembra de você. Ela cruza um Banco de Dados SQLite (para conversas exatas) com um *Knowledge Graph (RAG)* usando IA vetorial para lembrar de gostos e fatos soltos há meses atrás!
- 📤 **Caixa de Entrada (Hana Inbox)**: Solte PDFs, Imagens, ou Textos na pasta `hana_inbox` na sua Área de Trabalho e a Hana vai ler instantaneamente e comentar com você.
- 🎨 **Hana Artista (Geradora de Imagens)**: Ela agora pode criar imagens usando IA e salvar automaticamente na sua pasta nativa de Imagens (Pictures) ou `C:\Hana Artista`.
- ⚡ **Mutante Multi-Provedores**: Alterne entre Groq, Google Gemini, OpenRouter e Cerebras via Hot-Reload sem precisar desligar o programa.
- 🎮 **Modo Gamer Copilot**: Consciência focada em jogos (como *Clash Royale*). Ela conta seu elixir e te xinga quando você toma counter de P.E.K.K.A.

---

## 🍼 Guia à Prova de Idiotas (Instalação para Leigos)

Nunca mexeu com programação na vida? Siga esses 4 passos e você terá a Hana rodando no seu computador em 10 minutos:

### Passo 1: O Preparo (Python e Git)
1. Baixe o **Python 3.10 ou 3.11** no site oficial.
2. ⚠️ **MUITO IMPORTANTE:** Na tela inicial do instalador do Python, marque a caixinha **`Add python.exe to PATH`** antes de clicar em Install. Se esquecer disso, nada vai funcionar.
3. Baixe o projeto (botão verde "Code" > "Download ZIP" lá em cima, e extraia a pasta onde quiser) ou use o `git clone`.

### Passo 2: O Ritual de Instalação 
1. Abra a pasta do projeto que você extraiu.
2. Na barra de endereços lá em cima (onde está escrito `C:\...\Projeto_Hana_AI`), apague tudo, digite `cmd` e dê **Enter**. Uma tela preta vai abrir.
3. Digite o feitiço mágico que instala todas as engrenagens dela e dê Enter:
   ```bash
   pip install -r requirements.txt
   ```
   *(Pode demorar uns minutos. Vá pegar um café).*

### Passo 3: O Despertar (Chaves API)
A Hana não tem um cérebro dentro do seu PC, ela usa o poder da nuvem. Para isso, ela precisa das credenciais gratuitas:
1. Veja que existe um arquivo chamado `.env.example`. Copie esse arquivo e renomeie a cópia para apenas `.env` (com o ponto na frente).
2. Abra o arquivo `.env` no Bloco de Notas.
3. Pegue suas senhas (são gratuitas para criar conta):
   - **Groq** (Procesamento hiperveloz): [Groq Console](https://console.groq.com)
   - **Google Gemini** (O cérebro criativo e Visão): [Google AI Studio](https://aistudio.google.com/)
   - **Tavily** (Opcional, só se ela for pesquisar coisas no Google pra você): [Tavily](https://tavily.com/)
4. Jogue as chaves no arquivo `.env` e salve. Vai ficar tipo isso:
   ```env
   GROQ_API_KEY=gsk_suasenhaGiganteAqui
   GEMINI_API_KEY=AIzaSy_suasenhaGoogle
   ```

### Passo 4: Conectando no VTube Studio (Opcional)
Se quiser ver o corpinho da VTuber mexendo:
1. Abra o VTube Studio no PC.
2. Vá nas opções e **Ative o Plugins API** (Porta padrão: 8001).
3. A Hana vai pedir para se conectar a primeira vez que você rodar. Clique no botão de permitir dentro do VTube Studio!

---

## 🚀 Como Iniciar a Máquina

Tudo configurado? A hora chegou!
Abra a pasta do projeto, digite `cmd` na barrinha de cima pra abrir o console, e escolha uma das duas formas de dar vida a ela:

**1. Modo Clássico (O Cérebro no Terminal):**
```bash
python main.py
```
*A tela vai subir o banner. Depois disso, aperte (ou segure) o botão configurado (padrão MOUSE_X1 ou botão lateral do mouse) para falar no microfone. Ela ouvirá, pensará e responderá em voz alta e texto.*

**2. O Modo Deus (Painel de Controle Gráfico):**
```bash
python -m src.gui.hana_gui
```
*Abre um painel lindo onde você pode gerenciar tudo visualmente! Deste painel, você pode dar `Start` na Hana, trocar os LLMs no voo, ver a memória dela visualmente e injetar imagens pro chat.*

---

## ⚙️ Configuração Ninja (Power Users)

- **A Personalidade da Hana:** O arquivo `src/config/persona.txt` (que o Git ignora as edições) é o coração dela. Edite esse arquivo para mudar quem ela é, os seus gostos peculiares e as gírias pesadas que ela solta. (Sim, ela xinga!).
- **Hot-Reload de Configs:** Altere as configurações no Painel Gráfico ou no `config.json` e o *main loop* da Hana aplicará as regras no próximo turno instantaneamente, sem precisar reiniciar o processo.
- **Auto-Detecção de Sub-Pastas:** A Hana cria as próprias pastas de `Inbox` e de `Geração de Imagens` dinamicamente no seu Windows baseado na sua pasta raiz (`~Home`). Se precisar focar os caminhos, vá no arquivo de configurações do sistema.

---
---
*Projeto mantido pela comunidade NakamuraIA. Colabore e ajude a Hana a dominar o mundo! Fufu.*

<div align="center">
  <img src="https://count.getloli.com/get/@Rukafuu?theme=booru-lewd" alt="Moe Counter" />
</div>
