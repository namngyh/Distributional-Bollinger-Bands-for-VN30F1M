@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
echo [1/6] Checking Python, dependencies and disk space...
python -c "import sys, numpy, pandas, scipy; print('Python', sys.version.split()[0], 'NumPy', numpy.__version__, 'pandas', pandas.__version__, 'SciPy', scipy.__version__); sys.exit(0 if sys.version_info >= (3, 11) else 1)" || goto failed
python -c "import shutil, sys; free=shutil.disk_usage('.').free; print('Free disk GiB:', round(free / 1024**3, 2)); sys.exit(0 if free >= 1 * 1024**3 else 1)" || goto failed
echo [2/6] Checking completed input artifacts...
if not exist "configs\selection_v1.json" goto missing_input
if not exist "configs\baseline_v1.json" goto missing_input
if not exist "configs\walk_forward_v1.json" goto missing_input
if not exist "configs\distribution_fit_v2.json" goto missing_input
if not exist "outputs\data_v1\manifest.json" goto missing_input
if not exist "outputs\data_v1\samples_1m.csv" goto missing_input
if not exist "outputs\data_v1\samples_5m.csv" goto missing_input
if not exist "outputs\baseline_v1\1m\latest.json" goto missing_input
if not exist "outputs\baseline_v1\5m\latest.json" goto missing_input
if not exist "outputs\distribution_wf_v1\1m\latest.json" goto missing_input
if not exist "outputs\distribution_wf_v1\5m\latest.json" goto missing_input
if not exist "outputs\baseline_v1\1m\metrics.json" goto missing_input
if not exist "outputs\baseline_v1\5m\metrics.json" goto missing_input
if not exist "outputs\distribution_wf_v1\1m\metrics.json" goto missing_input
if not exist "outputs\distribution_wf_v1\5m\metrics.json" goto missing_input
echo [3/6] Validating config, source runs and selection checkpoints...
python -m distributional_bands.selection --timeframe 1m --sample "outputs\data_v1\samples_1m.csv" --baseline-dir "outputs\baseline_v1\1m" --wf-dir "outputs\distribution_wf_v1\1m" --output-dir "outputs\selection_v1\1m" --check-only
if errorlevel 1 goto failed
python -m distributional_bands.selection --timeframe 5m --sample "outputs\data_v1\samples_5m.csv" --baseline-dir "outputs\baseline_v1\5m" --wf-dir "outputs\distribution_wf_v1\5m" --output-dir "outputs\selection_v1\5m" --check-only
if errorlevel 1 goto failed
if /i "%~1"=="check" goto checked
echo [4/6] Starting or resuming 1m diagnostics...
python -m distributional_bands.selection --timeframe 1m --sample "outputs\data_v1\samples_1m.csv" --baseline-dir "outputs\baseline_v1\1m" --wf-dir "outputs\distribution_wf_v1\1m" --output-dir "outputs\selection_v1\1m"
if errorlevel 1 goto failed
echo [5/6] Starting or resuming 5m diagnostics...
python -m distributional_bands.selection --timeframe 5m --sample "outputs\data_v1\samples_5m.csv" --baseline-dir "outputs\baseline_v1\5m" --wf-dir "outputs\distribution_wf_v1\5m" --output-dir "outputs\selection_v1\5m"
if errorlevel 1 goto failed
echo [6/6] Complete. Return outputs\selection_v1 for review before locking a model.
exit /b 0
:checked
echo Preflight complete. No diagnostics job was started.
exit /b 0
:missing_input
echo ERROR: Missing DATA-V1, baseline or distribution walk-forward artifacts.
goto failed
:failed
echo ERROR: Selection diagnostics stopped. Existing outputs\selection_v1 checkpoints are preserved.
echo Fix the error and rerun the same .bat. Do not delete checkpoints.
pause
exit /b 1
