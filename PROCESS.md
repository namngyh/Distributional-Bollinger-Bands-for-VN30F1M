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
Out-of-sample calibration of next-bar distributional bands on 1m and 5m VN30F1M data, followed by separate trading research.
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
Training: `distributional_bands.distributions.fit_distribution` (bounded fit library only; full walk-forward not implemented)
Backtest: Not implemented
Tests: python -m unittest discover -s tests -v
Configuration: configs/data_v1.json; configs/baseline_v1.json; configs/distribution_fit_v1.json
Checkpoints: outputs/baseline_v1/<timeframe>/latest.json (full run); bounded smoke checkpoints in outputs/baseline_smoke_v1/
Experiments: BASELINE-V1 (development forecasts); DISTRIBUTION-FIT-V1 is configuration/library only, no full run
Outputs: outputs/data_v1/; outputs/baseline_v1/ (user-run artifacts verified)
Logs: CLI stdout, run_manifest.json, metrics.json after completion
```

---

# 5. CURRENT STATUS

## Current objective

```text
Build and compare 1m/5m distributional bands, prioritizing out-of-sample forecast quality.
```

## Current task

```text
Phase 4A fit/quantile library for six candidates is implemented and lightly tested. Next: approve phase 4B skewed families and then phase 5 checkpointed OOS walk-forward.
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
TESTING — phase 4A unit and bounded real-data smoke tests passed; full distribution walk-forward has not run.
```

## Last known working state

```text
Branch: main (tracks origin/main)
Commit: See `git log -1`; original remote base is ca2d150.
Command: python -m unittest discover -s tests -v; bounded 120-observation 1m/5m in-sample fit smoke; git diff --check.
Result: Eighteen unit tests passed; all six phase 4A candidates fitted on each bounded historical sample; no full walk-forward or final-test access. Existing completed baseline artifacts remain verified.
Date: 2026-09-23
```

## Current modifications

```text
Phase 4A adds distributions.py, distribution_fit_v1.json, test_distributions.py and SciPy dependency; documentation updated. Baseline code/config/checkpoints and DATA-V1 artifacts are unchanged. Raw CSV and all outputs are ignored by Git and remain local.
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

```text
Current task: Phase 4A fit/quantile library implementation following verified phase 3 baseline.

Current status: Phase 4A IMPLEMENTED and locally TESTED; full phase 4/5 walk-forward NOT RUN. Phase 3 user-run artifacts remain VERIFIED.

Approved scope: User explicitly asked to start phase 4 after the phase 4A proposal. Implement six fit candidates, config, tests and docs; defer skewed families, full walk-forward and backtest.

What has been investigated: Baseline and DATA-V1 artifacts; SciPy GH/NIG/GED APIs and parameter constraints; synthetic quantiles/convergence; bounded historical numerical smoke.

What has been implemented: Phase 0–3 data/baseline foundation plus phase 4A fit library with Normal, Student-t, GED, NIG, GH and Normal Mixture 2, explicit failure diagnostics and unit tests.

Files touched this task: distributions.py, distribution_fit_v1.json, test_distributions.py, pyproject.toml, README.md, docs/research_plan.md, PROCESS.md. Baseline code/config/outputs untouched.

Pre-existing user changes: Git worktree was clean before this task. Local raw CSV and user-generated outputs/data_v1/ were preserved and remain ignored by Git.

Tests already run: Eighteen unittest tests and bounded 120-observation in-sample smoke for both timeframes. No full model fitting or OOS selection run.

Experiment ID: DISTRIBUTION-FIT-V1 config only; BASELINE-V1 completed artifacts remain available.

Latest checkpoint: outputs/baseline_v1/<timeframe>/latest.json, complete through 2024-12-31.

Best checkpoint: N/A for deterministic baseline.

Can resume: VERIFIED for bounded smoke; full run completed, so no resume needed. Artifact integrity verified.

Known issue: User confirmed bar-start timestamps. Source timezone and rollover metadata remain absent. Original DATA-V1 config/manifest retain the earlier unverified timestamp label to preserve hashes.

Next recommended action: Review phase 4B scope, then build phase 5 chronological OOS runner with portable .bat and atomic checkpoints after approval. Use only development data through 2024 for selection.

Do NOT: Use 2025–2026-07-17 for model/parameter selection; do not run full fitting/backtest locally or rewrite versioned DATA-V1 artifacts.

Waiting for user decision on: Phase 4B/phase 5 scope. Rollover and source timezone metadata can be supplied later.
```

AI mới phải đọc phần này trước khi tiếp tục.

---

# 54. CURRENT CHECKPOINT STATUS

```text
Experiment: BASELINE-V1 full development baseline
Run: BASELINE-V1-1m and BASELINE-V1-5m

Latest checkpoint: outputs/baseline_v1/<timeframe>/latest.json
Created: 2026-09-23
Progress: Both timeframes through 2024-12-31, 1790/1790 days; complete. 748 daily prediction files per timeframe.

Best checkpoint: N/A
Metric: N/A
Value: N/A

Resume status: VERIFIED for bounded smoke; completed full run checkpoint and artifacts validated. Full user-run interruption/resume was not separately observed.

Last successful resume test: 2026-09-23, resumed bounded 1m and 5m smoke from day 2 to day 3. Full completed-run validation: 2026-09-23.
```

---

# 55. NEXT ACTIONS

```text
[x] Confirm bar-start source timestamp labeling with user; source timezone and contract rollover rule remain open.
[x] Lock development OOS 2022–2024 and untouched final 2025–2026-07-17 with user.
[x] Validate completed BASELINE-V1 1m/5m checkpoints, predictions and metrics.
[x] Approve and locally test phase 4A fitting/quantile library; no full OOS run yet.
[ ] Discuss phase 4B skewed families and phase 5 checkpointed OOS runner.
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
