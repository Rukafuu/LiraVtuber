@echo off
cd /d "%~dp0.."
echo [Lira] Iniciando WhatsApp API na porta 8043...
python apps\whatsapp_api\main.py
pause