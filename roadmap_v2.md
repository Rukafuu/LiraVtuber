# LiraVT — Roadmap v2.0 (The Agency Era) 🚀

Este roadmap foca em transformar a Lira de uma assistente reativa em uma IA autônoma e imersiva.

---

### Phase 5: Agência & Proatividade 🤖
*   [ ] **Autonomous Tool Loops:** Permitir uso sequencial de ferramentas (ex: Pesquisa -> Leitura -> Escrita) sem intervenção manual.
*   [ ] **Lira Scheduler:** Sistema de agendamento proativo onde ela monitora o tempo e interrompe o usuário para avisos.
*   [ ] **Self-Memory Maintenance:** Rotina de limpeza e condensação de memórias no ChromaDB/SQLite para evitar redundâncias.

### Phase 6: Multimodality 2.0 (WhatsApp/Discord) 📱
*   [ ] **Voice-to-Voice (WA):** Integração do `faster-whisper` no Bridge para transcrever áudios recebidos e responder com voz.
*   [ ] **Video Understanding:** Extração de frames de vídeos enviados para análise visual pela Lira.
*   [ ] **Multimodal OCR:** Capacidade de ler prints de erro ou textos complexos em imagens de forma contextual.

### Phase 7: Expressividade & Imersão 🎭
*   [ ] **Emotional RVC Mapping:** Ajuste dinâmico de tom/pitch da voz RVC baseado no sentimento da resposta.
*   [ ] **VTS/Warudo Bridge:** Sincronização de expressões e movimentos 3D via WebSocket.
*   [ ] **Episodic Memory Logs:** Criação de diários ou resumos de "grandes eventos" para dar noção de passagem de tempo.

---

### Próximos Passos (Prioridade Atual):
1.  **WA Voice-to-Voice:** Implementar a ponte de áudio no `whatsapp_bridge/index.js` e o endpoint de transcrição no backend Python.
