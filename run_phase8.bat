@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
echo [1/7] Checking Python, dependencies and free disk space...
python -c "import sys, numpy, pandas, scipy; print('Python', sys.version.split()[0], 'NumPy', numpy.__version__, 'pandas', pandas.__version__, 'SciPy', scipy.__version__); sys.exit(0 if sys.version_info >= (3, 11) else 1)" || goto failed
python -c "import shutil, sys; free=shutil.disk_usage('.').free; print('Free disk GiB:', round(free / 1024**3, 2)); sys.exit(0 if free >= 4 * 1024**3 else 1)" || goto failed
echo [2/7] Checking locked config, data and completed development artifacts...
if not exist "configs\phase8_v1.json" goto missing_input
if not exist "outputs\data_v1\manifest.json" goto missing_input
if not exist "outputs\data_v1\samples_1m.csv" goto missing_input
if not exist "outputs\data_v1\samples_5m.csv" goto missing_input
if not exist "outputs\phase7a_v1\1m\report.json" goto missing_input
if not exist "outputs\phase7a_v1\5m\report.json" goto missing_input
if not exist "outputs\phase7b_v1\1m\report.json" goto missing_input
if not exist "outputs\phase7b_v1\5m\report.json" goto missing_input
echo [3/7] Checking final-test checkpoints and lineage without scoring...
python -m distributional_bands.phase8 --timeframe 1m --input "outputs\data_v1\samples_1m.csv" --phase7a-dir "outputs\phase7a_v1\1m\hl30" --phase7a-report "outputs\phase7a_v1\1m\report.json" --phase7b-dir "outputs\phase7b_v1\1m" --phase7b-report "outputs\phase7b_v1\1m\report.json" --output-dir "outputs\phase8_v1\1m" --check-only
if errorlevel 1 goto failed
python -m distributional_bands.phase8 --timeframe 5m --input "outputs\data_v1\samples_5m.csv" --phase7a-dir "outputs\phase7a_v1\5m\hl30" --phase7a-report "outputs\phase7a_v1\5m\report.json" --phase7b-dir "outputs\phase7b_v1\5m" --phase7b-report "outputs\phase7b_v1\5m\report.json" --output-dir "outputs\phase8_v1\5m" --check-only
if errorlevel 1 goto failed
if /i "%~1"=="check" goto checked
echo [4/7] Running or resuming frozen 1m final test...
python -m distributional_bands.phase8 --timeframe 1m --input "outputs\data_v1\samples_1m.csv" --phase7a-dir "outputs\phase7a_v1\1m\hl30" --phase7a-report "outputs\phase7a_v1\1m\report.json" --phase7b-dir "outputs\phase7b_v1\1m" --phase7b-report "outputs\phase7b_v1\1m\report.json" --output-dir "outputs\phase8_v1\1m"
if errorlevel 1 goto failed
echo [5/7] Running or resuming frozen 5m final test...
python -m distributional_bands.phase8 --timeframe 5m --input "outputs\data_v1\samples_5m.csv" --phase7a-dir "outputs\phase7a_v1\5m\hl30" --phase7a-report "outputs\phase7a_v1\5m\report.json" --phase7b-dir "outputs\phase7b_v1\5m" --phase7b-report "outputs\phase7b_v1\5m\report.json" --output-dir "outputs\phase8_v1\5m"
if errorlevel 1 goto failed
echo [6/7] Building frozen final-test reports...
python -m distributional_bands.phase8_report --timeframe 1m --input "outputs\data_v1\samples_1m.csv" --phase7a-dir "outputs\phase7a_v1\1m\hl30" --phase7a-report "outputs\phase7a_v1\1m\report.json" --phase7b-dir "outputs\phase7b_v1\1m" --phase7b-report "outputs\phase7b_v1\1m\report.json" --output-dir "outputs\phase8_v1\1m"
if errorlevel 1 goto failed
python -m distributional_bands.phase8_report --timeframe 5m --input "outputs\data_v1\samples_5m.csv" --phase7a-dir "outputs\phase7a_v1\5m\hl30" --phase7a-report "outputs\phase7a_v1\5m\report.json" --phase7b-dir "outputs\phase7b_v1\5m" --phase7b-report "outputs\phase7b_v1\5m\report.json" --output-dir "outputs\phase8_v1\5m"
if errorlevel 1 goto failed
echo [7/7] Complete. Return outputs\phase8_v1 for verification. Do not retune on final outcomes.
exit /b 0
:checked
echo Preflight complete. No final-test prediction was generated.
exit /b 0
:missing_input
echo ERROR: Missing locked config, data or completed Phase 7A/7B artifacts.
goto failed
:failed
echo ERROR: Phase 8 stopped. Keep outputs\phase8_v1 and rerun this same .bat after diagnosis.
pause
exit /b 1
