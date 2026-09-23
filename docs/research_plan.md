# Research plan — VN30F1M distributional bands

## Mục tiêu và nguyên tắc chọn mô hình

Tại thời điểm bar `t` hoàn tất, dự báo phân phối log-return của bar kế tiếp:

`r[t+1] = log(C[t+1] / C[t])`.

Với các quantile dự báo `q_low` và `q_high`, band giá là `C[t] * exp(q_low)` và `C[t] * exp(q_high)`. Nghiên cứu 1m và 5m riêng; mỗi khung có thể có winner khác nhau. **Chất lượng dự báo out-of-sample là tiêu chí chính.** In-sample likelihood, AIC và BIC chỉ dùng để chẩn đoán fit và độ phức tạp.

Các band trung tâm dự kiến: 90%, 95%, 97,5%, 99% và 99,5%. Ví dụ band 95% dùng quantile 2,5% và 97,5%. Kết quả lower và upper tail luôn được báo cáo riêng.

## Các phase và gate

| Phase | Công việc | Gate để chuyển bước |
|---|---|---|
| 0. Research contract | Chốt target, timing, tiêu chí chọn, chronology | Định nghĩa đã ghi và versioned |
| 1. Data audit | Schema, nguồn, phiên, gap, auction, anomaly, rollover | Data contract và các unknown được ghi rõ |
| 2. Mẫu 1m/5m | Return liên tục trong phiên; 5m chỉ từ đủ năm bar | Tests chống leakage và kiểm tra aggregation |
| 3. Baseline | Normal, EWMA, empirical quantile, Bollinger truyền thống | Dự báo baseline tái tạo được |
| 4. Distribution fitting | Student-t, GED, skewed variants, NIG, GH, Normal Mixture | Fit/quantile/convergence tests |
| 5. Walk-forward | Dự báo theo chronology; fit lại trên quá khứ; checkpoint/resume | Dự báo OOS và resume được xác minh |
| 6. Chọn distribution | Quantile loss, interval score, coverage, independence, PIT | Winner riêng 1m/5m từ validation OOS |
| 7. Tối ưu band | Lookback, EWMA half-life, fit window/frequency | Cấu hình band được khóa |
| 8. Trading research | Mean reversion, breakout, 5m regime + 1m entry | Luật giao dịch và chi phí được khóa |
| 9. Final test | Đánh giá trên giai đoạn chưa dùng chọn mô hình | Báo cáo toàn bộ kết quả, gồm kết quả âm |
| 10. Reproducibility | Artifact lineage, config, logs, scripts, báo cáo | Run có thể truy nguyên và tái tạo |

### Baseline implementation (phase 3)

`configs/baseline_v1.json` cố định lần chạy development: dữ liệu quá khứ từ 2017 được cập nhật tuần tự; chỉ phát prediction từ 2022-01-01 đến 2024-12-31. Đây là cửa sổ development cho baseline, chưa phải quyết định về final test. Ba mô hình:

- `normal_ewma`: `mu=0`, phương sai EWMA cập nhật sau khi quan sát return; half-life 60 phút giao dịch.
- `normal_rolling`: `mu=0`, căn bậc hai của trung bình bình phương return trong 240 phút giao dịch gần nhất.
- `empirical_ewma`: quantile của return đã chia cho sigma EWMA, lấy từ tối đa 60 phiên trước đó và cố định trong ngày hiện tại; cần ít nhất 20 phiên lịch sử.

Normal quantile dùng phân phối chuẩn chuẩn hóa. Tất cả ba baseline dùng cùng các central coverage đã định nghĩa và lưu cả quantile return lẫn band giá. Forecast của bar hiện tại được tạo trước khi return mục tiêu đi vào EWMA, rolling window hoặc lịch sử empirical.

`run_baseline.bat` chạy hai timeframe theo thứ tự, ghi prediction từng ngày và checkpoint `latest.json` sau **mỗi ngày**. Khi resume, runner đối chiếu hash của input, data manifest, config, source code và mọi prediction đã checkpoint; một ngày bị gián đoạn có thể tính lại, nhưng output khác với file đã có sẽ bị từ chối. `best` không áp dụng cho baseline xác định, vì không có quá trình chọn model trong run. Full run do người dùng thực hiện trên máy khác; AI chỉ chạy bounded smoke test.

## Phương pháp ước lượng dự kiến cho phase 3–7

Mô hình `r[t+1] = mu[t+1|t] + sigma[t+1|t] * z[t+1]`. Vòng so sánh phân phối đầu tiên đặt `mu=0`, dùng cùng volatility estimator EWMA trong từng timeframe, và fit phân phối trên `z`. Shape parameters fit trên rolling training window dài hơn cửa sổ cập nhật volatility. Tần suất fit và độ dài cửa sổ sẽ được chốt bằng validation; mốc thử ban đầu là 60 phiên và fit lại mỗi 5 phiên.

- Normal, Student-t, GED, skewed-t, skewed-GED, NIG, GH: maximum likelihood. GH cần tối ưu có ràng buộc, nhiều điểm khởi tạo và kiểm tra nghiệm.
- Normal Mixture: Gaussian mixture 2 thành phần bằng EM; 3 thành phần là sensitivity test. Cần nhiều khởi tạo, chặn phương sai tối thiểu và kiểm tra hội tụ.
- Empirical quantile: baseline phi tham số từ standardized residual quá khứ.

NIG là trường hợp con của GH, nhưng vẫn được so sánh riêng để xem tham số bổ sung của GH có cải thiện dự báo OOS không. Các phân phối phải có trung bình 0 và phương sai 1 sau chuẩn hóa trước khi đi vào công thức band.

Primary comparison: mean quantile/pinball loss trên các tail đã định trước. Secondary: interval score, coverage error và log score khi phù hợp. Guardrails: độc lập của chuỗi vượt band, PIT, độ ổn định theo năm/giờ/regime và tỷ lệ fit thất bại. Nếu khác biệt nằm trong bất định thống kê, ưu tiên mô hình đơn giản hơn.

## Chia dữ liệu và nguyên tắc thời gian

Mốc đề xuất để khóa trước phase 5: phát triển và walk-forward validation đến hết 2024; final untouched test từ 2025 đến ngày cuối dữ liệu. Không dùng final test để chọn tham số, distribution hoặc trading rule. Ngày 2025–2026 hiện là **đề xuất**, chưa phải quyết định đã duyệt.

Mỗi forecast chỉ dùng thông tin có sẵn khi bar nguồn đã hoàn tất. Prediction, target, dataset hash, policy hash, config và mã phiên bản phải đi cùng artifact. Full walk-forward, optimization và backtest được cung cấp bằng `.bat` để người dùng chạy theo `PROCESS.md`.

## Quy tắc chạy và checkpoint

AI chạy trực tiếp các kiểm tra nhẹ (unit/smoke tests, audit, benchmark nhỏ). Full fitting, walk-forward, optimization và backtest có thể tốn nhiều thời gian sẽ được đóng gói thành `.bat` dùng đường dẫn portable để chạy trên máy khác. Mỗi job phải kiểm tra checkpoint hợp lệ và resume trước khi bắt đầu mới; lưu tiến độ định kỳ, tối thiểu sau từng fold/window/trial hoàn tất, bằng cách ghi an toàn qua file tạm rồi thay thế. `latest` phục vụ resume, `best` lưu kết quả tốt nhất theo metric đã định nghĩa trước. Checkpoint và manifest ghi dataset/config/code hash, run ID và vị trí tiến độ để tránh mất hoặc ghi trùng kết quả.

## Trạng thái hiện tại

Phase 0–2: đã triển khai và kiểm thử. Phase 3: baseline runner đã triển khai, unit tests và bounded smoke test đã đạt; full user-run chưa được xác minh. Phase 4–10: chưa triển khai. Các unknown về timestamp convention và rollover được giữ rõ trong [data contract](data_contract.md).
