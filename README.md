# Distributional Bollinger Bands for VN30F1M

**Trạng thái:** Phase 0–2 đã hoàn thành phần nền tảng; phase 3 baseline 1m/5m đã được người dùng chạy và xác minh artifact. Phase 4A có thư viện fit sáu phân phối và kiểm thử nhẹ; full distribution walk-forward và backtest chưa chạy.

Xem [lộ trình nghiên cứu](docs/research_plan.md) và [data contract](docs/data_contract.md). Dataset gốc `ohlc_export.csv` được giữ nguyên tại root và không đưa vào Git.

Chạy kiểm thử:

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
```

Chỉ audit dữ liệu (không ghi output):

```powershell
$env:PYTHONPATH = 'src'
python -m distributional_bands.cli audit
```

Để tạo bộ mẫu nghiên cứu chính thức, chạy `run_prepare.bat`. Lệnh này ghi `outputs/data_v1/` và từ chối ghi đè thư mục đã tồn tại.

## Phase 3: baseline development walk-forward

Trên máy Windows chạy job, dùng Python 3.11 trở lên và cài dependency từ repository:

```powershell
python -m pip install -e .
```

Sau khi `outputs/data_v1/` đã có đủ hai file mẫu và `manifest.json`, chạy `run_baseline.bat`. Cần mang theo repository và thư mục `outputs/data_v1/`; nếu chỉ có raw CSV, chạy `run_prepare.bat` trên máy đó trước. Script kiểm tra môi trường và yêu cầu ít nhất 2 GiB dung lượng đĩa trống trước khi chạy.

Script chạy lần lượt 1m và 5m, tự nhận checkpoint hợp lệ trong `outputs/baseline_v1/<timeframe>/latest.json` và tiếp tục từ ngày kế tiếp. Dự báo được lưu theo ngày trong `predictions/`; `metrics.json` chỉ có sau khi job hoàn tất. Ngắt job rồi chạy lại cùng lệnh để resume. Dataset, config hoặc code khác với checkpoint sẽ bị từ chối.

Lần chạy này chỉ phát dự báo development giai đoạn 2022–2024. Người dùng đã khóa 2025–17/07/2026 làm final test chưa dùng để chọn mô hình. Tham số và lịch chạy được ghi ở [baseline_v1.json](configs/baseline_v1.json); chi tiết tại [research plan](docs/research_plan.md).

## Phase 4A: fit phân phối (chưa chạy walk-forward)

`distributional_bands.distributions` cung cấp `fit_distribution(model, historical_residuals, config)` cho `normal`, `student_t`, `ged`, `nig`, `gh` và `normal_mixture_2`. Kết quả có `cdf`, `ppf`, `logpdf`, tham số và diagnostics hội tụ. Đầu vào phải là residual **chỉ từ quá khứ** do caller cung cấp; module không tự đọc dữ liệu hay truy cập final test. Fit thất bại sẽ ném `FitError`, không thay ngầm bằng Normal. Cấu hình versioned ở [distribution_fit_v1.json](configs/distribution_fit_v1.json).

Kiểm thử nhẹ bằng `python -m unittest discover -s tests -v`. Full fit/walk-forward cho cả lịch sử sẽ thuộc Phase 5 và cần `.bat` có checkpoint; chưa có lệnh full run ở Phase 4A.

Project này nghiên cứu việc **xây dựng và kiểm định Bollinger Band dựa trên các phân phối xác suất khác nhau** đối với hợp đồng tương lai **VN30F1M**, sử dụng dữ liệu nến **1 phút** và triển khai bằng Python.

Bollinger Band truyền thống sử dụng trung bình động và độ lệch chuẩn để xác định vùng giá bất thường. Tuy nhiên, lợi suất tài chính thường có các đặc điểm như **fat tails, skewness và volatility clustering**, khiến giả định về một phân phối đối xứng hoặc việc sử dụng cố định khoảng cách \(k\sigma\) có thể không phản ánh chính xác xác suất xuất hiện của các biến động cực đoan.

Mục tiêu chính của project là trả lời câu hỏi:

> **Phân phối nào ước lượng chính xác nhất xác suất lợi suất VN30F1M đi vào các vùng tail, đặc biệt trên dữ liệu out-of-sample?**

Các phân phối sẽ được xem xét có thể bao gồm:

- Normal
- Student-t
- Skewed Student-t
- GED
- Skewed GED
- Normal Inverse Gaussian (NIG)
- Generalized Hyperbolic (GH)
- Normal Mixture
- và các phân phối heavy-tail phù hợp khác.

Thay vì chỉ xây Bollinger Band dưới dạng:

\[
MA_t \pm k\sigma_t
\]

project sẽ xây dựng các **probabilistic / distributional bands** dựa trên quantile của từng phân phối:

\[
L_t=\mu_t+\sigma_tF^{-1}(\alpha)
\]

\[
U_t=\mu_t+\sigma_tF^{-1}(1-\alpha)
\]

với các mức tail như:

\[
90\%,\ 95\%,\ 97.5\%,\ 99\%,\ 99.5\%.
\]

Mỗi phân phối sẽ được đánh giá không chỉ dựa trên độ phù hợp in-sample như Log-Likelihood, AIC hay BIC, mà quan trọng hơn là khả năng **dự báo tail out-of-sample**, thông qua các kiểm định coverage, independence, PIT và walk-forward testing.

Sau khi xác định được các distributional bands có khả năng mô hình hóa tail tốt, project sẽ tiếp tục nghiên cứu xem việc giá/lợi suất đi vào các vùng xác suất cực đoan này có tạo ra thông tin hữu ích cho các logic giao dịch như **mean reversion, breakout hoặc regime-dependent trading** hay không.

Mục tiêu cuối cùng không đơn thuần là tìm ra phân phối “fit dữ liệu đẹp nhất”, mà là xác định:

\[
\boxed{
\text{Phân phối nào tạo ra các Bollinger Bands có ý nghĩa xác suất đáng tin cậy nhất?}
}
\]

và liệu những vùng tail đó có thực sự chứa **predictive information** có thể khai thác trong giao dịch VN30F1M hay không.
