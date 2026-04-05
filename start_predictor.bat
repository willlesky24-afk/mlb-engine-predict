@echo off
echo =========================================
echo   INICIANDO SISTEMA PREDICTOR MLB
echo =========================================

echo.
echo [1/2] Levantando API Python (Puerto 5050)...
echo NOTA: Si ves que esto tarda, es porque esta instalando librerias pesadas (Scipy).
echo POR FAVOR ESPERA hasta ver un marco que dice "API CORRIENDO PERFECTAMENTE".
start cmd /k "pip install -r requirements.txt && python mlb_api.py"

echo.
echo [2/2] Levantando Interfaz React...
start cmd /k "cd frontend && npm install && npm run dev"

echo.
echo Listo. Se han abierto dos consolas negras con los servidores.
echo Tu navegador se abrira automaticamente en unos segundos.
echo Si no se abre, entra a: http://127.0.0.1:5173
pause
