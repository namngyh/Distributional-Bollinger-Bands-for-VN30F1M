@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
echo [1/4] Checking input and policy...
if not exist "ohlc_export.csv" goto missing_input
if not exist "configs\data_v1.json" goto missing_policy
if exist "outputs\data_v1" goto existing_output
echo [2/4] Checking Python environment...
python -c "import numpy, pandas" || goto failed
echo [3/4] Auditing and preparing 1m/5m data...
python -m distributional_bands.cli prepare --input "ohlc_export.csv" --policy "configs/data_v1.json" --output-dir "outputs/data_v1"
if errorlevel 1 goto failed
echo [4/4] Completed. See outputs\data_v1\manifest.json
exit /b 0
:missing_input
echo ERROR: ohlc_export.csv is missing.
goto failed
:missing_policy
echo ERROR: configs\data_v1.json is missing.
goto failed
:existing_output
echo ERROR: outputs\data_v1 already exists. Choose a new output path through the CLI.
goto failed
:failed
echo Preparation failed. Existing outputs were not overwritten.
pause
exit /b 1
