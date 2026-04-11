# Instalacao da Hana

Este guia instala a Hana em um PC novo usando o minimo publico: `Groq` para LLM/STT e `Edge TTS` para voz.

## Requisitos

- Windows 10 ou 11.
- Python 3.10 ou superior.
- Git.
- Microfone funcional.
- Uma chave `GROQ_API_KEY`.

## 1. Clonar

```powershell
git clone https://github.com/NakamuraIA/HanaNakamura-VTuber-OSS.git
cd HanaNakamura-VTuber-OSS
```

## 2. Ambiente virtual

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

## 3. Dependencias

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configurar `.env`

```powershell
copy .env.example .env
```

Abra `.env` e preencha pelo menos:

```env
GROQ_API_KEY=sua_chave_groq
```

As outras chaves sao opcionais e so precisam existir se voce selecionar esses providers.

## 5. Criar config local

```powershell
copy src\config\config.example.json src\config\config.json
```

O `config.json` e local e ignorado pelo Git.

## 6. Rodar terminal

```powershell
python main.py
```

## 7. Rodar GUI

```powershell
python -m src.gui.hana_gui
```

## Setup minimo esperado

- LLM: `groq`.
- STT: Groq Whisper.
- TTS: `edge`.
- GUI: habilitada.
- Geracao de imagem/musica: opcional.
- Geracao de video: removida da release publica.
