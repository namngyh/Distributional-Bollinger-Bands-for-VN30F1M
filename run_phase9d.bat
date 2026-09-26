@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
echo [1/8] Checking environment and disk space...
python -c "import sys, numpy, pandas, scipy; print('Python', sys.version.split()[0], 'NumPy', numpy.__version__, 'pandas', pandas.__version__, 'SciPy', scipy.__version__); sys.exit(0 if sys.version_info >= (3, 11) else 1)" || goto failed
python -c "import shutil, sys; free=shutil.disk_usage('.').free; print('Free disk GiB:', round(free / 1024**3, 2)); sys.exit(0 if free >= 6 * 1024**3 else 1)" || goto failed
echo [2/8] Checking versioned config and completed upstream artifacts...
if not exist "configs\phase9d_v1.json" goto missing_input
if not exist "configs\distribution_fit_v2.json" goto missing_input
if not exist "outputs\data_v1\manifest.json" goto missing_input
if not exist "outputs\data_v1\samples_1m.csv" goto missing_input
if not exist "outputs\data_v1\samples_5m.csv" goto missing_input
if not exist "outputs\phase7a_v1\1m\hl30\latest.json" goto missing_input
if not exist "outputs\phase7a_v1\5m\hl30\latest.json" goto missing_input
echo [3/8] Validating inputs and any existing Phase 9D checkpoints (read-only)...
for %%T in (1m 5m) do for %%H in (30 60) do (
  python -m distributional_bands.win_retry distributional_bands.phase9d --timeframe %%T --half-life %%H --input "outputs\data_v1\samples_%%T.csv" --output-dir "outputs\phase9d_v1\%%T\hl%%H" --check-only || goto failed
)
if /i "%~1"=="check" goto checked
echo [4/8] Starting or resuming 5m, half-life 30...
python -m distributional_bands.win_retry distributional_bands.phase9d --timeframe 5m --half-life 30 --input "outputs\data_v1\samples_5m.csv" --output-dir "outputs\phase9d_v1\5m\hl30"
if errorlevel 1 goto failed
echo [5/8] Starting or resuming 5m, half-life 60...
python -m distributional_bands.win_retry distributional_bands.phase9d --timeframe 5m --half-life 60 --input "outputs\data_v1\samples_5m.csv" --output-dir "outputs\phase9d_v1\5m\hl60"
if errorlevel 1 goto failed
echo [6/8] Starting or resuming 1m, half-life 30...
python -m distributional_bands.win_retry distributional_bands.phase9d --timeframe 1m --half-life 30 --input "outputs\data_v1\samples_1m.csv" --output-dir "outputs\phase9d_v1\1m\hl30"
if errorlevel 1 goto failed
echo [7/8] Starting or resuming 1m, half-life 60...
python -m distributional_bands.win_retry distributional_bands.phase9d --timeframe 1m --half-life 60 --input "outputs\data_v1\samples_1m.csv" --output-dir "outputs\phase9d_v1\1m\hl60"
if errorlevel 1 goto failed
echo [8/8] Building 5m and 1m reports...
python -m distributional_bands.win_retry distributional_bands.phase9d_report --timeframe 5m --input "outputs\data_v1\samples_5m.csv"
if errorlevel 1 goto failed
python -m distributional_bands.win_retry distributional_bands.phase9d_report --timeframe 1m --input "outputs\data_v1\samples_1m.csv"
if errorlevel 1 goto failed
echo Complete. Return outputs\phase9d_v1 for verification and discussion.
exit /b 0
:checked
echo Preflight complete. No Phase 9D computation was started.
exit /b 0
:missing_input
echo ERROR: Missing config, DATA-V1 or completed Phase 7A HL30 artifacts.
goto failed
:failed
echo ERROR: Phase 9D stopped. All checkpoints and upstream artifacts remain available.
echo Fix the error and rerun this same .bat. Do not delete outputs\phase9d_v1.
pause
exit /b 1
