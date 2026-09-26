@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
set "OMP_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "RUN=python -m distributional_bands.win_retry"
echo [1/7] Checking environment and disk space...
python -c "import sys, numpy, pandas, scipy; print('Python', sys.version.split()[0], 'NumPy', numpy.__version__, 'pandas', pandas.__version__, 'SciPy', scipy.__version__); sys.exit(0 if sys.version_info >= (3, 11) else 1)" || goto failed
python -c "import shutil, sys; free=shutil.disk_usage('.').free; print('Free disk GiB:', round(free / 1024**3, 2)); sys.exit(0 if free >= 6 * 1024**3 else 1)" || goto failed
echo [2/7] Checking configs and completed upstream artifacts...
for %%F in (phase9c_v1 phase9d_v1 phase9e_v1 phase9f_v1 distribution_fit_v2) do if not exist "configs\%%F.json" goto missing_input
for %%T in (1m 5m) do (
  if not exist "outputs\data_v1\samples_%%T.csv" goto missing_input
  if not exist "outputs\phase8_v1\%%T\latest.json" goto missing_input
  if not exist "outputs\phase9d_v1\%%T\report.json" goto missing_input
)
echo [3/7] Verifying Phase 9D sources and any existing Phase 9C checkpoints (read-only)...
for %%T in (1m 5m) do (
  for %%H in (30 60) do (
    %RUN% distributional_bands.phase9d --timeframe %%T --half-life %%H --input "outputs\data_v1\samples_%%T.csv" --output-dir "outputs\phase9d_v1\%%T\hl%%H" --check-only || goto failed
  )
  %RUN% distributional_bands.phase9d_report --timeframe %%T --input "outputs\data_v1\samples_%%T.csv" --check-only || goto failed
  %RUN% distributional_bands.phase9c --timeframe %%T --input "outputs\data_v1\samples_%%T.csv" --output-dir "outputs\phase9c_v1\%%T" --check-only || goto failed
)
if /i "%~1"=="check" goto checked
echo [4/7] Phase 9F: scale-normalisation sensitivity (minutes)...
for %%T in (5m 1m) do (
  %RUN% distributional_bands.phase9f --timeframe %%T --output-dir "outputs\phase9f_v1\%%T" || goto failed
)
echo [5/7] Phase 9C: 2025-2026 descriptive nine-family run (about 1-1.5 hours)...
for %%T in (5m 1m) do (
  %RUN% distributional_bands.phase9c --timeframe %%T --input "outputs\data_v1\samples_%%T.csv" --output-dir "outputs\phase9c_v1\%%T" || goto failed
  %RUN% distributional_bands.phase9c --timeframe %%T --input "outputs\data_v1\samples_%%T.csv" --output-dir "outputs\phase9c_v1\%%T" --report || goto failed
)
echo [6/7] Phase 9E: Monte Carlo study, parallel workers (about 5-7 hours)...
for %%T in (5m 1m) do (
  %RUN% distributional_bands.phase9e --timeframe %%T --stage setup || goto failed
  %RUN% distributional_bands.phase9e --timeframe %%T --stage run || goto failed
  %RUN% distributional_bands.phase9e --timeframe %%T --stage report || goto failed
)
echo [7/7] Complete. Return outputs\phase9f_v1, outputs\phase9c_v1 and outputs\phase9e_v1 for verification.
exit /b 0
:checked
echo Preflight complete. No Phase 9C, 9E or 9F computation was started.
exit /b 0
:missing_input
echo ERROR: Missing config, DATA-V1, Phase 8 or completed Phase 9D artifacts.
goto failed
:failed
echo ERROR: Phase 9 run stopped. All checkpoints and upstream artifacts remain available.
echo Fix the error and rerun this same .bat; completed steps are verified and skipped.
pause
exit /b 1
