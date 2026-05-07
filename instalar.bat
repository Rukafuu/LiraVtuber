@echo off
echo ===================================
echo  LIRA — Instalador de Dependencias
echo ===================================
echo.

:: PyAudio via pipwin (evita precisar do Build Tools)
echo [1/3] Instalando PyAudio...
pip install pipwin >nul 2>&1
pipwin install pyaudio
if errorlevel 1 (
    echo     Tentando wheel alternativo...
    pip install PyAudio --find-links https://download.lfd.uci.edu/pythonlibs/archived/ >nul 2>&1
    if errorlevel 1 (
        echo     AVISO: PyAudio falhou. Voz/microfone nao funcionarao.
        echo     Instale manualmente: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
    ) else (
        echo     PyAudio instalado com sucesso.
    )
) else (
    echo     PyAudio instalado com sucesso.
)

:: Resto das dependencias (sem groq — nao obrigatorio para stack local)
echo.
echo [2/3] Instalando dependencias principais...
pip install -r requirements.txt --ignore-installed PyAudio
echo     Feito.

:: Cria .env com dummy key para nao explodir imports condicionais
echo.
echo [3/3] Criando .env...
if not exist .env (
    echo GROQ_API_KEY=nao-configurado> .env
    echo     .env criado com chave dummy.
) else (
    echo     .env ja existe, pulando.
)

echo.
echo ===================================
echo  Instalacao concluida!
echo  Para rodar:
echo    Terminal: python main.py
echo    GUI:      python -m src.gui.lira_gui
echo ===================================
pause
