@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
echo [1/7] Checking Python, dependencies and free disk space...
python -c "import sys, numpy, pandas, scipy; print('Python', sys.version.split()[0], 'NumPy', numpy.__version__, 'pandas', pandas.__version__, 'SciPy', scipy.__version__); sys.exit(0 if sys.version_info >= (3, 11) else 1)" || goto failed
python -c "import shutil, sys; free=shutil.disk_usage('.').free; print('Free disk GiB:', round(free / 1024**3, 2)); sys.exit(0 if free >= 4 * 1024**3 else 1)" || goto failed
echo [2/7] Checking Phase 7B config and completed Phase 7A inputs...
if not exist "configs\phase7b_v1.json" goto missing_input
if not exist "outputs\data_v1\samples_1m.csv" goto missing_input
if not exist "outputs\data_v1\samples_5m.csv" goto missing_input
if not exist "outputs\phase7a_v1\1m\report.json" goto missing_input
if not exist "outputs\phase7a_v1\5m\report.json" goto missing_input
python -m distributional_bands.phase7a --timeframe 1m --half-life 30 --input "outputs\data_v1\samples_1m.csv" --output-dir "outputs\phase7a_v1\1m\hl30" --check-only
if errorlevel 1 goto failed
python -m distributional_bands.phase7a --timeframe 5m --half-life 30 --input "outputs\data_v1\samples_5m.csv" --output-dir "outputs\phase7a_v1\5m\hl30" --check-only
if errorlevel 1 goto failed
python -m distributional_bands.phase7a_report --timeframe 1m --input "outputs\data_v1\samples_1m.csv" --selection-dir "outputs\selection_v1\1m" --check-only
if errorlevel 1 goto failed
python -m distributional_bands.phase7a_report --timeframe 5m --input "outputs\data_v1\samples_5m.csv" --selection-dir "outputs\selection_v1\5m" --check-only
if errorlevel 1 goto failed
echo [3/7] Checking Phase 7B checkpoints...
python -m distributional_bands.phase7b --timeframe 1m --source-dir "outputs\phase7a_v1\1m\hl30" --source-report "outputs\phase7a_v1\1m\report.json" --output-dir "outputs\phase7b_v1\1m" --check-only
if errorlevel 1 goto failed
python -m distributional_bands.phase7b --timeframe 5m --source-dir "outputs\phase7a_v1\5m\hl30" --source-report "outputs\phase7a_v1\5m\report.json" --output-dir "outputs\phase7b_v1\5m" --check-only
if errorlevel 1 goto failed
if /i "%~1"=="check" goto checked
echo [4/7] Starting or resuming 1m past-only PIT calibration...
python -m distributional_bands.phase7b --timeframe 1m --source-dir "outputs\phase7a_v1\1m\hl30" --source-report "outputs\phase7a_v1\1m\report.json" --output-dir "outputs\phase7b_v1\1m"
if errorlevel 1 goto failed
echo [5/7] Starting or resuming 5m past-only PIT calibration...
python -m distributional_bands.phase7b --timeframe 5m --source-dir "outputs\phase7a_v1\5m\hl30" --source-report "outputs\phase7a_v1\5m\report.json" --output-dir "outputs\phase7b_v1\5m"
if errorlevel 1 goto failed
echo [6/7] Building paired OOS reports...
python -m distributional_bands.phase7b_report --timeframe 1m --source-dir "outputs\phase7a_v1\1m\hl30" --source-report "outputs\phase7a_v1\1m\report.json" --output-dir "outputs\phase7b_v1\1m"
if errorlevel 1 goto failed
python -m distributional_bands.phase7b_report --timeframe 5m --source-dir "outputs\phase7a_v1\5m\hl30" --source-report "outputs\phase7a_v1\5m\report.json" --output-dir "outputs\phase7b_v1\5m"
if errorlevel 1 goto failed
echo [7/7] Complete. Return outputs\phase7b_v1 for verification and model-lock discussion.
exit /b 0
:checked
echo Preflight complete. No Phase 7B trial was started.
exit /b 0
:missing_input
echo ERROR: Missing Phase 7B config or completed Phase 7A artifacts.
goto failed
:failed
echo ERROR: Phase 7B stopped. Checkpoints and Phase 7A artifacts remain available.
echo Fix the error and rerun this same .bat. Do not delete outputs\phase7b_v1.
pause
exit /b 1
