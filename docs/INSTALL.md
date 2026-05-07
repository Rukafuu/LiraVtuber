# Instalacao da Lira

Este guia instala a Lira em um PC novo usando o minimo publico: `Groq` para LLM/STT e `Edge TTS` para voz.

## Requisitos

- Windows 10 ou 11.
- Python 3.12 recomendado.
- Node.js LTS.
- Rust stable, necessario para rodar/empacotar o Control Center Tauri.
- Git.
- Microfone funcional.
- Uma chave `GROQ_API_KEY`.

## 1. Clonar

```powershell
git clone https://github.com/AmarinthIA/AmarinthLira-VTuber-OSS.git
cd AmarinthLira-VTuber-OSS
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
cd control_panel
npm install
cd ..
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
copy src\config\persona.example.txt src\config\persona.txt
```

O `config.json` e o `persona.txt` sao locais e ignorados pelo Git.

## 6. Rodar Lira

```powershell
python main.py
```

O `main.py` inicia o runtime, a API local e o Control Center Tauri.

## 7. Rodar sem terminal visivel no Windows

```powershell
wscript run_lira_gui_hidden.vbs
```

## Setup minimo esperado

- LLM: `groq`.
- STT: Groq Whisper.
- TTS: `edge`.
- GUI: habilitada.
- Geracao de imagem/musica: opcional.
- Geracao de video: removida da release publica.
