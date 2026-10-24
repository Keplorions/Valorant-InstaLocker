@echo off
title KepsLocker - Tek EXE Derleyici
color 0b
cls
echo ========================================================
echo       KEPSLOCKER - TEK EXE DERLEME ARACI
echo ========================================================
echo.
echo [1/3] Gerekli kutuphaneler kontrol ediliyor...
python -m pip install --upgrade pyinstaller requests rich flask urllib3 pypresence >nul 2>&1

echo [2/3] PyInstaller ile tek dosya EXE olusturuluyor...
echo (Bu islem bilgisayar hizina bagli olarak 1-2 dakika surebilir)
echo.

python -m PyInstaller --noconfirm --clean --onefile --icon="app.ico" --name "KepsLocker" --add-data "stealth_engine.dat;." --add-data "app.ico;." --hidden-import "pypresence" locker.py

echo.
if exist "dist\KepsLocker.exe" (
    echo ========================================================
    echo  [BASARILI!] KepsLocker.exe basariyla olusturuldu!
    echo  Konum: dist\KepsLocker.exe
    echo ========================================================
    echo.
    echo Olusturulan EXE dosyasini istediginiz arkadasiniza veya
    echo baska bir bilgisayara tek basina gonderebilirsiniz!
) else (
    echo [HATA] Derleme sirasinda bir sorun olustu.
)

echo.
pause
