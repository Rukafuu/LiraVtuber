@echo off
title Lira Control Center (HUD)
cd /d "%~dp0..\control_panel"

where npm.cmd >nul 2>&1
if errorlevel 1 (
  echo [ERRO] npm nao encontrado. Instale Node.js 20+ e tente de novo.
  pause
  exit /b 1
)

echo [HUD] Iniciando Vite (1425) + Tauri...
echo [HUD] Na primeira vez o Rust pode compilar ~1-3 min.
echo [HUD] Mantenha a Control API rodando: python apps\control_api\main.py
echo.

call npm.cmd run tauri dev
if errorlevel 1 (
  echo.
  echo [ERRO] Falha ao abrir HUD. Tente:
  echo   cd control_panel
  echo   npm.cmd install
  echo   npm.cmd run tauri dev
  pause
)