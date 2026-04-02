# Análise Técnica Completa do Projeto Hana

Data da análise: 2026-04-02  
Projeto analisado em: `E:\Projeto_Hana_AI`

## Escopo

Esta análise cobre:

- arquitetura geral
- terminal principal
- chat do painel de controle
- TTS/STT
- memória curta, vetorial e grafo
- pesquisa web
- anexos, PDFs, áudio e vídeo
- integração com VTube Studio
- UI/UX do painel
- consistência de configuração, dependências e documentação

## Resumo Executivo

- O projeto tem potencial e já possui vários blocos importantes, mas hoje está com a arquitetura muito fragmentada.
- Terminal e chat da GUI não compartilham o mesmo pipeline real. Na prática, parecem dois produtos diferentes.
- A memória longa existe, mas a recuperação está inconsistente por causa de poluição de dados, falta de resolução de entidade e dessincronização entre grafo e vetor.
- A pesquisa web está espalhada entre caminhos diferentes, sem uma camada central de capacidades por provedor/modelo.
- A integração com VTube Studio está incompleta: há movimento de cabeça/olhos, mas não há lipsync real, o status da GUI não reflete a conexão real e host/porta configurados nem são usados.
- O painel visual tem problemas reais de UX: markdown quase inexistente, sem drag-and-drop, sem cancelamento de inferência, e até conflito de layout na sidebar.
- Há inconsistências graves entre o que a UI promete, o que o `config.json` salva e o que o runtime realmente aplica.
- Dependências e onboarding estão desalinhados com o código atual.

## Achados Críticos

### 1. Chat da GUI quebra fora do Google

Severidade: crítica

Evidências:

- `src/brain/base_llm.py:128-133` sempre chama `_chamar_api(..., arquivos_multimidia=...)`.
- `src/providers/groq_provider.py:23`
- `src/providers/openrouter_provider.py:47`
- `src/providers/cerebras_provider.py:40`
- Esses três providers síncronos não aceitam `arquivos_multimidia`.

Validação prática:

- Reproduzido localmente:
  `GroqProvider._chamar_api() got an unexpected keyword argument 'arquivos_multimidia'`
- O mesmo erro apareceu para OpenRouter e Cerebras.

Impacto:

- O chat do painel de controle está funcionalmente quebrado para Groq, OpenRouter e Cerebras.
- Isso explica por que a experiência “só funciona direito no Google”.

Correção recomendada:

- Padronizar a assinatura de todos os providers.
- Ou remover `arquivos_multimidia` do caminho síncrono genérico e tratar capacidades por provider.

### 2. Terminal e GUI usam pipelines diferentes e incompatíveis

Severidade: crítica

Evidências no terminal:

- `main.py:135-137` usa memória híbrida completa.
- `main.py:236-326` usa `SentenceDivider`, parser de emoções, parâmetros VTS e parser XML.
- `main.py:303-326` executa ferramentas pós-resposta.

Evidências na GUI:

- `src/gui/frames/tab_chat.py:471-477` carrega apenas histórico do SQLite.
- `src/gui/frames/tab_chat.py:521-527` só chama `llm.gerar_resposta(...)`.
- Não há `ToolManager`, `SentenceDivider`, `EmotionEngine`, `VTSController` nem parser XML no fluxo da GUI.

Impacto:

- A Hana do terminal e a Hana do painel não têm paridade funcional.
- O chat da GUI não usa memória longa real.
- O chat da GUI não executa ações silenciosas.
- O chat da GUI não processa ferramentas.
- O chat da GUI não espelha o comportamento “completo” prometido.

Correção recomendada:

- Extrair um orquestrador único de conversa.
- Fazer terminal e GUI chamarem o mesmo pipeline.

### 3. Vazamento de XML/TTS é um problema estrutural, não só cosmético

Severidade: crítica

Evidências:

- `main.py:255` imprime `"[HANA]:"` a cada chunk.
- `main.py:259` limpa TTS chunk a chunk.
- `main.py:279-326` só processa XML depois da resposta inteira.
- `src/utils/sentence_divider.py:195-202` remove apenas tags completas.
- `src/utils/text.py:41-50` também assume tags completas.

Diagnóstico:

- Se a resposta chega fragmentada e a tag XML ainda não fechou, o conteúdo interno pode escapar do filtro e ir para a fala.
- Como o terminal imprime prefixo por chunk, o efeito visual é exatamente o que você relatou: várias “Hana” cortadas e resposta quebrada.

Impacto:

- XML pode vazar para voz.
- XML pode vazar para terminal.
- A leitura fica artificial e confusa.

Correção recomendada:

- Separar texto falado e ações estruturadas antes da etapa de TTS.
- Não depender de regex pós-stream como barreira principal.
- No terminal, imprimir stream incremental sem repetir prefixo em cada chunk.

### 4. A memória longa está inconsistente por desenho e por dados

Severidade: crítica

Evidências:

- `src/memory/memory_manager.py:108-121` monta contexto híbrido.
- `src/memory/memory_manager.py:123-141` extrai entidades de forma muito frágil.
- Consulta validada localmente:
  `_extrair_entidades("quando é meu aniversário") -> []`
- Consulta validada localmente:
  `_extrair_entidades("qual é a data de aniversario do nakamura") -> ['nakamura']`

Consequência direta:

- A pergunta “quando é meu aniversário?” não ativa a camada de grafo, mesmo quando o fato existe.

Problemas adicionais:

- `src/memory/memory_manager.py:84-106` salva muita coisa como `hana_nota -> deve_lembrar -> texto inteiro`.
- `src/memory/memory_manager.py:91-95` transforma qualquer número encontrado em `número_importante`.
- O grafo local contém fatos úteis misturados com ruído e conflitos.
- O RAG retorna memórias irrelevantes para perguntas simples, como foi reproduzido localmente.

Exemplo validado:

- Para a query `quando é meu aniversário`, o RAG retornou memórias como:
  `que eu dou um ok aqui`
  `Ei, guri, mano.`
  `Que dia que eu nasci?`

Impacto:

- A Hana “sabe” algo no armazenamento, mas falha em recuperar no momento certo.
- Isso bate exatamente com o problema do aniversário que você relatou.

Correção recomendada:

- Resolver pronomes de 1ª pessoa para a entidade do usuário.
- Priorizar fatos estruturados antes de RAG livre.
- Parar de armazenar texto solto como fato permanente.
- Criar desduplicação, normalização e política de conflito.

### 5. O painel de Memória cria inconsistência entre grafo e vetor

Severidade: crítica

Evidências:

- `src/gui/frames/tab_memoria.py:274` salva fato manual só no grafo.
- `src/gui/frames/tab_memoria.py:290-291` apaga do grafo e salva.
- Não existe sincronização com Chroma nesse fluxo.
- `src/memory/memory_manager.py:26-38` só sincroniza grafo -> RAG na inicialização do `HanaMemoryManager`.

Impacto:

- Fato manual salvo na GUI pode não aparecer na busca semântica.
- Fato deletado no grafo pode continuar vivo no banco vetorial.
- Isso contribui para memória contraditória e respostas erradas.

Correção recomendada:

- Toda operação manual na GUI deve passar por um service layer único.
- Salvar e deletar precisam atualizar grafo, vetor e qualquer índice derivado.

### 6. Mensagens `System` voltam para o prompt como se fossem falas da Hana

Severidade: crítica

Evidências:

- `main.py:314` salva resultado de ferramenta como `System`.
- `src/brain/base_llm.py:58-60`
- `src/brain/base_llm.py:117-121`
- Qualquer role diferente de `Nakamura` vira `assistant`.

Impacto:

- Transcrições, blocos internos e resultados de ferramenta entram no histórico futuro como se fossem mensagens da Hana.
- Isso distorce contexto, persona e recuperação.

Correção recomendada:

- Preservar `system` como `system`, ou excluir esse material do histórico conversacional bruto.
- Separar memória operacional de histórico de diálogo.

## Achados Altos

### 7. Vídeo, PDF e mídia pesada: fluxo bloqueante e sem cancelamento real

Severidade: alta

Evidências:

- `src/gui/frames/tab_chat.py:434-560` processa em thread simples.
- `src/gui/frames/tab_chat.py:496-504` bloqueia mídia pesada fora do Google.
- `src/providers/google_provider.py:64-75`
- `src/providers/google_provider.py:134-143`
- `src/gui/frames/tab_chat.py:663-669` o botão “Parar” só tenta parar `pygame`.

Diagnóstico:

- Upload é síncrono.
- Geração é síncrona.
- Não existe token de cancelamento.
- Não existe timeout explícito.
- Não existe progresso real.

Impacto:

- Se o arquivo é pesado ou o provider demora, a experiência trava.
- Isso bate com o seu relato de “fica muito tempo processando e não consigo interromper”.

Correção recomendada:

- Implementar cancelamento cooperativo.
- Separar upload, polling e resposta em estados.
- Exibir progresso real por etapa.
- Criar timeout por operação.

### 8. Pesquisa web está fragmentada e acoplada ao provider errado

Severidade: alta

Evidências:

- `src/providers/google_provider.py:76-85` habilita Google Search só quando não há imagem nem mídia.
- `main.py:208-214` captura visão em todo turno quando `VISAO_ATIVA` está ligada.
- `main.py:316-326` usa `<ferramenta_web>` no terminal.
- `src/config/prompt.json:3-4` proíbe inventar `<ferramenta_web>` e diz que pesquisa nativa não deve usar tag.
- `src/brain/tool_manager.py:89-110` implementa Tavily de forma paralela ao resto.
- `src/config/config.json:16` tem `modelo_web` para Groq, mas o código não usa essa capacidade como política unificada.

Diagnóstico:

- O sistema não tem uma camada central do tipo:
  “este modelo suporta search nativo?”
  “este suporta search com visão?”
  “este usa fallback Tavily?”
- Em vez disso, cada trecho decide sozinho.

Impacto:

- Com visão global ligada, a pesquisa nativa do Google é desativada por código.
- Groq Compound não foi integrado como capability real.
- OpenAI/Azure OpenAI não existem como providers próprios.
- Tavily fica como remendo isolado.

Correção recomendada:

- Criar um registro de capacidades por provider/modelo.
- Separar `chat`, `vision`, `web_search`, `file_upload`, `thinking`, `video`, `music`.
- Escolher motor por capability, não por `if provedor == ...`.

### 9. O provider “google_cloud” não está implementado como Vertex completo

Severidade: alta

Evidência:

- `src/providers/google_provider.py:26` usa `genai.Client(api_key=api_key)`.

Leitura técnica:

- Isso indica um caminho baseado em API key do ecossistema Gemini, não uma integração Vertex completa com projeto/região/capabilities específicas do Vertex.

Impacto:

- Recursos Vertex que você citou, como Thinking, Veo, Lyria, contagem de tokens e outras APIs específicas, não estão realmente integrados hoje.
- O nome `google_cloud` induz a acreditar em algo mais completo do que o código entrega.

Observação:

- Isso é uma inferência baseada no código atual e na documentação oficial do Vertex AI.

### 10. VTube Studio: host/porta ignorados, boca sem movimento, status da GUI é enganoso

Severidade: alta

Evidências:

- `src/modules/vts_controller.py:90` cria `pyvts.vts(plugin_info=plugin_info)` sem passar host/porta.
- A assinatura local de `pyvts.vts(...)` aceita `vts_api_info` com `host` e `port`.
- `src/modules/vts_controller.py:320-328` injeta cabeça, olhos e respiração.
- Não há `ParamMouthOpenY`, `ParamMouthForm` ou equivalente.
- `src/gui/frames/tab_vtube.py:166-177` status usa só `CONFIG.get("VTUBESTUDIO_ATIVO")`.

Impacto:

- Configurar host/porta na GUI não garante efeito real.
- A boca não mexe porque não existe lipsync/parâmetro de boca no loop.
- A GUI pode mostrar “ativo” sem confirmar sessão real.

Problemas extras:

- `src/modules/vts_controller.py:60-66` faz `stop()` sem parar o loop/event thread de forma limpa.
- `main.py:102-109` no hot-reload cria `VTSController` sem `signals=signals`.

Correção recomendada:

- Passar `vts_api_info` corretamente.
- Criar status real de conexão/autenticação.
- Implementar lipsync por RMS/fonema.
- Fazer shutdown limpo do loop async.

## Achados Médios

### 11. A personalização está “escondida” porque há conflito real de grid

Severidade: média

Evidências:

- `src/gui/hana_gui.py:134` botão `Personalização` usa `row=13`.
- `src/gui/hana_gui.py:153` `_status_frame` também usa `row=13`.

Impacto:

- O bloco `ONLINE` invade o mesmo espaço do item de menu.
- Isso explica exatamente o print que você mandou.

### 12. O chat do painel quase não tem markdown de verdade

Severidade: média

Evidências:

- `src/gui/frames/tab_chat.py:341-409`
- `src/gui/frames/tab_chat.py:399-401` literalmente comenta que “por enquanto” só remove `**`.
- Usa `CTkLabel` para tudo, sem parser real.

Impacto:

- Quebras de linha não ficam naturais.
- Negrito é improvisado.
- Listas, blocos longos e formatação rica ficam pobres.
- A UX fica longe de ChatGPT/Claude/Gemini.

### 13. Não existe drag-and-drop de arquivos no chat

Severidade: média

Evidências:

- Não há binding de DnD/tkdnd/drop no projeto.
- O chat usa apenas `filedialog.askopenfilenames()` em `src/gui/frames/tab_chat.py:566-583`.

Impacto:

- O usuário precisa caçar arquivo manualmente.
- Isso piora muito a ergonomia do painel.

### 14. `.docx` no chat da GUI cai em leitura errada

Severidade: média

Evidências:

- `src/gui/frames/tab_chat.py:573` aceita `.docx`.
- `src/gui/frames/tab_chat.py:506-512` lê arquivos “texto” com `open(..., "r")`.
- O código certo para `.docx` existe em `src/modules/tools/inbox_manager.py:205-214`, mas não é usado no chat.

Impacto:

- `.docx` anexado na GUI tende a virar lixo binário/XML zipado em vez de texto útil.

### 15. O sistema de Inbox existe, mas está solto e pouco integrado

Severidade: média

Evidências:

- `src/modules/tools/inbox_manager.py` tem bastante lógica útil.
- Mas não há integração real no fluxo principal nem watcher funcional no projeto atual.

Impacto:

- Você tem um módulo pronto pela metade, mas a experiência real do usuário depende de outro caminho.
- Isso aumenta duplicação e inconsistência.

### 16. Hot-reload e configuração “em tempo real” não são confiáveis

Severidade: média

Evidências:

- `src/brain/base_llm.py:15` define `self.temperatura = 1.0`.
- Os providers carregados continuam com `temperatura=1.0`.
- `main.py:95-99` recria selector só quando o provider muda.
- `src/providers/provider_selector.py:14-43` cacheia instâncias.
- `src/gui/frames/tab_chat.py:213-256` cacheia `_llm_instance`.

Impacto:

- Trocar modelo dentro do mesmo provider pode não surtir efeito imediato.
- Slider de temperatura hoje é, na prática, quase decorativo.

### 17. Configuração de PTT da GUI não conversa com o STT real

Severidade: média

Evidências:

- GUI salva `GUI.ptt_enabled` e `GUI.ptt_key` em `src/gui/frames/tab_conexoes.py`.
- STT lê `precione_para_falar` e `TECLA_PTT` em `src/modules/voice/stt_whisper.py:62-63`.
- Essas chaves nem existem no `config.json` atual.

Impacto:

- O toggle de PTT do painel não governa o motor real.

### 18. TTS da UI está inconsistente com o runtime

Severidade: média

Evidências:

- `src/gui/frames/tab_llm.py:82` oferece `google`, `edge`, `azure`.
- `src/modules/voice/tts_selector.py:28-29` diz que agora só mantém `google`.
- `src/modules/voice/tts_selector.py:67-72` cacheia instância.
- `src/modules/voice/tts_google.py:29-32` lê voz/rate/pitch só no `__init__`.

Impacto:

- A UI promete TTSs que o seletor não usa de verdade.
- Alterações de voz/velocidade/pitch podem não aplicar sem reiniciar a instância.

### 19. ToolManager tem duplicação de método, sinal de merge mal resolvido

Severidade: média

Evidências:

- `src/brain/tool_manager.py` possui `_despachar_anotacao` duplicado.
- `src/brain/tool_manager.py` possui `_despachar_youtube` duplicado.

Impacto:

- Aumenta risco de manutenção.
- É um cheiro claro de código colado/merge sujo.

### 20. `analisar_youtube` baixa transcrição, mas não faz pipeline de análise de verdade

Severidade: média

Evidências:

- `src/brain/tool_manager.py:134-189` apenas baixa legenda.
- `main.py:307-314` injeta o resultado no sistema/memória.

Impacto:

- O fluxo é pesado.
- A “análise” real depende de turnos posteriores.
- A resposta ao usuário tende a ser fraca para o custo do processamento.

## Dependências, Setup e Documentação

### 21. `requirements.txt` e `.env.example` não batem com o código

Severidade: alta

Dependências usadas no código mas ausentes do `requirements.txt`:

- `openai`
- `pyvts`
- `youtube_transcript_api`
- `pypdf` ou `PyPDF2`
- o provider Cerebras também depende de SDK específico

Validação prática no ambiente:

- `youtube_transcript_api`: faltando
- `pypdf`: faltando
- `PyPDF2`: faltando

Problema adicional:

- `.env.example` não expõe `OPENROUTER_API_KEY` nem `CEREBRAS_API_KEY`, embora o projeto suporte esses providers.

Impacto:

- Setup novo tende a quebrar em recursos específicos.

### 22. README vende mais do que a build atual entrega

Severidade: média

Pontos em que o discurso está à frente da implementação:

- “cross-platform”
- inbox instantânea integrada
- controle total do VTube Studio
- chat GUI equivalente ao terminal
- hot-reload amplo de comportamento

Impacto:

- Gera expectativa errada.
- Dificulta priorização real.

## Observações Externas Relevantes

Validadas com documentação oficial:

- Groq Compound possui capacidades como web search/browser automation/code execution, mas isso não está integrado como capability central no projeto.
- Vertex AI possui documentação própria para Thinking.
- Veo 3.1 e Lyria existem como linhas de produto no ecossistema Vertex.
- O código atual, porém, está estruturado como chat-provider genérico, não como plataforma multi-capability orientada a Vertex.

Links oficiais consultados:

- Groq Compound: https://console.groq.com/docs/compound/systems/compound
- Vertex AI Thinking: https://cloud.google.com/vertex-ai/generative-ai/docs/thinking?hl=pt-br
- Veo no Vertex AI: https://cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos
- Lyria no Vertex AI: https://cloud.google.com/vertex-ai/generative-ai/docs/music/generate-music

## Prioridade Recomendada de Correção

### Fase 1: estabilizar o núcleo

- unificar pipeline terminal + GUI
- corrigir assinatura dos providers
- corrigir vazamento de XML/TTS
- corrigir memória híbrida e resolução de entidade

### Fase 2: devolver confiabilidade ao usuário

- cancelamento real de upload/inferência
- progresso real por etapa
- status real de VTube Studio
- correção do conflito visual da sidebar

### Fase 3: arrumar a camada de capacidades

- capability registry por provider/modelo
- pesquisa unificada
- separação entre chat, visão, web, thinking, vídeo, música
- provider Google/Vertex realmente orientado a Vertex quando necessário

### Fase 4: limpar UX e dados

- markdown real no chat
- drag-and-drop
- textarea multiline
- higienização da base de memória
- política de conflito, atualização e deleção de fatos

### Fase 5: reduzir dívida técnica

- limpar duplicações
- alinhar README e setup
- alinhar `.env.example`, `requirements.txt` e providers reais

## Diagnóstico Final

Hoje o maior problema da Hana não é “falta de feature”. É falta de eixo central.

Você já tem:

- UI
- memória
- multimodal
- VTube
- múltiplos providers
- pesquisa

Mas cada um vive em um fluxo diferente, com contratos diferentes e regras diferentes. O resultado é o clássico sistema que “tem muita coisa” e ao mesmo tempo passa sensação de frágil.

Se eu tivesse que resumir em uma frase:

> a Hana já tem peças de produto avançado, mas ainda está operando como uma coleção de módulos acoplados de forma desigual, em vez de um runtime único e coerente.

## Próximo passo mais inteligente

Se você quiser, o próximo trabalho ideal não é sair enfiando feature nova.

O passo certo é:

1. consolidar um runtime único de conversa
2. refatorar memória e capabilities
3. corrigir GUI chat para virar cliente desse runtime
4. só depois expandir Vertex/OpenAI/Azure/Groq Compound/Veo/Lyria

Isso reduz retrabalho, melhora latência e impede que cada feature nova entre quebrando duas antigas.
