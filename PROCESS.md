# PROCESS.md

> **Operational memory, engineering protocol, and research safety standard for AI coding agents**
>
> File này là nguồn ngữ cảnh vận hành chung cho Codex, Claude Code và các AI coding agent khác khi làm việc với repository.
>
> Mục tiêu:
>
> - Giúp AI hiểu nhanh project và trạng thái hiện tại.
> - Giữ continuity giữa nhiều session và nhiều AI khác nhau.
> - Không lặp lại lỗi đã từng gặp.
> - Không tự ý sửa code trước khi thảo luận.
> - Giữ phạm vi implementation đúng với phần đã được approve.
> - Không mất kết quả training/backtest/optimization.
> - Đảm bảo research quant/ML có thể tái tạo.
> - Ngăn look-ahead bias, leakage, cherry-picking và overfitting.
> - Có thể truy ngược một kết quả về code, data, config và experiment đã tạo ra nó.
>
> **Mọi AI phải đọc file này trước khi bắt đầu một task mới.**

---

# 0. AI ENTRY POINT

`PROCESS.md` phải nằm tại root repository:

```text
<repository-root>/PROCESS.md
```

Các instruction file của từng agent nên trỏ về file này.

Ví dụ `CLAUDE.md`:

```text
Before doing any work, read PROCESS.md and follow it.
```

Ví dụ `AGENTS.md`:

```text
Before doing any work, read PROCESS.md and follow it.
```

Instruction cho Codex:

```text
PROCESS.md is the operational source of truth for this repository.
Read it before starting any task.
```

---

# 1. PRIORITY OF INSTRUCTIONS

Thứ tự ưu tiên:

1. Yêu cầu trực tiếp mới nhất của người dùng.
2. `PROCESS.md`.
3. Documentation và conventions chính thức của project.
4. Architecture/code hiện tại.
5. Giả định của AI.

AI không được tự thay thế yêu cầu của người dùng bằng một phương án mà AI nghĩ là tốt hơn.

Nếu AI thấy có giải pháp tốt hơn:

```text
Explain
→ Compare
→ Discuss
→ Get approval
→ Implement
```

---

# 2. GOLDEN WORKFLOW

Quy trình mặc định:

```text
INSPECT
   ↓
UNDERSTAND
   ↓
DISCUSS
   ↓
APPROVAL
   ↓
SCOPE LOCK
   ↓
IMPLEMENT
   ↓
TEST
   ↓
CHECKPOINT
   ↓
VERIFY
   ↓
REPORT
   ↓
RECORD
```

Không được bỏ qua:

```text
DISCUSS
APPROVAL
```

trước khi sửa code.

---

# 3. INSPECTION ≠ IMPLEMENTATION

## 3.1 Inspection / Investigation

AI được phép chủ động thực hiện trước khi hỏi người dùng:

- Đọc source code.
- Search repository.
- Đọc documentation.
- Đọc `PROCESS.md`.
- Đọc config.
- Kiểm tra cấu trúc thư mục.
- Kiểm tra schema.
- Xem `git status`.
- Xem `git diff`.
- Xem git log.
- Kiểm tra dependency.
- Đọc logs.
- Kiểm tra checkpoint.
- Kiểm tra experiment đang dang dở.
- Chạy existing tests.
- Chạy lint.
- Chạy type check.
- Chạy static analysis.
- Reproduce bug trong môi trường an toàn.
- Chạy diagnostic không gây side effect.

Mục đích:

> AI phải hiểu project đủ tốt trước khi đề xuất giải pháp.

Không yêu cầu AI hỏi người dùng trước mỗi thao tác đọc.

---

## 3.2 Implementation

Implementation bao gồm:

- Sửa source code.
- Tạo source code.
- Refactor.
- Xóa code.
- Rename/move file.
- Sửa config.
- Thêm/xóa dependency.
- Sửa database schema.
- Viết migration.
- Viết `.bat`.
- Sửa CI/CD.
- Thay architecture.
- Thay data processing behavior.
- Thay model behavior.

Implementation chỉ được bắt đầu sau approval.

---

# 4. PROJECT SNAPSHOT

## Project

```text
Name: Distributional Bollinger Bands for VN30F1M
Purpose:
Identify which distribution of the standardized residual z_t gives the best out-of-sample forecasts of next-bar VN30F1M returns on 1m and 5m data. Pure distributional forecasting research; trading signals/backtests are out of scope (DEC-006).
Repository:
https://github.com/namngyh/Distributional-Bollinger-Bands-for-VN30F1M.git (origin/main)
Primary language:
Python
Framework:
pandas / NumPy data pipeline, SciPy distribution fitting
Database:
None
Package manager:
pyproject.toml / pip
Test framework:
unittest
```

## Important directories

| Path | Purpose |
|---|---|
| `src/distributional_bands/` | Data preparation, baseline and distribution fitting |
| `configs/` | Versioned data, baseline and fit policies |
| `docs/` | Research plan and data contract |
| `tests/` | Synthetic data validation |
| `outputs/` | Generated datasets and manifest; never overwrite |

## Entry points

```text
Application: None
API: None
Worker: None
CLI: python -m distributional_bands.cli audit|prepare
Baseline: python -m distributional_bands.baseline --timeframe 1m|5m ...; run_baseline.bat for full development run
Training: `distributional_bands.distributions.fit_distribution`; completed development walk-forward via `distributional_bands.walk_forward` and `run_distribution_walkforward.bat`
Analysis: `distributional_bands.selection` via `run_selection.bat`; Phase 7A/7B and frozen Phase 8 via `phase8`, `phase8_report`, `run_phase8.bat` (all user-run verified)
Backtest: Out of scope (DEC-006)
Tests: python -m unittest discover -s tests -v
Configuration: configs/data_v1.json; configs/baseline_v1.json; configs/distribution_fit_v2.json; configs/walk_forward_v1.json; configs/selection_v1.json; configs/phase7a_v1.json; configs/phase7b_v1.json; configs/phase8_v1.json
Checkpoints: BASELINE-V1, DISTRIBUTION-WF-V1, SELECTION-V1, PHASE7A-V1, PHASE7B-V1 and PHASE8-V1 complete
Experiments: Phase 3/5/6/7A/7B/8 user-run verified; PHASE9A-V1 (z_t diagnostics, exploratory, AI-run read-only) complete; 9B–9F proposed; Phase 10 not started
Outputs: outputs/data_v1/, baseline_v1/, distribution_wf_v1/, selection_v1/, phase7a_v1/, phase7b_v1/, phase8_v1/ verified; outputs/phase9a_v1/ (report.json + figure CSVs, copies in Bao_cao/du_lieu/)
Logs: CLI stdout, run_manifest.json, metrics.json after completion
```

---

# 5. CURRENT STATUS

## Current objective

```text
Find the distribution of z_t with the best out-of-sample forecast quality for 1m/5m VN30F1M returns. No trading research (DEC-006).
```

## Current task

```text
Phase 9A z_t diagnostics complete (2026-09-25). Next: user decides on 9B–9F; recommended 9D (past-only intraday-seasonal sigma) before 9B.
```

## Current state

Allowed states:

```text
NOT_STARTED
INVESTIGATING
DISCUSSING
APPROVED
IMPLEMENTING
TESTING
RUNNING
BLOCKED
DONE
```

Current:

```text
DONE — Phase 8 verified; DEC-006/007 documented; PHASE9A-V1 implemented, tested and run (read-only, development only). 9B–9F DISCUSSING; no new model lock.
```

## Last known working state

```text
Branch: main (tracks origin/main)
Commit: See `git log -1`; original remote base is ca2d150.
Command: run_phase8.bat check; phase8_report --check-only (1m/5m); read-only review of final reports and hashes.
Result: Phase 8 complete 381/381 days per timeframe; 1m 90,478 bars, 5m 17,474 bars and 76/76 fits successful. Both reports recomputed exactly. Locked 5m model had 0.2253% worse final pinball than predeclared Empirical control.
Date: 2026-09-23
```

## Current modifications

```text
2026-09-25: documentation-only scope update (DEC-006) in README.md, docs/research_plan.md, docs/phase8_final_assessment.md, docs/data_contract.md, PROCESS.md. Phase 3–8 code/config/checkpoints/predictions/reports untouched.
```

## Blockers

```text
User confirmed timestamp labels are bar starts. Source timezone and contract rollover rule remain unverified; DATA-V1 never builds targets across sessions. Historical DATA-V1 config/manifest text still says timestamp unverified and must not be edited in place because artifact hashes depend on it.
```

---

# 6. FACTS / ASSUMPTIONS / UNKNOWNS

Trước một thay đổi quan trọng, AI nên phân biệt:

```text
Confirmed:
- ...

Assumptions:
- ...

Unknown:
- ...

Needs user confirmation:
- ...
```

Không được biến assumption thành fact.

Không implement dựa trên một assumption có thể thay đổi behavior quan trọng mà chưa xác minh hoặc thảo luận.

---

# 7. BEFORE CODING GATE

Trước khi viết code, AI phải trình bày:

## Understanding

```text
AI hiểu yêu cầu là gì?
```

## Current implementation

```text
Code hiện tại hoạt động như thế nào?
```

## Findings

```text
Những gì đã phát hiện sau khi inspect repository.
```

Nếu là bug:

```text
Possible root cause:
Confirmed root cause:
```

Nếu là feature:

```text
Relevant modules:
Relevant architecture:
```

## Proposed solution

```text
Giải pháp dự kiến.
```

## Files expected to change

```text
path/to/file_1
path/to/file_2
```

## Risks

```text
[ ] API impact
[ ] Database impact
[ ] Breaking changes
[ ] Performance impact
[ ] Dependency changes
[ ] Migration
[ ] Data impact
[ ] Checkpoint compatibility
[ ] Backward compatibility
[ ] Quant/model impact
```

## Validation plan

```text
[ ] Unit tests
[ ] Integration tests
[ ] Lint
[ ] Type check
[ ] Build
[ ] Manual verification
[ ] Backtest
[ ] Benchmark
[ ] Save/load checkpoint test
[ ] Resume checkpoint test
```

Sau đó:

> **STOP AND WAIT FOR USER APPROVAL.**

Một cuộc thảo luận chưa kết thúc không được xem là approval.

---

# 8. CHANGE SCOPE LOCK

Sau khi được approve, phạm vi implementation phải được khóa.

Template:

```text
Approved scope:

Modify:
- ...

Create:
- ...

Delete:
- ...

Out of scope:
- ...
```

Ví dụ:

```text
Approved scope:

Modify:
- src/model.py
- tests/test_model.py

Create:
- run_training.bat

Out of scope:
- Database schema
- API contract
- UI
- Dependency upgrades
```

AI không được tự mở rộng scope.

Nếu cần sửa ngoài scope:

```text
STOP
→ Explain
→ Update scope
→ Get approval
```

---

# 9. IMPLEMENTATION RULES

Sau approval:

1. Ưu tiên minimal diff.
2. Chỉ sửa phần liên quan.
3. Không refactor unrelated code.
4. Không tự đổi architecture.
5. Không thêm dependency nếu không cần thiết.
6. Không xóa code chỉ vì AI nghĩ là thừa.
7. Không overwrite uncommitted work.
8. Không sửa technical debt ngoài scope.
9. Không thay behavior âm thầm.
10. Không kết hợp nhiều vấn đề không liên quan vào cùng task.

Nếu phát hiện thông tin mới làm proposal không còn đúng:

```text
STOP
→ Report finding
→ Update proposal
→ Discuss
→ Approval
```

---

# 10. GIT SAFETY PROTOCOL

Trước khi sửa:

```bash
git status
```

Nếu phù hợp:

```bash
git diff
```

AI phải phân biệt:

```text
Pre-existing user changes
vs
Changes made by AI
```

Không được claim toàn bộ diff là do AI tạo.

Không tự sử dụng:

```bash
git reset --hard
git clean -fd
git checkout -- .
```

Không force push nếu chưa có approval rõ ràng.

Uncommitted changes luôn được coi là có giá trị cho đến khi xác minh ngược lại.

---

# 11. ROLLBACK PLAN

Đối với thay đổi có mức rủi ro từ MEDIUM trở lên, phải xác định rollback plan.

Template:

```text
Rollback plan:

Previous commit:
Previous config:
Previous checkpoint:
Previous artifact:
Database rollback:
Other:
```

Nếu rollback không đơn giản, phải nói rõ trước khi triển khai.

---

# 12. TESTING PROTOCOL

AI được phép tự chạy test an toàn:

```text
Unit tests
Integration tests
Build
Lint
Type checking
Static analysis
Benchmark
Bug reproduction
Mock API tests
Local isolated DB tests
Checkpoint tests
Resume tests
```

Chỉ tự chạy khi:

- Không tác động production.
- Không sửa dữ liệu thật.
- Không deploy.
- Không gửi transaction thật.
- Không gửi email/message thật.
- Không gọi live trading system.

Báo cáo:

```text
Command:
Passed:
Failed:
Warnings:
Relevant result:
```

Không được nói:

```text
Tests pass.
```

nếu chưa thực sự chạy.

---

# 13. VERIFICATION LEVELS

Không dùng từ "DONE" mơ hồ.

Phân biệt:

```text
IMPLEMENTED
TESTED
VERIFIED
USER-RUN VERIFIED
```

Ví dụ:

```text
Implementation: DONE
Unit tests: PASS
Integration tests: PASS
Local validation: PASS
Real training run: NOT VERIFIED
User-run validation: NOT VERIFIED
```

AI không được nâng trạng thái lên `VERIFIED` nếu bằng chứng chưa đủ.

---

# 14. REAL RUN PROTOCOL

## Execution rule agreed on 2026-09-23

- AI chạy trực tiếp các tác vụ nhẹ và an toàn: đọc/audit dữ liệu, unit/smoke tests, lint, kiểm tra schema và benchmark nhỏ. Ghi lại command và kết quả.
- Với tác vụ nặng hoặc kéo dài (full walk-forward, fit nhiều distribution/fold, optimization, full backtest, Monte Carlo lớn), AI chuẩn bị `.bat` để người dùng chạy trên máy khác. AI không tự chạy full job.
- `.bat` phải dùng đường dẫn tương đối với chính file (`%~dp0`) hoặc tham số rõ ràng; không hardcode đường dẫn máy phát triển. Script phải kiểm tra Python, dependency, input, config, dung lượng output và checkpoint trước khi chạy.
- Máy chạy khác phải tạo được environment snapshot và manifest gồm dataset/config/code hash, experiment ID, run ID, seed, thời gian chạy và output path. Không ghi đè run đã hoàn tất.
- Sau khi người dùng chuyển artifact/log từ máy chạy về, AI kiểm tra integrity và cập nhật Current Checkpoint Status, Artifact Registry và Current Task Handoff. Không tuyên bố user-run verified chỉ dựa vào việc `.bat` đã được tạo.

Phân biệt:

```text
TEST / VALIDATION
```

với:

```text
REAL RUN
```

AI được chạy validation an toàn.

Đối với real run:

- Full model training.
- Full backtest.
- Hyperparameter optimization.
- Production pipeline.
- Large Monte Carlo.
- Database migration.
- Live application.
- Live trading.

AI không tự chạy thay người dùng.

Phải tạo `.bat`.

Ví dụ:

```text
run_training.bat
resume_training.bat
run_backtest.bat
run_optimization.bat
run_pipeline.bat
run_app.bat
```

Người dùng chạy:

```powershell
.\run_training.bat
```

`.bat` phải:

- Hiển thị progress.
- Hiển thị error rõ ràng.
- Không swallow stderr.
- Có exit code.
- Có timestamp khi hữu ích.
- Dừng nếu critical step fail.
- Không tự đóng ngay khi lỗi.
- Kiểm tra checkpoint trước.
- Ưu tiên resume.

Ví dụ:

```text
[1/6] Checking environment...
[2/6] Checking configuration...
[3/6] Checking checkpoint...
[4/6] Preparing run...
[5/6] Starting...
[6/6] Finished.
```

---

# 15. CHECKPOINT PROTOCOL

Mọi tiến trình dài hoặc tốn compute phải hỗ trợ checkpoint.

Checkpoint phải được lưu **trong khi job chạy**, ngay sau từng đơn vị công việc hoàn tất có thể resume (ví dụ fold, trial, cửa sổ walk-forward hoặc stage). Manifest tiến độ phải được cập nhật cùng checkpoint để có thể tiếp tục trên cùng máy hoặc chuyển artifact sang máy khác.

Áp dụng đặc biệt cho:

```text
Machine learning training
Deep learning training
Hyperparameter optimization
Grid search
Bayesian optimization
Walk-forward optimization
Long backtests
Monte Carlo simulations
Large preprocessing
Feature generation
Batch jobs
Research pipelines
```

Không chấp nhận:

```text
Start
→ Run for hours
→ Save only at the end
```

---

# 16. RESUME-FIRST RULE

Trước workflow dài:

```text
[ ] Existing checkpoint checked
[ ] Experiment ID verified
[ ] Run ID verified
[ ] Config verified
[ ] Dataset verified
[ ] Architecture verified
[ ] Checkpoint integrity verified
[ ] Resume possibility determined
```

Nếu checkpoint hợp lệ:

> **RESUME BEFORE RESTART.**

Không được chạy lại từ đầu chỉ vì dễ hơn.

---

# 17. CHECKPOINT CONTENT

Checkpoint nên lưu khi phù hợp:

```text
Model state
Optimizer state
Scheduler state
Epoch
Global step
Best metric
Current metric
Training history
Hyperparameters
Configuration
Random seeds
RNG state
Mixed precision scaler
Early stopping state
Dataset version
Feature configuration
Train/validation/test periods
Git commit
Experiment ID
Run ID
Timestamp
```

Chỉ lưu weights không nhất thiết đủ để resume.

---

# 18. CHECKPOINT STRATEGY

Nên có tối thiểu:

```text
latest
best
```

`latest`:

> Resume sau interruption.

`best`:

> Model tốt nhất theo metric đã định nghĩa trước.

Không giả định:

```text
latest == best
```

---

# 19. CHECKPOINT FREQUENCY

Checkpoint theo:

```text
N epochs
N steps
N minutes
Every fold
Every trial
Every walk-forward window
Every major pipeline stage
```

Job chạy nhiều giờ không được chỉ save khi hoàn tất.

Tần suất cụ thể phải được ghi trong config trước khi chạy. Với walk-forward, tối thiểu lưu sau mỗi fold/window đã hoàn tất; nếu một fold dài, bổ sung checkpoint theo số bước hoặc thời gian. `latest` và `best` có vai trò riêng; không để checkpoint mới làm mất best trước đó.

---

# 20. SAFE CHECKPOINT WRITING

Ưu tiên atomic save:

```text
save temporary
→ verify
→ replace latest
```

Ví dụ:

```text
latest.tmp
→ latest.ckpt
```

Crash khi save không được phá checkpoint hợp lệ trước đó.

Checkpoint phải gắn với dataset hash, config hash, code version, experiment/run ID và vị trí tiến độ. Resume phải từ chối checkpoint không tương thích và không tạo trùng prediction/metric đã ghi.

---

# 21. CHECKPOINT VALIDATION

Không xem checkpoint là tốt chỉ vì file tồn tại.

Kiểm tra:

```text
[ ] File loads
[ ] Model loads
[ ] Optimizer loads
[ ] Architecture compatible
[ ] Config compatible
[ ] Dataset compatible
[ ] Epoch/step valid
[ ] No corruption
```

Workflow quan trọng phải test:

```text
save
→ terminate
→ load
→ resume
```

---

# 22. ENVIRONMENT SNAPSHOT

Với ML/quant hoặc workflow phụ thuộc môi trường, lưu:

```text
OS:
Python:
Compiler:
PyTorch:
TensorFlow:
CUDA:
cuDNN:
NumPy:
Pandas:
GPU:
GPU driver:
CPU:
Package lock/hash:
Other critical libraries:
```

Nếu environment khác giữa hai experiment:

> Không mặc định kết quả hoàn toàn comparable.

---

# 23. DATA / MODEL SAFETY PROTOCOL

Phần này bắt buộc với:

- Quant research.
- ML.
- Time-series.
- Backtesting.
- Trading strategies.
- Portfolio/risk modeling.

---

# 24. NO LOOK-AHEAD BIAS

Không sử dụng thông tin tương lai để tạo decision trong quá khứ.

Kiểm tra đặc biệt:

```text
rolling()
shift()
resample()
center=True
future labels
aggregation
normalization
indicator computation
execution price
timestamp alignment
```

Nếu signal chỉ biết sau khi candle `t` đóng:

```text
execution >= t + 1
```

trừ khi execution model được định nghĩa khác rõ ràng.

---

# 25. NO DATA LEAKAGE

Validation/test không được ảnh hưởng:

```text
Scaler
Normalizer
Feature selection
PCA
Imputation
Distribution fitting
Threshold selection
Hyperparameter tuning
Model selection
```

Sai:

```text
fit preprocessing on entire dataset
→ split
```

Đúng:

```text
split
→ fit on train
→ transform validation/test
```

---

# 26. TIME-SERIES SPLIT INTEGRITY

Không random shuffle time series nếu không có lý do hợp lệ.

Ưu tiên:

```text
TRAIN
→ VALIDATION
→ TEST
```

theo chronology.

Nếu dùng:

```text
Walk-forward
Rolling window
Expanding window
Purged CV
Embargo
```

phải ghi configuration.

---

# 27. DATA PROVENANCE / DATA CONTRACT

Mỗi dataset quan trọng phải có metadata:

```text
Dataset name:
Source:
Version:
Hash:
Rows:
Columns:
Time range:
Timezone:
Frequency:
Primary key:
Expected columns:
Dtypes:
Missing-data policy:
Duplicate policy:
Outlier policy:
Filtering rules:
Resampling rules:
```

AI không được âm thầm thay:

- Timezone.
- Frequency.
- Missing data behavior.
- Duplicate handling.
- Filter rules.
- Resampling logic.

---

# 28. DATASET IMMUTABILITY

Không âm thầm thay:

```text
Dataset
Sample period
Symbols
Frequency
Filtering
Outlier rules
Train period
Validation period
Test period
```

để tạo kết quả đẹp hơn.

Mọi thay đổi dataset phải được ghi lại.

---

# 29. EXPERIMENT CONFIGURATION

Mỗi experiment quan trọng phải ghi:

```text
Experiment ID:
Run ID:

Parent experiment:

Dataset:
Dataset version/hash:

Features:

Train period:
Validation period:
Test period:

Random seed:

Model:
Model parameters:

Optimizer:
Learning rate:

Loss:

Transaction cost:
Commission:
Slippage:
Spread:

Execution assumptions:

Initial capital:
Position sizing:
Leverage:
Margin:

Primary metric:
Secondary metrics:

Baseline:

Git commit:

Environment:

Checkpoint path:
Output path:
```

---

# 30. EXPERIMENT LINEAGE

Mỗi experiment nên có parent nếu được phát triển từ experiment trước.

Ví dụ:

```text
Experiment:
EXP-024

Parent:
EXP-017

Changed:
- Error distribution: Gaussian → Student-t
- learning_rate: 0.001 → 0.0005

Unchanged:
- Dataset
- Features
- Train period
- Test period
- Costs
- Execution rules
```

Mục tiêu:

> Biết chính xác thay đổi nào dẫn đến kết quả nào.

---

# 31. SINGLE-VARIABLE CHANGE PRINCIPLE

Nếu mục tiêu là nghiên cứu ảnh hưởng của một yếu tố:

> Giữ các yếu tố khác cố định khi có thể.

Ví dụ so sánh:

```text
EGARCH Gaussian
vs
EGARCH Student-t
```

Không đồng thời đổi:

```text
Feature set
Window
Optimizer
Dataset
Training period
Execution assumptions
```

nếu muốn xác định riêng tác động của error distribution.

---

# 32. RANDOM SEED

Nếu experiment có stochastic component:

```text
Python seed:
NumPy seed:
PyTorch seed:
CUDA seed:
Other:
```

Nếu không đảm bảo full determinism:

```text
NON-DETERMINISTIC
Reason:
```

---

# 33. BASELINE-FIRST RULE

Không tuyên bố:

```text
model improved
strategy improved
performance improved
```

nếu chưa có baseline xác định trước.

Baseline phải ghi:

```text
Baseline ID:
Model/strategy:
Dataset:
Period:
Parameters:
Costs:
Slippage:
Seed:
Metrics:
```

---

# 34. FAIR MODEL COMPARISON

Khi so sánh model/strategy, giữ cố định khi có thể:

```text
Dataset
Train period
Validation period
Test period
Features
Costs
Slippage
Execution
Capital
Risk limits
Random seeds
Evaluation metric definitions
```

Nếu có khác biệt:

> Phải báo rõ.

---

# 35. METRIC DEFINITION REGISTRY

Không chỉ ghi tên metric.

Phải định nghĩa cách tính.

Ví dụ:

## Sharpe Ratio

```text
Return type:
Frequency:
Annualization factor:
Risk-free rate:
Gross/net:
Arithmetic/log:
```

## Sortino Ratio

```text
Target return:
Downside deviation definition:
Frequency:
Annualization:
```

## Max Drawdown

```text
Equity definition:
Realized/unrealized:
Gross/net:
Intraday/end-of-bar:
```

## CAGR

```text
Start/end convention:
Calendar basis:
```

Nếu metric definition thay đổi:

> Phải coi đó là một thay đổi methodology.

---

# 36. PRIMARY METRIC / NO CHERRY-PICKING

Primary metric phải được xác định trước experiment nếu có thể.

```text
Primary metric:
Secondary metrics:
Guardrail metrics:
```

Không được:

1. Chạy experiment.
2. Xem 20 metrics.
3. Chỉ báo metric đẹp nhất.

Nếu metric khác xấu đi, phải báo.

Ví dụ:

```text
Sharpe: improved
Max Drawdown: worse
Turnover: worse
Net Profit: unchanged
```

Không được giấu các trade-off này.

---

# 37. STATISTICAL UNCERTAINTY

Không chỉ báo point estimate khi uncertainty quan trọng.

Nếu phù hợp, bổ sung:

```text
Standard error
Confidence interval
Bootstrap interval
Number of observations
Number of trades
Number of independent periods
```

Ví dụ:

```text
Sharpe = 1.4
95% bootstrap interval = [...]
Trades = ...
```

---

# 38. MODEL SELECTION SAFETY

Không chọn model dựa trực tiếp vào final test set.

Ưu tiên:

```text
TRAIN
   ↓
VALIDATION / CV
   ↓
MODEL SELECTION
   ↓
FINAL TEST
```

Final test nên được giữ ngoài quá trình model selection.

---

# 39. OVERFITTING WARNING

AI phải cảnh báo khi có:

- Quá nhiều parameters.
- Quá nhiều trials.
- Nhiều rule được chỉnh dựa trên backtest.
- Performance quá tốt bất thường.
- Ít trades.
- Parameter sensitivity cao.
- Performance tập trung trong một đoạn nhỏ.
- Test set được xem quá nhiều lần.

Nếu phù hợp, kiểm tra:

```text
Out-of-sample
Walk-forward
Bootstrap
Monte Carlo
Sensitivity analysis
Parameter stability
Multiple-testing effects
```

---

# 40. BACKTEST SAFETY

Backtest phải ghi:

```text
Instrument:
Data period:
Frequency:

Signal timing:
Execution timing:

Fees:
Commission:
Spread:
Slippage:

Position sizing:
Leverage:
Margin:

Initial capital:

Missing data handling:
Corporate actions:
Execution assumptions:
```

Không mặc định:

```text
fees = 0
slippage = 0
```

nếu mục tiêu là đánh giá khả năng triển khai thực tế.

---

# 41. ARTIFACT REGISTRY

Mỗi run quan trọng nên ghi output chính thức.

```text
Experiment ID: BASELINE-V1
Run IDs: BASELINE-V1-1m; BASELINE-V1-5m
Checkpoint: outputs/baseline_v1/<timeframe>/latest.json (complete, 1790/1790 days, last day 2024-12-31)
Metrics: outputs/baseline_v1/<timeframe>/metrics.json
Predictions: outputs/baseline_v1/<timeframe>/predictions/ (748 daily CSV files per timeframe)
Manifest: outputs/baseline_v1/<timeframe>/run_manifest.json
Config: configs/baseline_v1.json, SHA-256 5fd89c4331c8807bedea6c276c6e3c11a6770229d5783ca0c7a32365ffcfcc6d
Dataset: outputs/data_v1/manifest.json, SHA-256 374fa77f8c5eb4db2caa12a88f7e090b200ff045da2f680b7d0c57fecd3c1bdd
Validation: completed-run runner verified checkpoint and all artifact hashes for 1m and 5m on 2026-09-23.
Git/source lineage: See each run_manifest.json; source file hashes are recorded there. The raw data and outputs are ignored by Git.
```

```text
Experiment ID: DISTRIBUTION-WF-V1
Run IDs: DISTRIBUTION-WF-V1-1m; DISTRIBUTION-WF-V1-5m
Checkpoint: outputs/distribution_wf_v1/<timeframe>/latest.json (complete, 748/748 days, last day 2024-12-31)
Metrics: outputs/distribution_wf_v1/<timeframe>/metrics.json
Fit history: outputs/distribution_wf_v1/<timeframe>/fit_history.json
Predictions: outputs/distribution_wf_v1/<timeframe>/predictions/ (748 daily CSV per timeframe)
Manifest: outputs/distribution_wf_v1/<timeframe>/run_manifest.json
Config: configs/distribution_fit_v2.json; configs/walk_forward_v1.json
Validation: completed-run runner verified signatures, all prediction hashes, metrics and fit history for both timeframes on 2026-09-23. Nine candidates each had 150 fit attempts and zero failures per timeframe.
Selection: no winner locked; paired pinball ranking is descriptive only.
```

```text
Experiment ID: SELECTION-V1
Run IDs: SELECTION-V1-1m; SELECTION-V1-5m
Checkpoint: outputs/selection_v1/<timeframe>/latest.json (complete 748/748)
Daily analyses: outputs/selection_v1/<timeframe>/daily/ (748 daily JSON each)
Report: outputs/selection_v1/<timeframe>/report.json (complete)
Config: configs/selection_v1.json
Validation: run_selection.bat check verified daily hashes for 1m/5m; recomputed reports exactly matched saved report. Paired bars: 177939 (1m), 34344 (5m). Shortlist not winner lock: Empirical EWMA reference, Mixture 3 1m, Mixture 2 5m; user approved Phase 7A sensitivity.
```

```text
Experiment ID: PHASE7A-V1
Run IDs: PHASE7A-V1-<timeframe>-HL30 / HL120
Checkpoint: outputs/phase7a_v1/<timeframe>/hl<half_life>/latest.json; all four 1m/5m HL30/HL120 complete 748/748
Predictions: outputs/phase7a_v1/<timeframe>/hl<half_life>/predictions/ (all checkpoint hashes verified)
Daily diagnostics: outputs/phase7a_v1/<timeframe>/hl<half_life>/daily/ (all report inputs verified)
Reports: outputs/phase7a_v1/<timeframe>/report.json (both complete and recomputation matched)
Config: configs/phase7a_v1.json; fit policy configs/distribution_fit_v2.json
Anchor: verified SELECTION-V1 / DISTRIBUTION-WF-V1 / BASELINE-V1 HL60; not rerun.
PIT migration: each migrated 1m trial retains old metadata in pit_boundary_migration_v1/ and lineage in pit_boundary_migration_v1.json; no prediction/daily bytes changed.
Validation: run_phase7a.bat check and phase7a_report --check-only verified all four 748/748 trials, each with 150 fit attempts/0 failures, both reports; development 2022–2024 only. No model winner locked.
```

```text
Experiment ID: PHASE7B-V1
Run IDs: PHASE7B-V1-1m; PHASE7B-V1-5m
Checkpoint: outputs/phase7b_v1/<timeframe>/latest.json (user-run complete: 748/748 both)
Raw past PIT: outputs/phase7b_v1/<timeframe>/pits/<day>.npy
Calibrated predictions: outputs/phase7b_v1/<timeframe>/predictions/<day>.csv (after 60 warmup days)
Daily diagnostics: outputs/phase7b_v1/<timeframe>/daily/<day>.json
Reports: outputs/phase7b_v1/<timeframe>/report.json (both recomputed and verified; 688 scored days each)
Config: configs/phase7b_v1.json; source completed Phase 7A HL30 and report per timeframe
Validation: run_phase7b.bat check and both phase7b_report --check-only passed on completed user-run artifacts. Final test remained untouched at model lock.
```

```text
Experiment ID: PHASE8-V1
Run IDs: PHASE8-V1-1m; PHASE8-V1-5m
Locked models: 1m Empirical EWMA HL30; 5m Normal Mixture 2 HL30 with expanding past-only PIT calibration
Checkpoint: outputs/phase8_v1/<timeframe>/latest.json (user-run complete: 381/381 both)
Predictions: outputs/phase8_v1/<timeframe>/predictions/<day>.csv
Daily diagnostics: outputs/phase8_v1/<timeframe>/daily/<day>.json
5m final PIT: outputs/phase8_v1/5m/pits/<day>.npy
Reports: outputs/phase8_v1/<timeframe>/report.json (both recomputed and verified)
Config: configs/phase8_v1.json; frozen hashes of verified Phase 7B reports
Validation: run_phase8.bat check passed 381/381 days each; both phase8_report --check-only passed. 1m: 90,478 bars, no fits; 5m: 17,474 bars, 76 fits, zero failures. See docs/phase8_final_assessment.md for immutable result and report/checkpoint hashes.
```

```text
Experiment ID:
Run ID:

Model:
Checkpoint:
Metrics:
Predictions:
Backtest result:
Charts:
Logs:
Config:
Dataset snapshot:
Other outputs:
```

Mỗi artifact nên truy ngược được về:

```text
experiment_id
run_id
git_commit
dataset_version
config
```

Không để xảy ra:

> "Không biết file này được sinh từ model nào."

---

# 42. RESULT DIRECTORY CONVENTION

Khuyến nghị:

```text
experiments/
└── <experiment_name>/
    └── <run_id>/
        ├── config/
        ├── checkpoints/
        ├── metrics/
        ├── logs/
        ├── charts/
        ├── predictions/
        └── outputs/
```

Không đặt:

```text
final
final2
final_new
final_real
final_final
```

---

# 43. REPRODUCIBILITY COMMAND

Mỗi run quan trọng nên có một command chính thức để tái tạo.

Ví dụ:

```powershell
.\run_experiment_EXP024.bat
```

hoặc:

```bash
python train.py --config configs/EXP024.yaml
```

Command này phải được ghi cùng experiment metadata.

---

# 44. RESULT INTEGRITY RULE

Không được chỉnh thủ công:

```text
metrics
predictions
backtest results
experiment outputs
```

để làm kết quả đẹp hơn.

Nếu output sai:

```text
Fix code
→ rerun
→ generate new artifact
```

Không sửa kết quả bằng tay rồi coi là result hợp lệ.

---

# 45. NEGATIVE RESULTS ARE VALID

Một experiment không cải thiện kết quả vẫn là thông tin có giá trị.

Ví dụ:

```text
EXP-031:
Student-t did not outperform Gaussian under current setup.
```

Không tự thay configuration liên tục chỉ để cố tạo kết quả tốt hơn.

Negative result nên được lưu nếu nó giúp tránh lặp lại research không hiệu quả.

---

# 46. STOP CONDITIONS / FAIL-FAST

Workflow phải có điều kiện dừng.

Ví dụ:

```text
STOP if:
- Unexpected NaN/Inf
- Data schema mismatch
- Checkpoint cannot load
- Dataset hash changed unexpectedly
- Critical test regression
- Severe divergence
- Insufficient disk space
- Output path may overwrite another run
- Required environment missing
- Required config missing
- Data timestamps invalid
```

Không được tiếp tục chạy chỉ để "xem thử chuyện gì xảy ra" nếu có nguy cơ làm mất kết quả hoặc tạo output sai.

---

# 47. RESOURCE BUDGET

Trước experiment lớn nên xác định:

```text
Expected runtime:
Maximum acceptable runtime:

CPU:
RAM:
GPU:
VRAM:

Disk:
Maximum output size:

Number of trials:
Number of models:
Number of folds:
```

Nếu dự kiến vượt budget đáng kể:

> Thảo luận với người dùng trước.

AI không tự quyết định chạy grid search hàng chục nghìn combination nếu chưa được approve.

---

# 48. SECRETS & CREDENTIAL SAFETY

Không ghi:

```text
API keys
Passwords
Access tokens
Broker credentials
Database passwords
Private keys
```

vào:

```text
PROCESS.md
Source code
Committed config
Logs
Experiment metadata
```

Chỉ tham chiếu tên biến:

```text
BROKER_API_KEY
DATABASE_URL
OPENAI_API_KEY
```

Không in secret ra terminal/log.

---

# 49. KNOWN PITFALLS

Đây là danh sách ngắn các lỗi dễ tái phạm.

AI phải đọc mỗi session.

Ví dụ:

```text
- Timestamp is a bar-start label per user confirmation on 2026-09-23; original DATA-V1 config/manifest still records its earlier unverified state. Source timezone and rollover rule remain unverified.
- DATA-V1 intentionally excludes 11:30, 14:30, 14:45 and all cross-session targets.
- A 5m bar requires all five source minutes; partial buckets must not enter forecasts.
- GH/NIG fits can reach parameter bounds and Normal Mixture EM can be weakly identified; record convergence/bound diagnostics and never silently substitute another law.
- At extreme residuals, an EM mixture CDF can round to 1 + a few ulps because component weights sum slightly above one; guard only numerical PIT boundary error, never drop the tail observation or accept a materially invalid CDF.
- Never use future candle information in signals or fit a distribution with test data.
- Final test must remain untouched while selecting distributions and parameters.
- Check checkpoint before restarting future long walk-forward runs.
```

`Known Pitfalls` khác `Error Log`.

`Known Pitfalls`:

> Summary ngắn cần thấy ngay.

`Error Log`:

> Lịch sử chi tiết.

---

# 50. ERROR & LESSONS LOG

## ERR-001 — Strict EM tolerance exhausted bounded 5m smoke

```text
Date: 2026-09-23
Context: Phase 4A two-component Normal Mixture on 120 early 5m residuals (in-sample numerical smoke only).
Symptom: Five EM starts reached 300 iterations without meeting the initial 1e-6 relative likelihood tolerance.
Root cause: Slowly converging, weakly separated mixture on a small sample; no nonfinite values or component collapse.
Incorrect approach: Treat a valid but unfinished EM run as converged or silently substitute Normal.
Correct solution: Keep explicit failure handling and set a documented numerical tolerance of 1e-5, which converged on the bounded 5m smoke in 52 iterations. Full-window failure rates must be reported in phase 5.
Prevention rule: Preserve convergence diagnostics and do not tune this tolerance using OOS forecast scores.
Affected files: configs/distribution_fit_v1.json, src/distributional_bands/distributions.py, tests/test_distributions.py.
Checkpoint impact: None; phase 4A produced no long-run checkpoint.
Experiment impact: No OOS fit or model-selection result was generated.
Status: FIXED for bounded smoke; MONITOR in full walk-forward.
```

## ERR-002 — Phase 7A PIT just above one at an extreme 1m return

```text
Date: 2026-09-23
Context: User-run 1m-HL120 Phase 7A on 2022-11-16; checkpoint 216/748 through 2022-11-15.
Symptom: Invalid PIT for normal_mixture_3 on 20221116 after successful fit.
Root cause: Recorded return 0.0377526 / sigma 0.001978 gave z~19.09. EM weights summed to 1.000000000000004, yielding CDF 1.000000000000004; strict [0,1] comparison raised.
Incorrect approach: Delete the tail bar, rerun all fitting, suppress all invalid CDFs, or edit a checkpoint signature without verifying and backing up every artifact.
Correct solution: Tolerate only 1e-12 boundary roundoff and clip to [0,1]; reject larger/nonfinite violations. Migrate only the exact known legacy source signature after validating all checkpointed files, with original metadata backup and migration record.
Prevention rule: Test extreme residuals and interrupted metadata migration; retain orphan prediction CSV for deterministic reuse.
Affected files: phase7a.py, phase7a_migrate.py, run_phase7a.bat, test_phase7a.py, README.md.
Checkpoint impact: 1m-HL30 748 days and 1m-HL120 216 days preserved; bounded real resume advanced HL120 to 217 days. No prediction/daily bytes or fit state rewritten.
Experiment impact: Full Phase 7A comparison delayed; no winner selection or final-test impact.
Status: FIXED for the observed day; MONITOR for full user-run.
```

Template:

## ERR-XXX — Title

```text
Date:

Context:

Symptom:

Root cause:

Incorrect approach:

Correct solution:

Prevention rule:

Affected files:

Checkpoint impact:

Experiment impact:

Status:
OPEN / FIXED / MONITORING
```

Không ghi mọi typo nhỏ.

---

# 51. DECISION LOG

## DEC-001 — Light runs locally; heavy runs on another machine with resume

```text
Date: 2026-09-23
Decision: AI runs safe, light checks directly. Heavy/full experiments are delivered as portable .bat scripts for user execution on another machine, with periodic atomic checkpoints and resume-first behavior.
Reason: Preserve compute resources and prevent loss of long-running results.
Alternatives considered: Run all jobs locally; save only final outputs.
Trade-offs: Heavy results become available for verification only after the user returns artifacts/logs.
Affected modules: Future fitting, walk-forward, optimization, backtest and experiment orchestration.
Checkpoint compatibility: Future runs must bind checkpoints to dataset/config/code hashes and run ID.
Revisit conditions: User changes execution environment or explicitly authorizes a specific full run here.
Status: ACTIVE
```

## DEC-002 — Bar-start timestamps and locked OOS/final periods

```text
Date: 2026-09-23
Decision: User confirmed source timestamps label bar starts. Use 2022-01-01 through 2024-12-31 for development OOS model selection; keep 2025-01-01 through the current data end (2026-07-17) untouched for final evaluation.
Reason: Preserve causal forecast timing and prevent final-test contamination.
Alternatives considered: Rebuild DATA-V1 as end-labeled data; leave the final-test boundary provisional.
Trade-offs: Source timezone and contract rollover remain unknown; they must be revisited before interpreting trading performance or rollover-sensitive tails.
Affected modules: Research/data documentation and future phase 4–9 experiments; no change to DATA-V1 code, config, data or baseline artifacts.
Checkpoint compatibility: Existing DATA-V1 and BASELINE-V1 hashes remain unchanged. Record the user's later timestamp confirmation as an addendum rather than rewriting a hashed config/manifest.
Revisit conditions: Source documentation contradicts the timestamp confirmation, timezone/roll metadata arrives, or user explicitly changes the split.
Status: ACTIVE
```

## DEC-003 — Nine-candidate development walk-forward with explicit fit failures

```text
Date: 2026-09-23
Decision: Phase 5 uses the nine models in distribution_fit_v2.json. Each 1m/5m refit uses the preceding 60 trading days of EWMA-standardized residuals, every 5 development days. Forecasts run only 2022–2024. Failed candidate fits are recorded and skipped until the next refit; no silent fallback. Report per-model metrics plus paired metrics/ranking on bars where all candidates succeeded. No automatic winner declaration.
Reason: Preserve causal OOS evaluation, negative fit results and fair paired comparisons.
Alternatives considered: Abort the whole run at one candidate failure; silently substitute Normal; select by unequal-sample raw metrics.
Trade-offs: Some candidate windows may have missing forecasts; paired sample may shrink. GH/mixtures can require many hours of CPU time.
Affected modules: distributions.py, skewed.py, walk_forward.py, distribution_fit_v2.json, walk_forward_v1.json, run_distribution_walkforward.bat.
Checkpoint compatibility: Atomic latest.json after every fit attempt and completed day; data/config/source hashes bind resume. fit_history.json stores parameters, train windows and failures after completion.
Revisit conditions: Failure rate is material, paired sample becomes too small, or source rollover/timezone metadata changes interpretation. Any config change requires a new experiment/run path.
Status: ACTIVE
```

## DEC-004 — Phase 7A bounded volatility half-life sensitivity

```text
Date: 2026-09-23
Decision: After SELECTION-V1, retain Empirical EWMA as reference and shortlist Mixture 3 for 1m / Mixture 2 for 5m. Test only EWMA half-life 30, 60 and 120 trading minutes; retain 60-day fit window and 5-day refit schedule. Reuse verified 60m artifacts; run only new 30/120 trials. Rank by 2022-23 development OOS pinball and show 2024 as retrospective stability, not a new independent holdout. No automatic winner or final-test access.
Reason: Diagnose whether volatility responsiveness reduces tail clustering before adding a new calibration mechanism, while limiting trial count and preserving prior results.
Alternatives considered: Large joint grid of half-life, fit window and refit frequency; immediate quantile correction; refit 60m anchor unnecessarily.
Trade-offs: Phase 6 shortlist used all 2022-24, so Phase 7A inference remains exploratory despite the 2022-23 ranking / 2024 display. New mixture fits can be slow; use .bat and per-fit/day checkpoints.
Affected modules: New phase7a.py, phase7a_report.py, phase7a_v1.json, run_phase7a.bat and tests only; existing Phase 3-6 artifacts remain immutable.
Checkpoint compatibility: Trial signature includes data/config/fit policy/code hashes and exact half-life. No in-place config changes or reuse across unlike trials.
Revisit conditions: Fit failures, severe 2024 instability, persistent conditional miscalibration or new source rollover/timezone metadata. Phase 7B requires a separate proposal and approval.
Status: ACTIVE
```

## DEC-005 — Frozen 1m/5m models for one-shot final test

```text
Date: 2026-09-23
Decision: User confirmed Empirical EWMA HL30 for 1m and Normal Mixture 2 HL30 with expanding, strictly past-day PIT calibration for 5m. Continue the 5m five-trading-day refit cadence from Phase 7A; use the prior 60 trading days for each new fit and all prior available PIT for calibration. Run one frozen final evaluation from 2025-01-01 through 2026-07-17. Do not select or retune from final outcomes.
Evidence: Verified Phase 7B 748/748 days and recomputed reports on both timeframes. On paired 2022–23 bars, 1m Mixture raw pinball advantage versus Empirical–30 was only 0.023% and not robust; calibrated 1m was 0.003% worse. 5m calibrated Mixture 2 improved pinball 0.131% versus Empirical–30 with 94.928% coverage at nominal 95% (Holm p=0.023); raw 5m Mixture undercovered at 93.834%.
Reason: Prioritize OOS predictive quality and calibration while preferring simpler 1m baseline when mixture improvement is uncertain.
Alternatives considered: Raw 5m Mixture 2 (best pinball but undercoverage); 1m Mixture 3 raw/calibrated (negligible or absent score benefit); Empirical–30 for 5m (simpler but lower development pinball).
Trade-offs: 5m calibrated model is more complex and its development gain is small. 2024 was retrospective, not independent holdout; serial dependence and unknown rollover/timezone remain risks. Final test is a one-shot evaluation, not another selection set.
Affected modules: New Phase 8 config, runner, report, batch launcher, tests and documentation. Completed Phase 3–7B artifacts immutable.
Checkpoint compatibility: New PHASE8-V1 paths only; config pins verified Phase 7B report hashes and run signature binds data/config/source/upstream checkpoints. Atomic per-fit/day checkpoint and resume-first semantics.
Revisit conditions: Verified source metadata contradicts data contract, integrity check fails, or user expressly authorizes a new experiment after reporting the one-shot final outcome; never silently revise this locked result.
Status: ACTIVE
```

## DEC-006 — Scope limited to the distribution of z_t; trading research removed

```text
Date: 2026-09-25
Decision: User stated the project goal is solely to find which probability distribution of the standardized residual z_t gives the best out-of-sample forecasts of returns. Trading signals, backtests, transaction costs and entry/exit rules are out of scope. The planned "8. Trading research" row was removed from the phase table (never implemented), so phase numbers now match the implemented names (8 = Final test, 9 = z_t diagnostics/extended comparison, 10 = synthesis/reproducibility).
Reason: Research question is purely distributional forecasting quality.
Alternatives considered: Keep trading research as a later optional phase.
Trade-offs: None for completed work; Phase 0–8 were all distributional and remain valid. Phase 7B (PIT-calibrated hybrid) and Phase 8 (two locked models only) are reframed as ablation and narrow final test respectively, not as the answer to "which family".
Affected modules: Documentation only (README.md, docs/research_plan.md, docs/phase8_final_assessment.md, docs/data_contract.md, PROCESS.md). No code, config, checkpoint or output changed.
Checkpoint compatibility: Unaffected; no hashed artifact references these documents.
Revisit conditions: User explicitly re-opens trading research.
Status: ACTIVE
```

## DEC-007 — Statistical Vietnamese terminology in human-facing documents

```text
Date: 2026-09-25
Decision: User found terms such as "pinball" and "DGP" hard to follow. Human-facing documents (README.md, docs/*.md, Bao_cao/*.tex) use standard statistical Vietnamese terms defined in docs/thuat_ngu.md, e.g. pinball loss -> "tổn thất phân vị", coverage -> "tỷ lệ bao phủ", band -> "khoảng dự báo", DGP -> "phân phối sinh mẫu", development -> "tập xác thực", final test -> "tập kiểm thử cuối", walk-forward -> "đánh giá cửa sổ trượt", Empirical EWMA -> "phân phối thực nghiệm".
Reason: The research audience reads from a statistics background.
Alternatives considered: Rename code identifiers/JSON keys too.
Trade-offs: Code, configs, JSON keys, file names, experiment IDs and this operating log stay in their original English names because checkpoints/reports are hash-bound; docs/thuat_ngu.md maps each term to its code name.
Affected modules: Documentation only.
Checkpoint compatibility: Unaffected.
Revisit conditions: User requests different wording.
Status: ACTIVE
```

Template:

## DEC-XXX — Title

```text
Date:

Decision:

Reason:

Alternatives considered:

Trade-offs:

Affected modules:

Checkpoint compatibility:

Revisit conditions:

Status:
ACTIVE / SUPERSEDED / DEPRECATED
```

Ví dụ:

```text
Revisit when:
- Dataset > 100M rows
- Concurrent workers > 4
- Production deployment begins
```

Nếu bị thay thế:

```text
Superseded by: DEC-XXX
```

---

# 52. PROGRESS LOG

Chỉ lưu milestone có ý nghĩa.

## 2026-09-23 — Phase 0–2 foundation

```text
Status: TESTED (data source timing and roll rule remain unverified)
Changes: Research plan, DATA-V1 contract, CLI, 1m/5m sample preparation, tests.
Files changed: README.md, PROCESS.md, docs/, configs/, src/, tests/, pyproject.toml, .gitignore, run_prepare.bat.
Validation: Synthetic unit tests and read-only audit of ohlc_export.csv.
Experiment ID: None; no model fit or backtest has run.
Latest checkpoint: N/A
Best checkpoint: N/A
Artifacts: User-generated outputs/data_v1/ exists; raw and both output SHA-256 hashes match its manifest. These files are ignored by Git.
Remaining: Verify timestamp and rollover, then discuss phase 3 baseline.
```

## 2026-09-23 — Connect Git repository

```text
Status: DONE; main tracks origin/main at a46501c.
Changes: Added Git remote, committed and pushed phase 0–2 source/doc changes.
Validation: Remote main contains a46501c; .gitignore excludes raw CSV and generated outputs; dataset hashes matched manifest.
Remaining: Confirm source timestamp and rollover metadata before phase 3.
```

## 2026-09-23 — Execution and checkpoint policy

```text
Status: DOCUMENTED
Changes: Recorded DEC-001 and portable .bat/checkpoint requirements for future heavy experiments.
Files changed: PROCESS.md, docs/research_plan.md.
Validation: Documentation review and git diff --check; no computational experiment run.
Latest checkpoint: N/A at the time of this decision; phase 3 later added bounded baseline smoke checkpoints.
Remaining: Use the rule for full baseline and later distribution experiments.
```

## 2026-09-23 — Phase 3 baseline

```text
Status: TESTED locally; full user-run NOT VERIFIED.
Changes: Added Normal EWMA, Normal rolling variance and empirical EWMA quantile baselines for 1m/5m, development-only date filter, daily atomic checkpoint/resume, metrics, portable run_baseline.bat.
Files changed: src/distributional_bands/baseline.py, configs/baseline_v1.json, tests/test_baseline.py, run_baseline.bat, README.md, docs/research_plan.md, PROCESS.md.
Validation: Eleven unit tests passed; bounded real-data smoke ran three days per timeframe and resumed from day two to day three.
Experiment ID: BASELINE-V1.
Latest checkpoint: outputs/baseline_smoke_v1/1m/latest.json and outputs/baseline_smoke_v1/5m/latest.json, both through 2017-11-08 (3/1790 development days).
Best checkpoint: N/A for deterministic baseline.
Artifacts: Smoke checkpoints only; no full development metrics or selected model.
Remaining: User runs run_baseline.bat on the other machine; inspect metrics/artifacts and validate source timestamp/rollover metadata.
```

## 2026-09-23 — Full baseline verification and research contract lock

```text
Status: USER-RUN ARTIFACTS VERIFIED; phase 4 not started.
Changes: Documentation only. Recorded user confirmation of bar-start timestamps, locked development OOS 2022–2024 and untouched final 2025–2026-07-17, and preserved unknown rollover/timezone status.
Files changed: README.md, docs/data_contract.md, docs/research_plan.md, PROCESS.md.
Validation: Both completed baseline runners reported `already complete; validated checkpoint and artifacts`; checkpoints show 1790/1790 days through 2024-12-31, 748 daily prediction files per timeframe, 177939 1m and 34344 5m OOS forecasts. No full experiment rerun.
Experiment ID: BASELINE-V1.
Latest checkpoint: outputs/baseline_v1/<timeframe>/latest.json, complete.
Best checkpoint: N/A for deterministic baseline.
Artifacts: outputs/baseline_v1/<timeframe>/{run_manifest.json,latest.json,metrics.json,predictions/}.
Remaining: Discuss and approve phase 4 fit/quantile scope; verify rollover and source timezone when metadata becomes available.
```

## 2026-09-23 — Phase 4A bounded distribution fitting

```text
Status: IMPLEMENTED and TESTED locally; full OOS distribution walk-forward NOT RUN.
Changes: Added Normal, Student-t, GED, NIG, GH and two-component Normal Mixture fitting on caller-supplied historical residuals; quantile/CDF/log-density interface, explicit convergence/failure diagnostics, versioned numeric config and synthetic tests. Added SciPy dependency.
Files changed: src/distributional_bands/distributions.py, configs/distribution_fit_v1.json, tests/test_distributions.py, pyproject.toml, README.md, docs/research_plan.md, PROCESS.md.
Validation: Eighteen unittest tests passed; six candidates fitted on bounded 120-observation historical samples from each timeframe. Mixture EM tolerance changed from 1e-6 to 1e-5 after the initial bounded 5m sample failed to converge within 300 iterations; this was numerical stability testing, not OOS metric selection.
Experiment ID: DISTRIBUTION-FIT-V1 configuration; no full experiment run or OOS metric artifact.
Rollback plan: Previous commit e0c647a; phase 4A source/config can be reverted independently, while BASELINE-V1 and DATA-V1 artifacts remain untouched.
Latest checkpoint: N/A for bounded fits; BASELINE-V1 completed checkpoints preserved.
Best checkpoint: N/A; no selection run.
Artifacts: Source, config and test only; no full distribution predictions or metrics.
Remaining: Phase 4B skewed-t/skewed-GED and three-component mixture sensitivity; phase 5 chronological OOS runner with portable .bat and checkpoint/resume. Source timezone and rollover remain open.
```

## 2026-09-23 — Phase 4B and Phase 5 user-run package

```text
Status: IMPLEMENTED and TESTED locally; full distribution user-run NOT VERIFIED.
Changes: Added two-piece skewed Student-t/GED and three-component Normal Mixture; development-only walk-forward with 60 prior trading days, refit every 5 days, per-model/per-day atomic checkpoint, fit-failure recording, paired OOS metrics, portable .bat preflight and resume.
Files changed: distributions.py, skewed.py, walk_forward.py, distribution_fit_v2.json, walk_forward_v1.json, run_distribution_walkforward.bat, tests/test_skewed.py, tests/test_walk_forward.py, README.md, docs/research_plan.md, PROCESS.md.
Validation: 28 unittest tests passed including chronology, final-test exclusion, mid-refit resume, orphan output reuse and corruption rejection. All nine candidates fitted on bounded 120-observation real samples for 1m and 5m. Predictive EWMA sigma matched verified baseline first development day within 1e-16 on both timeframes. A single bounded GH fit on 1000 1m residuals took 2.86 seconds on the local i5; this is not a full-run timing guarantee. `run_distribution_walkforward.bat check` passed and confirmed 0/748 days per timeframe without creating output. No full historical fit was run by AI.
Experiment ID: DISTRIBUTION-WF-V1; fit policy DISTRIBUTION-FIT-V2.
Latest checkpoint: Not created; user-run pending. BASELINE-V1 checkpoint retained.
Best checkpoint: N/A until OOS selection; paired ranking is descriptive only.
Artifacts: Source/config/tests and portable runner only; no official OOS predictions/metrics yet.
Rollback plan: Prior commit dc7618b. Remove/revert only this implementation if needed; do not touch DATA-V1 or BASELINE-V1 artifacts.
Remaining: User executes `.\run_distribution_walkforward.bat` on a machine with DATA-V1 artifacts and returns outputs/distribution_wf_v1/. Confirm source rollover/timezone when available; assess candidate coverage and fit failures before winner selection.
```

## 2026-09-23 — Phase 5 user-run verification and Phase 6 diagnostics package

```text
Status: DISTRIBUTION-WF-V1 USER-RUN ARTIFACTS VERIFIED; SELECTION-V1 IMPLEMENTED and locally TESTED, full diagnostics NOT RUN.
Changes: Verified completed 1m/5m distribution runs; added development-only quantile calibration, PIT, within-session exceedance dependence, yearly stability and day-block bootstrap comparisons with daily atomic checkpoint/resume.
Files changed: src/distributional_bands/selection.py, configs/selection_v1.json, run_selection.bat, tests/test_selection.py, README.md, docs/research_plan.md, PROCESS.md. DATA-V1, BASELINE-V1 and DISTRIBUTION-WF-V1 code/artifacts untouched.
Validation: Existing distribution runner confirmed both 748/748 checkpoints, all prediction hashes, metrics and fit histories. Each timeframe had 150 attempts/model, zero fit failures. 31 unit/integration tests passed; run_selection.bat check returned 0/748 each; bounded two-day real-data smoke and resume succeeded for each timeframe. No full diagnostics or final-test access.
Experiment ID: SELECTION-V1; upstream DISTRIBUTION-WF-V1 and BASELINE-V1.
Latest checkpoint: Phase 5 complete at outputs/distribution_wf_v1/<timeframe>/latest.json; Phase 6 full path not created. Bounded smoke checkpoints under outputs/selection_smoke_v*/ are ignored, not official.
Best checkpoint: N/A; no model selected. Descriptive leaders are GH 1m and Normal Mixture 3 5m, but margins over empirical EWMA are small.
Artifacts: New source/config/tests/batch only; official selection report pending user-run.
Remaining: User runs run_selection.bat and returns outputs/selection_v1/; evaluate calibration, uncertainty and stability, then explicitly agree on any winner lock. Source timezone/rollover remain unknown.
```

## 2026-09-23 — Phase 6 verification and Phase 7A half-life package

```text
Status: SELECTION-V1 USER-RUN ARTIFACTS VERIFIED. PHASE7A-V1 IMPLEMENTED and locally TESTED; full user-run pending.
Changes: Verified Phase 6 daily hashes and recomputed reports. User approved shortlist Empirical EWMA / Mixture 3 (1m) / Mixture 2 (5m), then approved Phase 7A EWMA half-life 30/60/120, fit window 60 days, refit every 5 days. Added new-only HL30/120 causal trial runner, checkpoint after each fit/day, report with 2022-23 tuning and retrospective 2024 diagnostics, portable .bat and tests.
Files changed: src/distributional_bands/phase7a.py, phase7a_report.py, configs/phase7a_v1.json, run_phase7a.bat, tests/test_phase7a.py, README.md, docs/research_plan.md, PROCESS.md. Existing Phase 3-6 source/config/checkpoints untouched.
Validation: Both SELECTION-V1 checkpoints complete 748/748; saved reports exactly match recomputation. 37 unit/integration tests passed, including synthetic interrupted/resumed trial and report. run_phase7a.bat check confirmed 0/748 on all four new trials. Bounded 1m HL120 Mixture 3 and 5m HL30 Mixture 2 real first-day fits succeeded; each resumed to day two. The HL60 sigma/Empirical bands matched BASELINE-V1 first OOS day within ~1e-16. No full Phase 7A run or final-test use.
Experiment ID: PHASE7A-V1; anchor BASELINE-V1/DISTRIBUTION-WF-V1/SELECTION-V1.
Latest checkpoint: Official Phase 7A not created; bounded smoke under outputs/phase7a_smoke_v*/ ignored. Completed SELECTION-V1 checkpoints preserved.
Best checkpoint: N/A; no parameter or model winner locked.
Artifacts: New source/config/tests/batch only; official Phase 7A report pending user-run.
Rollback plan: Prior commit 012a99e. Revert only new Phase 7A files/docs if necessary; never alter completed upstream artifacts.
Remaining: User runs run_phase7a.bat and returns outputs/phase7a_v1/. Assess conditional calibration and decide whether Phase 7B past-only correction is warranted. Source timezone/rollover remain unknown.
```

## 2026-09-23 — Phase 7A PIT boundary repair and checkpoint migration

```text
Status: PATCH TESTED; 1m-HL30 user-run 748/748 checkpoint verified; 1m-HL120 user-run 216/748 migrated and boundedly resumed to 217/748; 5m trials pending.
Cause: On 2022-11-16 at 10:46, target return 0.0377526 / sigma 0.001978 gave standardized residual ~19.09. Normal Mixture 3 EM weights summed to 1.000000000000004; CDF/PIT rounded to 1.000000000000004 and strict PIT bound raised. Fit succeeded; data outlier was not removed or relabeled.
Change: PIT roundoff within 1e-12 is clipped to [0,1], larger/nonfinite violations still fail. One-time migration accepts only the exact known old phase7a.py source hash and otherwise identical signature, verifies every checkpointed prediction/daily hash, backs up original metadata and records old/new signatures; .bat runs migration before resume. Check mode remains read-only.
Validation: 40 unittests passed including numeric guard, corrupt-artifact rejection, complete/incomplete migration, simulated migration interruption, and resume. Real orphan-day PIT recomputation passed all 238 bars; the existing orphan forecast CSV was reused unchanged. Official 1m-HL30 and HL120 metadata migrated after artifact verification; HL120 advanced exactly one day to 217/748 and both checkpoint checks passed. No full run or 2025+ use by AI.
Rollback: Original metadata is in each migrated trial's pit_boundary_migration_v1/ and the old source at commit a5d2664; do not restore/remove artifacts without an explicit plan. New code preserves old daily/prediction bytes and fit state.
Remaining: User pulls updated code and reruns run_phase7a.bat on compute machine. If machine has pre-migration outputs, .bat migrates them; if it has the already migrated workspace, migration is a no-op. Inspect full reports only after four trials finish.
```

## 2026-09-23 — Phase 7A verification and Phase 7B calibration package

```text
Status: PHASE7A-V1 USER-RUN ARTIFACTS VERIFIED. PHASE7B-V1 IMPLEMENTED and locally TESTED; full user-run pending.
Changes: Verified four completed Phase 7A checkpoints and recomputed both reports. On 2022-23, HL30 has lowest pinball on both timeframes, repeated in 2024 retrospective. Mixture 3 HL30 1m is only ~0.026% below Empirical HL30 in pinball; Mixture 2 HL30 5m is ~0.294% below Empirical HL30 but 95% coverage is only 93.964% vs Empirical 94.925%. No winner locked. Added a single expanding past-PIT calibration experiment on HL30, 60-day warmup, no refit/new grid, paired OOS report and checkpointed .bat.
Files changed: phase7b.py, phase7b_report.py, phase7b_v1.json, run_phase7b.bat, test_phase7b.py, README.md, docs/research_plan.md, PROCESS.md. Phase 3-7A source/config/outputs untouched.
Validation: run_phase7a.bat check and both phase7a_report --check-only passed 748/748/150 fits/0 failures. 44 unittests passed, including final-test exclusion, current-target nonleakage, resume and corruption rejection. run_phase7b.bat check confirmed 0/748 official days. Bounded real smoke for 1m and 5m saved 60 warmup days, resumed exactly one day to 61/748, generated first calibrated forecast and passed checkpoint integrity. No full Phase 7B run or 2025+ access.
Experiment ID: PHASE7B-V1; upstream PHASE7A-V1-HL30, SELECTION-V1, DATA-V1.
Latest checkpoint: Official Phase 7B path absent; final-source bounded smoke under outputs/phase7b_smoke_v2/ ignored (v1 smoke is also retained).
Best checkpoint: N/A; no model/calibration winner locked.
Rollback: Prior commit 8ca1d8f. Revert only new Phase 7B code/docs if required; leave verified Phase 3-7A outputs intact.
Remaining: User runs run_phase7b.bat on compute machine with verified Phase 7A outputs; inspect paired pinball/coverage/PIT and 2024 retrospective before any parameter lock or final test.
```

## 2026-09-23 — Phase 7B verification, model lock and Phase 8 package

```text
Status: PHASE7B-V1 USER-RUN VERIFIED. DEC-005 model lock approved. PHASE8-V1 IMPLEMENTED and locally TESTED; full user-run pending.
Changes: Verified 1m/5m Phase 7B checkpoints 748/748 and both reports recomputed exactly on 688 scored days. Locked 1m Empirical EWMA HL30 and 5m calibrated Mixture 2 HL30. Added a separate final-test runner with preserved 5m refit cadence, prior-day PIT updates, atomic fit/day checkpoints, no fallback or retuning, and a frozen final report.
Files changed: configs/phase8_v1.json, src/distributional_bands/phase8.py, phase8_report.py, run_phase8.bat, tests/test_phase8.py, README.md, docs/research_plan.md, PROCESS.md. All Phase 3–7B source/config/output artifacts untouched.
Validation: run_phase7b.bat check and both phase7b_report --check-only passed; run_phase8.bat check passed read-only for 0/381 final days per timeframe. Synthetic Phase 8 resume, integrity, first-fit cadence, fit-failure and report tests passed; full unittest suite 48 tests passed. No official Phase 8 prediction or score generated locally.
Experiment ID: PHASE8-V1; upstream PHASE7B-V1, PHASE7A-V1-HL30, DATA-V1.
Latest checkpoint: Official Phase 8 path absent. Completed Phase 7B checkpoints retained 748/748 each.
Best checkpoint: N/A; final test does not optimize or select a model.
Artifacts: Config pins both verified Phase 7B report hashes. Phase 8 artifacts will be written only when user runs run_phase8.bat.
Remaining: User runs run_phase8.bat check then run_phase8.bat on compute machine, returns outputs/phase8_v1/ for integrity and one-shot final evaluation. Timezone and rollover metadata remain unresolved.
```

## 2026-09-23 — Phase 8 final verification and negative-result record

```text
Status: PHASE8-V1 USER-RUN VERIFIED; result recorded. No Phase 9 or successor model approved.
Changes: Added docs/phase8_final_assessment.md and updated status/registry only. No code, config, checkpoint, prediction or report mutation.
Validation: run_phase8.bat check passed 381/381 each; phase8_report --check-only reproduced both reports. 1m: 90,478 bars, pinball 3.015375e-05, 95% coverage 94.968%. 5m: 17,474 paired bars; calibrated Mixture 2 pinball 7.259693e-05 versus Empirical HL30 7.243372e-05 (+0.2253% loss), 95% coverage 94.678% versus 94.941%; 76 fit attempts, zero failures. Day-block bootstrap CI for selected-minus-control is strictly positive; p=0.02249. 1m exceedances remain clustered.
Experiment ID: PHASE8-V1; model lock DEC-005 remains the historical pre-final decision, not a claim of success.
Latest checkpoint: outputs/phase8_v1/1m/latest.json and 5m/latest.json complete 381/381.
Best checkpoint: N/A; final test is not an optimization stage.
Artifacts: Both final reports and checkpoints verified; exact SHA-256 values in docs/phase8_final_assessment.md.
Remaining: Discuss whether to prioritize source metadata audit, conditional-calibration failure analysis (exploratory only), or a separately scoped Phase 9. Do not select a new 5m winner on this final period.
```

## 2026-09-25 — Scope narrowed to z_t distribution (DEC-006)

```text
Status: DOCUMENTED. No Phase 9 implementation approved.
Changes: Recorded DEC-006. Removed trading research from the phase table and README; renumbered phases so Final test = Phase 8 (as implemented). Added per-phase contribution to the research question and a proposed, unapproved Phase 9 (9A z_t diagnostics on development, 9B nine families at HL30, 9C descriptive nine-family table on 2025–2026, 9D seasonal-sigma protocol if warranted), all exploratory.
Files changed: README.md, docs/research_plan.md, docs/phase8_final_assessment.md, docs/data_contract.md, PROCESS.md.
Validation: Documentation review only; grep confirms no source/config/.bat references or hashes these documents. No experiment run.
Experiment ID: None.
Remaining: User chooses which Phase 9 items (if any) to approve; source timezone/rollover still open.
```

## 2026-09-25 — Phase 9E/9F proposal and official results report

```text
Status: DOCUMENTED; no Phase 9 implementation approved.
Changes: Added 9E (2 timeframes × 10 DGPs × R=200; 4,000 datasets, 36,000 parametric fits + empirical; optional 9E-c real-window bootstrap 600 datasets) and 9F (scale-normalization sensitivity) to docs/research_plan.md. Created Bao_cao/bao_cao_ket_qua.tex summarizing verified Phase 0–8 results from existing reports.
Findings recorded: No parameter-recovery simulation existed; tests only check numerical cdf/ppf/moment/convergence correctness. Parametric laws are normalized to variance 1 by their own theoretical moments while realized OOS z std is 1.018 (1m) / 1.076 (5m); Student-t df median 3.96 (1m) / 3.26 (5m), 28% of 5m fits df<3. Mixture 3 failed (weight floor) on a synthetic Student-t sample of n=2,753 in benchmark.
Validation: Local benchmark only (fit_distribution on synthetic t and mixture samples, n=2,753/14,271): ~5.5 s and ~23.7 s per dataset for all nine families, GH ~75–80%. Numbers in report extracted read-only from outputs/*/report.json; no official artifact modified.
Experiment ID: None (9E proposed as PHASE9E-V1).
Remaining: User reviews report and approves Phase 9 items; 9E should start with pilot R=20.
```

## 2026-09-25 — Statistical terminology pass (DEC-007)

```text
Status: DOCUMENTED.
Changes: Added docs/thuat_ngu.md (statistical Vietnamese glossary mapped to code names). Rewrote README.md, docs/research_plan.md, docs/phase8_final_assessment.md, Bao_cao/bao_cao_ket_qua.tex and edited docs/data_contract.md to use those terms. All numbers, decisions and hashes unchanged.
Validation: Report recompiled with XeLaTeX without errors or overfull boxes; grep shows no remaining "pinball"/"DGP"/"winner"/"shortlist" in human-facing prose (code identifiers excepted).
Remaining: Same as previous entry — user approval of Phase 9 items.
```

## 2026-09-25 — Phase 9A z_t diagnostics (PHASE9A-V1)

```text
Status: IMPLEMENTED, TESTED and RUN by AI (light, read-only). Exploratory; no model selection.
Scope: User approved 9A. Development 2022–2024 only; sources Phase 7A HL30 (z + empirical/mixture quantiles) and Phase 5 HL60 (z); every prediction file hash checked against its complete checkpoint; no refit; final-test rows rejected.
Changes: New src/distributional_bands/phase9a.py, configs/phase9a_v1.json, tests/test_phase9a.py; Bao_cao section 8 with pgfplots figures from Bao_cao/du_lieu/*.csv; research_plan/README/thuat_ngu updated.
Validation: 54 unittests pass (6 new: within-session pairing, clustered SE, lag labels, synthetic seasonality detect/remove, source hash/final-date guard, write-once + check-only). Real run 10 s (5m) / 22 s (1m); --check-only recomputation matches both reports.
Findings: E[z^2] rises ~monotonically intraday (1m 0.46→2.04; 5m 0.57→2.80) because continuous EWMA sigma carries previous-afternoon volatility into the open and lags the afternoon ramp; 95% coverage of empirical HL30 ranges 98.7%→87.2% (1m), 98.8%→85.3% (5m) while overall ≈95%; mixture shows same pattern (sigma, not F). z^2 ACF: 5m Q 119→7 after in-sample seasonal adjustment; 1m Q 6632→1389 with residual short-lag clustering (after |z|>=3, next-bar 95% coverage 88.6%). Excess kurtosis nearly unchanged after adjustment (1m 4.65→4.35; 5m 5.34→5.58).
Experiment ID: PHASE9A-V1.
Artifacts: outputs/phase9a_v1/<tf>/{report.json,acf.csv,intraday.csv,sigma_groups.csv,lagged_abs_z.csv}.
Remaining: Discuss 9D (past-only seasonal sigma) as next step; 9B/9C/9E/9F pending approval.
```

Template:

## YYYY-MM-DD — Task

```text
Status:

Changes:

Files changed:

Validation:

Experiment ID:

Latest checkpoint:

Best checkpoint:

Artifacts:

Remaining:
```

Không dump toàn bộ terminal log.

---

# 53. CURRENT TASK HANDOFF

Khi đổi AI hoặc kết thúc session dang dở:

Archived Phase 7B handoff (retained for audit; superseded by the Phase 8 block below):

```text
Current task: Hand off Phase 7B past-only PIT calibration package for full user execution and later model-lock discussion.

Current status: Phase 3/5/6/7A user-run artifacts VERIFIED. Phase 7B code/tests/bounded real smoke PASS; full Phase 7B user-run/report NOT VERIFIED.

Approved scope: After complete Phase 7A review, user approved proceeding with Phase 7B: past-only calibration of HL30 Mixture 3 (1m)/Mixture 2 (5m), Empirical HL30 reference, paired OOS score/calibration diagnostics, no final-test access or automatic winner. Implementation locks one expanding-PIT method with 60 prior development days of warmup; no new grid or refit.

What has been investigated: Four Phase 7A trials 748/748 and two reports recomputed. HL30 wins pinball across both timeframes, but Mixture HL30 undercovers; same-HL Mixture gain is tiny at 1m and modest at 5m. Prior 5m PIT has excess tail mass. Direct extra bootstrap comparisons were exploratory, not a winner lock.

What has been implemented: Standalone Phase 7B runner reads immutable Phase 7A HL30 forecast/fit artifacts, saves each day's raw PIT, uses only prior PITs to map target probabilities for the current fitted Mixture, and checkpoints daily. First 60 days warm up; paired report compares Empirical, raw Mixture, calibrated Mixture on later same bars with calibration/score/uncertainty. No fit rerun, auto-winner or final-test access.

Files touched this task: new phase7b.py, phase7b_report.py, phase7b_v1.json, run_phase7b.bat, test_phase7b.py; README.md, docs/research_plan.md, PROCESS.md. Phase 3-7A code/config/outputs untouched.

Pre-existing user changes: Git worktree was clean before this task. Local raw CSV and all completed user-generated outputs preserved. Bounded smoke under ignored outputs/phase7b_smoke_v*/ is separate from official output.

Tests already run: 44 unittests; run_phase7a.bat check; Phase 7A 1m/5m report --check-only; run_phase7b.bat check; bounded real Phase 7B 1m/5m 60-day warmup + one-day resume and integrity check. No full Phase 7B run or final-test use.

Experiment ID: PHASE7B-V1 (full user-run pending); upstream PHASE7A-V1 complete, with Phase 3/5/6 complete.

Latest checkpoint: Official outputs/phase7b_v1/ absent. Final-source bounded smoke at outputs/phase7b_smoke_v2/<timeframe>/latest.json 61/748 each, ignored and not official. Phase 7A four checkpoints complete 748/748 each.

Best checkpoint: N/A; no half-life or model winner locked.

Can resume: Phase 7B synthetic interrupted-run and real bounded 60→61 day resume VERIFIED on both timeframes; full user-run resume NOT VERIFIED until artifacts arrive.

Known issue: Source timezone and rollover metadata remain absent. First 60 Phase 7B days are warmup, not scored; extreme 5m calibration levels have few early observations, and serial dependence defeats guaranteed coverage. Original DATA-V1 config/manifest preserve prior unverified timestamp label despite user-confirmed bar starts.

Next recommended action: User pulls updated code with completed Phase 7A outputs, runs run_phase7b.bat check, then run_phase7b.bat on compute machine. Return outputs/phase7b_v1/ for artifact integrity, paired OOS and calibration review before any model lock.

Do NOT: Use 2025–2026-07-17 for model/parameter selection; do not run full fitting/backtest locally or rewrite versioned DATA-V1 artifacts.

Waiting for user action on: Full Phase 7B .bat run and returned trial artifacts. Rollover and source timezone metadata can be supplied later.
```

The handoff block above is historical and superseded by this current handoff:

```text
Current task: Phase 9A done; decide next Phase 9 item (9D recommended) under DEC-006 (project = best OOS distribution of z_t; no trading research).
Current status: Phase 0–8 done; 3/5/6/7A/7B/8 user-run verified. 5m locked calibrated Mixture 2 underperformed predeclared Empirical HL30 control on final pinball; 1m overall coverage near nominal but exceedances clustered. Development evidence (Phase 5–6): no parametric family clearly beats Empirical EWMA; Phase 7A: sigma half-life matters more than F. No Phase 9 or replacement winner approved.
Approved scope: 2026-09-25 user approved documentation-only scope update (DEC-006); done. No new fitting/model code.
Implemented: Updated README.md, docs/research_plan.md, docs/phase8_final_assessment.md, docs/data_contract.md, PROCESS.md; all code/config/artifacts unchanged.
Validation: Phase 8 integrity previously verified (run_phase8.bat check 381/381; phase8_report --check-only both). Scope update is docs-only.
Experiment: PHASE8-V1 complete; DEC-005 remains the historical pre-final model lock, not a statement that 5m passed final.
Next: User picks among proposed Phase 9 items (9A z_t diagnostics on development recommended first; 9B nine families at HL30; 9C descriptive 2025–2026 nine-family table; 9D seasonal sigma only if 9A warrants; 9E recovery/misspecification simulation, pilot R=20 first; 9F scale-normalization sensitivity). Official Phase 0–8 results are summarized in Bao_cao/bao_cao_ket_qua.tex for user review. All post-final results exploratory until verified on data after 2026-07-17.
Do NOT: Retune on 2025–2026 and call the same period independent final, overwrite Phase 8 outputs or silently promote the 5m Empirical control to a new locked winner.
```

AI mới phải đọc phần này trước khi tiếp tục.

---

# 54. CURRENT CHECKPOINT STATUS

```text
Experiment: PHASE8-V1 final test complete; upstream PHASE7B-V1 and prior phases complete
Run: PHASE8-V1-1m and PHASE8-V1-5m, locked by DEC-005
Latest checkpoint: outputs/phase8_v1/<timeframe>/latest.json
Progress: Both 381/381 final trading days; 1m 90,478 scored bars; 5m 17,474 scored bars and 76/76 fits successful.
Best checkpoint: N/A — one-shot final evaluation, no optimization
Primary metric: Mean pinball equally weighted over five central coverages
Value: 1m selected 3.015375e-05; 5m selected 7.259693e-05 versus Empirical control 7.243372e-05 (+0.2253% loss).
Integrity: Checkpoint/prediction/daily/PIT hashes verified by run_phase8.bat check; both reports recomputed exactly by phase8_report --check-only. Exact checkpoint and report SHA-256 in docs/phase8_final_assessment.md.
Resume status: Full user-run complete. Preserve outputs/phase8_v1 unchanged.
```

---

# 55. NEXT ACTIONS

```text
[x] Confirm bar-start source timestamp labeling with user; source timezone and contract rollover rule remain open.
[x] Lock development OOS 2022–2024 and untouched final 2025–2026-07-17 with user.
[x] Validate completed BASELINE-V1 1m/5m checkpoints, predictions and metrics.
[x] Approve and locally test phase 4A fitting/quantile library; no full OOS run yet.
[x] Implement and locally test phase 4B skewed families/mixture-3 and phase 5 checkpointed OOS runner.
[x] User ran run_distribution_walkforward.bat; checkpoints, prediction hashes and summaries validated for 1m/5m.
[x] Implement Phase 6 diagnostics runner and bounded validation without opening final test.
[x] User ran run_selection.bat; verified 748/748 days, daily hashes and reports on both timeframes.
[x] User approved Phase 7A shortlist and locked 30/60/120 grid; implementation and bounded validation complete.
[x] Diagnose 1m-HL120 PIT roundoff, implement guarded boundary handling, migrate verified checkpoints and test bounded real resume.
[x] User completed Phase 7A; all four checkpoints and both reports recomputed/verified, HL30 leading with Mixture coverage trade-off.
[x] Implement and locally test one past-only Phase 7B PIT calibration experiment with checkpointed .bat; no full run by AI.
[x] User ran run_phase7b.bat; both 748/748 checkpoints and 688-day reports verified.
[x] User approved DEC-005: 1m Empirical EWMA HL30; 5m PIT-calibrated Mixture 2 HL30.
[x] Prepare Phase 8 frozen runner, checkpointed .bat, report and synthetic tests; read-only preflight 0/381 each.
[x] User ran run_phase8.bat; 381/381 checkpoints and both final reports verified.
[x] Record Phase 8 result, including negative 5m model-vs-control outcome, without changing the model lock.
[x] Narrow scope to z_t distribution only (DEC-006); remove trading research from plan and renumber phases.
[x] Add 9E (parameter-recovery and misspecification simulation) and 9F (scale-normalization sensitivity) to the Phase 9 proposal; benchmark fit cost locally.
[x] Create Bao_cao/bao_cao_ket_qua.tex with official Phase 0–8 results for user review.
[x] User approved 9A; PHASE9A-V1 implemented, 6 new tests (54 total) pass, run on 1m/5m, reports re-checked, results added to Bao_cao and research_plan.
[ ] Approve (or reject) remaining Phase 9 items: 9D seasonal sigma (recommended next), 9B nine families at HL30, 9C descriptive 2025–2026 nine-family table, 9E simulation (pilot R=20 first), 9F scale normalization.
[ ] Obtain source timezone and contract rollover metadata when available.
[ ] Phase 10: synthesis report answering the research question, with reproducibility lineage.
```

Danh sách này không phải authorization để code.

Mỗi task mới vẫn phải qua:

```text
Inspect
→ Discuss
→ Approval
```

---

# 56. TECHNICAL DEBT / RISKS

Template:

## RISK-XXX — Title

```text
Area:

Description:

Impact:
LOW / MEDIUM / HIGH / CRITICAL

Likelihood:
LOW / MEDIUM / HIGH

Suggested remediation:

Status:
```

Không tự sửa technical debt ngoài scope.

---

# 57. CONTEXT HYGIENE

`PROCESS.md` là living operational document.

Không biến file thành kho chứa mọi lịch sử.

Giữ tại đây:

- Current state.
- Current handoff.
- Active decisions.
- Important pitfalls.
- Active risks.
- Current checkpoint.
- Core protocols.

Không giữ:

- Chain-of-thought.
- Terminal logs hàng nghìn dòng.
- Full source code.
- Historical noise.
- Typo nhỏ.

---

# 58. ARCHIVE POLICY

Khi lịch sử dài, chuyển sang:

```text
docs/
└── process/
    ├── ERRORS.md
    ├── DECISIONS.md
    ├── EXPERIMENTS.md
    ├── METRICS.md
    ├── DATASETS.md
    └── CHANGELOG_AI.md
```

`PROCESS.md` chỉ giữ summary và active information.

Ví dụ:

```text
PROCESS.md
→ current rules + current state

docs/process/ERRORS.md
→ historical errors

docs/process/EXPERIMENTS.md
→ full experiment history
```

---

# 59. DANGEROUS OPERATIONS

Không tự chạy:

```text
Production deployment
Live trading
Real financial orders
Production DB migration
DROP
TRUNCATE
Mass DELETE
Database reset
Delete checkpoints
Delete experiments
Delete datasets
git reset --hard
git clean -fd
Force push
Delete branch
Rotate credentials
Change secrets
Send real emails/messages
Modify production cloud infrastructure
```

Nếu cần:

```text
Explain
→ Discuss
→ Explicit approval
→ Prefer user-run command/.bat
```

---

# 60. ANTI-PATTERNS

AI không được:

```text
- Code trước rồi mới hỏi.
- Code ngay mà chưa inspect repository.
- Tự mở rộng approved scope.
- Refactor unrelated code.
- Tự đổi architecture.
- Thêm dependency vô lý.
- Claim tests pass khi chưa chạy.
- Claim model tốt hơn khi chưa có baseline.
- Thay dataset/test window âm thầm.
- Fit preprocessing bằng test data.
- Dùng future data trong signal.
- Cherry-pick metric.
- Chỉ báo positive results.
- Restart training mà chưa kiểm tra checkpoint.
- Save model chỉ khi training hoàn tất.
- Overwrite best checkpoint.
- Xóa checkpoint không cần thiết.
- Xóa uncommitted user work.
- Dump logs vào PROCESS.md.
- Lặp lại lỗi đã có trong Known Pitfalls.
- Chỉnh output thủ công.
- Over-engineer task đơn giản.
```

---

# 61. SESSION START CHECKLIST

```text
[ ] Read PROCESS.md
[ ] Read Current Status
[ ] Read Current Task Handoff
[ ] Read Known Pitfalls
[ ] Check git status
[ ] Check branch
[ ] Check uncommitted changes
[ ] Check current checkpoints
[ ] Check incomplete experiments
[ ] Inspect relevant code
[ ] Identify facts/assumptions/unknowns
[ ] Do NOT modify yet
[ ] Present findings
[ ] Present proposal
[ ] Wait for approval
```

---

# 62. LONG-RUN CHECKLIST

Trước train/backtest/optimization:

```text
[ ] Experiment ID created
[ ] Run ID created
[ ] Parent experiment recorded
[ ] Config saved
[ ] Dataset identified
[ ] Dataset hash/version recorded
[ ] Timezone verified
[ ] Train period recorded
[ ] Validation period recorded
[ ] Test period recorded
[ ] Features recorded
[ ] Seeds recorded
[ ] Environment recorded
[ ] Baseline recorded
[ ] Primary metric defined
[ ] Secondary metrics defined
[ ] Metric definitions verified
[ ] Transaction costs recorded
[ ] Slippage recorded
[ ] Execution assumptions recorded
[ ] Existing checkpoint checked
[ ] Resume possibility checked
[ ] Checkpoint interval defined
[ ] Checkpoint granularity prevents loss of a completed fold/window/trial
[ ] Latest checkpoint configured
[ ] Best checkpoint configured
[ ] Best metric defined
[ ] Output directory checked
[ ] No overwrite risk
[ ] Logging configured
[ ] Disk space checked
[ ] Resource budget checked
[ ] Save/load checkpoint tested
[ ] Interrupted-run resume tested without duplicate outputs
[ ] .bat uses portable paths and checks the target-machine environment
[ ] .bat prepared for real run
```

---

# 63. SESSION END CHECKLIST

```text
[ ] Update Current Status
[ ] Update Current Task Handoff
[ ] Update Progress Log
[ ] Record important errors
[ ] Update Known Pitfalls
[ ] Record technical decisions
[ ] Record latest checkpoint
[ ] Record best checkpoint
[ ] Record resume status
[ ] Record experiment artifacts
[ ] Record negative results if useful
[ ] Record remaining risks
[ ] Archive old history if necessary
[ ] Do not mark VERIFIED without evidence
```

---

# 64. DEFINITION OF DONE

Một task chỉ được xem là DONE khi các mục phù hợp được xác minh:

```text
[ ] Requirement implemented
[ ] Approved scope respected
[ ] Relevant tests pass
[ ] Build passes
[ ] Lint/type check passes
[ ] No known regression
[ ] No unrelated modifications
[ ] Error handling checked
[ ] No temporary debug code
[ ] No secrets exposed
[ ] Checkpoint implemented for long-running jobs
[ ] Resume verified
[ ] Data leakage checked
[ ] Look-ahead bias checked
[ ] Dataset/version recorded
[ ] Train/validation/test periods recorded
[ ] Random seed recorded
[ ] Baseline comparison fair
[ ] Metric definitions consistent
[ ] Costs/slippage recorded
[ ] Artifacts registered
[ ] Reproduction command exists
[ ] PROCESS.md updated
```

Nếu chưa kiểm tra:

```text
NOT VERIFIED
```

Không suy diễn thành PASS.

---

# 65. FINAL REPORT FORMAT

Sau implementation:

## Changed

```text
What changed:
```

## Approved Scope

```text
Scope respected:
YES / NO

Out-of-scope changes:
None / ...
```

## Files

```text
Files modified:
Files created:
Files deleted:
```

## Validation

```text
Commands:

Passed:
Failed:
Warnings:
```

## Verification Level

```text
IMPLEMENTED:
TESTED:
VERIFIED:
USER-RUN VERIFIED:
```

## Data / Model Safety

Nếu liên quan:

```text
Look-ahead check:

Leakage check:

Dataset:
Version/hash:

Train:
Validation:
Test:

Seed:

Baseline:

Primary metric:

Costs:
Slippage:
```

## Checkpoints

```text
Latest:

Best:

Interval:

Resume:
VERIFIED / NOT VERIFIED
```

## Artifacts

```text
Model:
Metrics:
Predictions:
Backtest:
Charts:
Logs:
Config:
```

## Remaining Risks

```text
None / ...
```

## User Action

Nếu cần real run:

```powershell
.\run_xxx.bat
```

Sau đó mô tả người dùng cần quan sát điều gì.

---

# 66. CORE PRINCIPLES

> **Inspect before proposing.**

> **Discuss before implementing.**

> **Lock the scope after approval.**

> **Test before claiming success.**

> **Checkpoint before risking hours of computation.**

> **Resume before restarting.**

> **Preserve existing user work.**

> **Know which data produced which result.**

> **Know which code and config produced which artifact.**

> **Define metrics before comparing models.**

> **Use a fixed baseline before claiming improvement.**

> **Report trade-offs, not only improvements.**

> **Never let future information leak into the past.**

> **Never silently change the experiment to get a better result.**

> **Negative results are valid research results.**

> **A result that cannot be reproduced should not be trusted as a final result.**

> **Record enough information so another AI—or the user months later—can understand exactly what happened.**
