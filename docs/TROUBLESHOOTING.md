# Troubleshooting

## `GROQ_API_KEY` ausente

Sintoma:

```text
Provider LLM nao inicializa ou STT falha.
```

Correcao:

```env
GROQ_API_KEY=sua_chave
```

## OpenRouter `401 User not found`

Provavel causa: chave errada, chave colada com outra variavel no `.env`, ou conta sem chave ativa.

Cheque se a linha esta assim:

```env
OPENROUTER_API_KEY=sua_chave_openrouter
```

## TTS nao fala

Teste primeiro com:

```json
"TTS_PROVIDER": "edge"
```

Edge nao exige chave e ajuda a separar problema de API de problema de audio.

## Microfone nao detecta voz

Verifique:

- permissao de microfone no Windows;
- microfone padrao do sistema;
- `MIC_DEVICE_INDEX` em `src/config/config.json`;
- se `ptt_enabled` esta ligado sem voce segurar a tecla PTT.

## GUI nao abre

Rode:

```powershell
python -m src.gui.hana_gui
```

Se faltar dependencia, reinstale:

```powershell
pip install -r requirements.txt
```

## Config nao muda

O arquivo local correto e:

```text
src/config/config.json
```

Se ele nao existir, crie a partir do template:

```powershell
copy src\config\config.example.json src\config\config.json
```

## Geracao de video

Geracao de video foi removida desta release. O chat ainda pode anexar e analisar arquivos de video.

