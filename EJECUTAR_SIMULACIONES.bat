@echo off
title Proyecto Comunicaciones II - BPSK - ejecucion automatica
echo ============================================================
echo  Proyecto Comunicaciones II - BPSK telemetria (UIS)
echo  Compila los .grc, ejecuta las simulaciones y guarda capturas.
echo  Tarda unos 10 a 25 minutos. No cierres esta ventana.
echo ============================================================
call "%USERPROFILE%\radioconda\Scripts\activate.bat" "%USERPROFILE%\radioconda"
cd /d "%~dp0"
if exist resultados\simulacion\TERMINADO.txt del resultados\simulacion\TERMINADO.txt
python scripts\ejecutar_y_capturar.py compilar
python scripts\ejecutar_y_capturar.py beta
python scripts\ejecutar_y_capturar.py costas
python scripts\ejecutar_y_capturar.py limpio
python scripts\ejecutar_y_capturar.py sim
echo terminado > resultados\simulacion\TERMINADO.txt
echo.
echo LISTO. Ya puedes cerrar esta ventana.
pause
