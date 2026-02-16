@echo off
REM Test Adaptive Strategy on Real IB Data

echo ============================================================
echo Running Adaptive Market Strategy on Real Data
echo ============================================================
echo.

python src\backtest\run_backtest.py --config config_adaptive_market.yaml --data-file MES_5mins_2024-12-20_to_2026-02-13_REAL.csv

echo.
echo ============================================================
echo Backtest Complete!
echo ============================================================
echo.
echo Results saved to logs\ directory
echo.

pause
