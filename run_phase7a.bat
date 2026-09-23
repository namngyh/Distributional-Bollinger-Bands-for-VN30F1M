@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
echo [1/9] Checking environment and disk space...
python -c "import sys, numpy, pandas, scipy; print('Python', sys.version.split()[0], 'NumPy', numpy.__version__, 'pandas', pandas.__version__, 'SciPy', scipy.__version__); sys.exit(0 if sys.version_info >= (3, 11) else 1)" || goto failed
python -c "import shutil, sys; free=shutil.disk_usage('.').free; print('Free disk GiB:', round(free / 1024**3, 2)); sys.exit(0 if free >= 4 * 1024**3 else 1)" || goto failed
echo [2/9] Checking versioned config and completed upstream artifacts...
if not exist "configs\phase7a_v1.json" goto missing_input
if not exist "configs\distribution_fit_v2.json" goto missing_input
if not exist "outputs\data_v1\manifest.json" goto missing_input
if not exist "outputs\data_v1\samples_1m.csv" goto missing_input
if not exist "outputs\data_v1\samples_5m.csv" goto missing_input
if not exist "outputs\selection_v1\1m\report.json" goto missing_input
if not exist "outputs\selection_v1\5m\report.json" goto missing_input
echo [3/9] Checking 60-minute anchor and migrating verified Phase 7A checkpoints if needed...
python -m distributional_bands.selection --timeframe 1m --sample "outputs\data_v1\samples_1m.csv" --baseline-dir "outputs\baseline_v1\1m" --wf-dir "outputs\distribution_wf_v1\1m" --output-dir "outputs\selection_v1\1m" --check-only
if errorlevel 1 goto failed
python -m distributional_bands.selection --timeframe 5m --sample "outputs\data_v1\samples_5m.csv" --baseline-dir "outputs\baseline_v1\5m" --wf-dir "outputs\distribution_wf_v1\5m" --output-dir "outputs\selection_v1\5m" --check-only
if errorlevel 1 goto failed
set "MIGRATION_MODE="
if /i "%~1"=="check" set "MIGRATION_MODE=--check-only"
python -m distributional_bands.phase7a_migrate --timeframe 1m --half-life 30 --input "outputs\data_v1\samples_1m.csv" --output-dir "outputs\phase7a_v1\1m\hl30" %MIGRATION_MODE%
if errorlevel 1 goto failed
python -m distributional_bands.phase7a_migrate --timeframe 1m --half-life 120 --input "outputs\data_v1\samples_1m.csv" --output-dir "outputs\phase7a_v1\1m\hl120" %MIGRATION_MODE%
if errorlevel 1 goto failed
python -m distributional_bands.phase7a_migrate --timeframe 5m --half-life 30 --input "outputs\data_v1\samples_5m.csv" --output-dir "outputs\phase7a_v1\5m\hl30" %MIGRATION_MODE%
if errorlevel 1 goto failed
python -m distributional_bands.phase7a_migrate --timeframe 5m --half-life 120 --input "outputs\data_v1\samples_5m.csv" --output-dir "outputs\phase7a_v1\5m\hl120" %MIGRATION_MODE%
if errorlevel 1 goto failed
if /i "%~1"=="check" goto checked
python -m distributional_bands.phase7a --timeframe 1m --half-life 30 --input "outputs\data_v1\samples_1m.csv" --output-dir "outputs\phase7a_v1\1m\hl30" --check-only
if errorlevel 1 goto failed
python -m distributional_bands.phase7a --timeframe 1m --half-life 120 --input "outputs\data_v1\samples_1m.csv" --output-dir "outputs\phase7a_v1\1m\hl120" --check-only
if errorlevel 1 goto failed
python -m distributional_bands.phase7a --timeframe 5m --half-life 30 --input "outputs\data_v1\samples_5m.csv" --output-dir "outputs\phase7a_v1\5m\hl30" --check-only
if errorlevel 1 goto failed
python -m distributional_bands.phase7a --timeframe 5m --half-life 120 --input "outputs\data_v1\samples_5m.csv" --output-dir "outputs\phase7a_v1\5m\hl120" --check-only
if errorlevel 1 goto failed
echo [4/9] Starting or resuming 1m, half-life 30...
python -m distributional_bands.phase7a --timeframe 1m --half-life 30 --input "outputs\data_v1\samples_1m.csv" --output-dir "outputs\phase7a_v1\1m\hl30"
if errorlevel 1 goto failed
echo [5/9] Starting or resuming 1m, half-life 120...
python -m distributional_bands.phase7a --timeframe 1m --half-life 120 --input "outputs\data_v1\samples_1m.csv" --output-dir "outputs\phase7a_v1\1m\hl120"
if errorlevel 1 goto failed
echo [6/9] Starting or resuming 5m, half-life 30...
python -m distributional_bands.phase7a --timeframe 5m --half-life 30 --input "outputs\data_v1\samples_5m.csv" --output-dir "outputs\phase7a_v1\5m\hl30"
if errorlevel 1 goto failed
echo [7/9] Starting or resuming 5m, half-life 120...
python -m distributional_bands.phase7a --timeframe 5m --half-life 120 --input "outputs\data_v1\samples_5m.csv" --output-dir "outputs\phase7a_v1\5m\hl120"
if errorlevel 1 goto failed
echo [8/9] Building 1m and 5m OOS comparison reports...
python -m distributional_bands.phase7a_report --timeframe 1m --input "outputs\data_v1\samples_1m.csv" --selection-dir "outputs\selection_v1\1m"
if errorlevel 1 goto failed
python -m distributional_bands.phase7a_report --timeframe 5m --input "outputs\data_v1\samples_5m.csv" --selection-dir "outputs\selection_v1\5m"
if errorlevel 1 goto failed
echo [9/9] Complete. Return outputs\phase7a_v1 for verification and Phase 7A discussion.
exit /b 0
:checked
echo Preflight complete. No Phase 7A trial or checkpoint migration was started.
exit /b 0
:missing_input
echo ERROR: Missing config, DATA-V1 or completed SELECTION-V1 artifacts.
goto failed
:failed
echo ERROR: Phase 7A stopped. All checkpoints and upstream artifacts remain available.
echo Fix the error and rerun this same .bat. Do not delete outputs\phase7a_v1.
pause
exit /b 1
