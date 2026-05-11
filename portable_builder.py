"""
Lira Portable Builder — Transforma a Lira em um .exe.
Usa PyInstaller para empacotar todas as dependências.
"""

import os
import subprocess
import sys

def build():
    print("=== LIRA PORTABLE BUILDER ===")
    
    # Verifica se PyInstaller está instalado
    try:
        import PyInstaller
    except ImportError:
        print("Instalando PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Nome do executável
    app_name = "LiraVT"
    main_script = "main.py"
    
    # Comandos do PyInstaller
    # --onefile: Gera um único .exe
    # --windowed: Não abre console (usaremos se a GUI for o foco, mas a Lira tem terminal)
    # --icon: Ícone do app
    # --add-data: Inclui pastas necessárias
    
    icon_path = r"C:\Users\conta\OneDrive\Imagens\Lira\lira icon new.png" # Usar .ico se possível
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--name", app_name,
        "--add-data", "src;src",
        "--add-data", "data;data",
        "--add-data", ".env;.",
        "--collect-all", "faster_whisper",
        "--collect-all", "customtkinter",
        "--collect-all", "onnxruntime",
        main_script
    ]
    
    print(f"Iniciando build de {app_name}...")
    try:
        subprocess.check_call(cmd)
        print("\n=== BUILD CONCLUÍDO COM SUCESSO! ===")
        print(f"O executável está na pasta 'dist/{app_name}.exe'")
    except Exception as e:
        print(f"\nErro no build: {e}")

if __name__ == "__main__":
    build()
