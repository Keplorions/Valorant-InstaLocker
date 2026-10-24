@echo off
title VALO LOCKER - BASLATICI
echo.
echo [VALO LOCKER] Kutuphaneler kontrol ediliyor...
echo.
python -m pip install -r requirements.txt
cls
echo.
echo [VALO LOCKER] Baslatiliyor...
echo.
python locker.py
pause
