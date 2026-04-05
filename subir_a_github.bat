@echo off
echo ====================================================
echo OBTENIENDO TODO LISTO PARA SUBIR A GITHUB...
echo ====================================================

:: Initialize Git if not already
git init

:: Add all files
git add .

:: Initial Commit
git commit -m "Primera subida: Predictor Sabermetrico MLB (React + Python)"

echo.
echo ====================================================
echo ¡Archivos locales listos! 
echo ====================================================
echo.
echo Ahora ve a https://github.com/new 
echo 1. Crea un repositorio vacio (ponle nombre 'mlb-predictor').
echo 2. NO marques ninguna casilla de README.
echo 3. Cuando lo crees, copia y pega aqui mismo en tu consola 
echo las dos lineas que dicen "git remote add origin..." y "git push -u origin main".
echo.
pause
