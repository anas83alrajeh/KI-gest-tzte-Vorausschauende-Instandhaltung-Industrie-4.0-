@echo off
chcp 65001 >nul
title Vorausschauende Instandhaltung - Power BI LIVE

echo ============================================================
echo   Vorausschauende Instandhaltung - PRODUCTION READY
echo   Power BI Connected ^& Streaming Live
echo ============================================================
echo.
echo  [1/2] Pruefe / installiere benoetigte Bibliotheken...
echo.
python -m pip install --quiet requests scikit-learn numpy

if errorlevel 1 (
    echo.
    echo  [FEHLER] Python wurde nicht gefunden!
    echo  Bitte installieren Sie Python aus dem Microsoft Store.
    echo.
    pause
    exit /b
)

echo  [2/2] Starte das System...
echo  ============================================================
echo   Steuerung:  beliebige Taste = Stoerfall ^| q = Beenden
echo   Status:     Power BI Connected - Daten live ^!
echo  ============================================================
echo.
python READY_single_machine_powerbi.py

echo.
echo  Programm beendet.
echo  Pruefen Sie:
echo  - protokoll.log (Wartungsprotokolle)
echo  - Power BI Dashboard (Live-Daten)
pause
