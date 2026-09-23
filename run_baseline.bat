@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
echo [1/5] Checking Python and dependencies...
python -c "import sys, numpy, pandas; print('Python', sys.version.split()[0], 'NumPy', numpy.__version__, 'pandas', pandas.__version__); sys.exit(0 if sys.version_info >= (3, 11) else 1)" || goto failed
python -c "import shutil, sys; free=shutil.disk_usage('.').free; print('Free disk GiB:', round(free / 1024**3, 2)); sys.exit(0 if free >= 2 * 1024**3 else 1)" || goto failed
echo [2/5] Checking config and DATA-V1 artifacts...
if not exist "configs\baseline_v1.json" goto missing_input
if not exist "outputs\data_v1\manifest.json" goto missing_input
if not exist "outputs\data_v1\samples_1m.csv" goto missing_input
if not exist "outputs\data_v1\samples_5m.csv" goto missing_input
echo [3/5] Running/resuming 1m development baseline...
python -m distributional_bands.baseline --timeframe 1m --config "configs\baseline_v1.json" --input "outputs\data_v1\samples_1m.csv" --data-manifest "outputs\data_v1\manifest.json" --output-dir "outputs\baseline_v1\1m"
if errorlevel 1 goto failed
echo [4/5] Running/resuming 5m development baseline...
python -m distributional_bands.baseline --timeframe 5m --config "configs\baseline_v1.json" --input "outputs\data_v1\samples_5m.csv" --data-manifest "outputs\data_v1\manifest.json" --output-dir "outputs\baseline_v1\5m"
if errorlevel 1 goto failed
echo [5/5] Completed. See outputs\baseline_v1\*
exit /b 0
:missing_input
echo ERROR: Config or prepared DATA-V1 artifacts are missing. Run run_prepare.bat on this machine first.
goto failed
:failed
echo Baseline run stopped. Existing checkpoints and predictions remain available for resume.
pause
exit /b 1
