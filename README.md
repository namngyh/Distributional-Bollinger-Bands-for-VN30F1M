# Distributional Bollinger Bands for VN30F1M

**Trạng thái:** Đã triển khai phase 0–2 (research contract, data audit, chuẩn bị mẫu 1m/5m). Chưa fit phân phối hoặc chạy backtest.

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
