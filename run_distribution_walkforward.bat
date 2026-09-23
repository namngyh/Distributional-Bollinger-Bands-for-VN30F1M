@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
echo [1/7] Checking Python and dependencies...
python -c "import sys, numpy, pandas, scipy; print('Python', sys.version.split()[0], 'NumPy', numpy.__version__, 'pandas', pandas.__version__, 'SciPy', scipy.__version__); sys.exit(0 if sys.version_info >= (3, 11) else 1)" || goto failed
python -c "import shutil, sys; free=shutil.disk_usage('.').free; print('Free disk GiB:', round(free / 1024**3, 2)); sys.exit(0 if free >= 4 * 1024**3 else 1)" || goto failed
echo [2/7] Checking configs and DATA-V1 artifacts...
if not exist "configs\walk_forward_v1.json" goto missing_input
if not exist "configs\distribution_fit_v2.json" goto missing_input
if not exist "outputs\data_v1\manifest.json" goto missing_input
if not exist "outputs\data_v1\samples_1m.csv" goto missing_input
if not exist "outputs\data_v1\samples_5m.csv" goto missing_input
echo [3/7] Validating inputs and existing checkpoints for both timeframes...
python -m distributional_bands.walk_forward --timeframe 1m --config "configs\walk_forward_v1.json" --fit-config "configs\distribution_fit_v2.json" --input "outputs\data_v1\samples_1m.csv" --data-manifest "outputs\data_v1\manifest.json" --output-dir "outputs\distribution_wf_v1\1m" --check-only
if errorlevel 1 goto failed
python -m distributional_bands.walk_forward --timeframe 5m --config "configs\walk_forward_v1.json" --fit-config "configs\distribution_fit_v2.json" --input "outputs\data_v1\samples_5m.csv" --data-manifest "outputs\data_v1\manifest.json" --output-dir "outputs\distribution_wf_v1\5m" --check-only
if errorlevel 1 goto failed
if /i "%~1"=="check" goto checked
echo [4/7] Starting or resuming 1m development walk-forward...
python -m distributional_bands.walk_forward --timeframe 1m --config "configs\walk_forward_v1.json" --fit-config "configs\distribution_fit_v2.json" --input "outputs\data_v1\samples_1m.csv" --data-manifest "outputs\data_v1\manifest.json" --output-dir "outputs\distribution_wf_v1\1m"
if errorlevel 1 goto failed
echo [5/7] Starting or resuming 5m development walk-forward...
python -m distributional_bands.walk_forward --timeframe 5m --config "configs\walk_forward_v1.json" --fit-config "configs\distribution_fit_v2.json" --input "outputs\data_v1\samples_5m.csv" --data-manifest "outputs\data_v1\manifest.json" --output-dir "outputs\distribution_wf_v1\5m"
if errorlevel 1 goto failed
echo [6/7] Both timeframes complete. Check metrics.json and fit_history.json in outputs\distribution_wf_v1.
echo [7/7] Return these artifacts for integrity and OOS comparison review.
exit /b 0
:checked
echo Preflight complete. No distribution fit was started.
exit /b 0
:missing_input
echo ERROR: Missing config or prepared DATA-V1 artifacts. See README.md.
goto failed
:failed
echo ERROR: Walk-forward stopped. Existing checkpoints and predictions remain available for resume.
echo Fix the error, then rerun this same .bat. Do not delete outputs\distribution_wf_v1.
pause
exit /b 1
