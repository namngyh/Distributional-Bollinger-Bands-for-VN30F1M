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

`configs/baseline_v1.json` cố định lần chạy development: dữ liệu quá khứ từ 2017 được cập nhật tuần tự; chỉ phát prediction từ 2022-01-01 đến 2024-12-31. Cửa sổ này hiện đã được người dùng chốt cho chọn mô hình OOS; final test bắt đầu 2025-01-01. Ba mô hình:

- `normal_ewma`: `mu=0`, phương sai EWMA cập nhật sau khi quan sát return; half-life 60 phút giao dịch.
- `normal_rolling`: `mu=0`, căn bậc hai của trung bình bình phương return trong 240 phút giao dịch gần nhất.
- `empirical_ewma`: quantile của return đã chia cho sigma EWMA, lấy từ tối đa 60 phiên trước đó và cố định trong ngày hiện tại; cần ít nhất 20 phiên lịch sử.

Normal quantile dùng phân phối chuẩn chuẩn hóa. Tất cả ba baseline dùng cùng các central coverage đã định nghĩa và lưu cả quantile return lẫn band giá. Forecast của bar hiện tại được tạo trước khi return mục tiêu đi vào EWMA, rolling window hoặc lịch sử empirical.

`run_baseline.bat` chạy hai timeframe theo thứ tự, ghi prediction từng ngày và checkpoint `latest.json` sau **mỗi ngày**. Khi resume, runner đối chiếu hash của input, data manifest, config, source code và mọi prediction đã checkpoint; một ngày bị gián đoạn có thể tính lại, nhưng output khác với file đã có sẽ bị từ chối. `best` không áp dụng cho baseline xác định, vì không có quá trình chọn model trong run. Người dùng đã chạy full baseline; AI kiểm tra lại checkpoint, hash và metrics của cả hai timeframe tại `outputs/baseline_v1/`. Cả hai hoàn tất 1.790 ngày, với 177.939 dự báo 1m và 34.344 dự báo 5m trong 2022–2024. Đây là kết quả development, không phải winner phân phối hay đánh giá final test.

## Phương pháp ước lượng dự kiến cho phase 3–7

Mô hình `r[t+1] = mu[t+1|t] + sigma[t+1|t] * z[t+1]`. Vòng so sánh phân phối đầu tiên đặt `mu=0`, dùng cùng volatility estimator EWMA trong từng timeframe, và fit phân phối trên `z`. Shape parameters fit trên rolling training window dài hơn cửa sổ cập nhật volatility. Tần suất fit và độ dài cửa sổ sẽ được chốt bằng validation; mốc thử ban đầu là 60 phiên và fit lại mỗi 5 phiên.

- Normal, Student-t, GED, skewed-t, skewed-GED, NIG, GH: maximum likelihood. GH cần tối ưu có ràng buộc, nhiều điểm khởi tạo và kiểm tra nghiệm.
- Normal Mixture: Gaussian mixture 2 thành phần bằng EM; 3 thành phần là sensitivity test. Cần nhiều khởi tạo, chặn phương sai tối thiểu và kiểm tra hội tụ.
- Empirical quantile: baseline phi tham số từ standardized residual quá khứ.

NIG là trường hợp con của GH, nhưng vẫn được so sánh riêng để xem tham số bổ sung của GH có cải thiện dự báo OOS không. Các phân phối phải có trung bình 0 và phương sai 1 sau chuẩn hóa trước khi đi vào công thức band.

### Phase 4A–4B: thư viện fit, chưa chọn mô hình

`src/distributional_bands/distributions.py` triển khai Normal, Student-t, GED, NIG, GH và Normal Mixture hai thành phần. Các họ Student-t/GED/NIG/GH fit bằng MLE có biên tham số và ba điểm khởi tạo; GH và NIG giữ `|b|<a` bằng tham số tỷ lệ có biên. Normal dùng ước lượng đóng. Mixture dùng EM với năm điểm khởi tạo theo seed, sàn phương sai/trọng số, kiểm tra hội tụ; quantile được đảo từ CDF bằng root finding. Tham số, likelihood **của luật sau chuẩn hóa**, số lần khởi tạo hội tụ và cảnh báo chạm biên được lưu trong kết quả. Fit thất bại nêu lỗi, không dùng fallback âm thầm. Mỗi luật sau fit được biến đổi affine về mean 0, variance 1; vì vậy đây là MLE/EM cho họ raw rồi chuẩn hóa, không phải tối ưu likelihood lại dưới ràng buộc mean/variance của luật cuối.

Config [distribution_fit_v1.json](../configs/distribution_fit_v1.json) khóa sáu ứng viên Phase 4A. Ngưỡng EM `1e-5` được chọn sau smoke fit rất nhỏ để tránh tiêu tốn hàng trăm bước khi hai thành phần gần không định danh; **không** được chọn bằng metric OOS. Phase 4B mở rộng bằng [distribution_fit_v2.json](../configs/distribution_fit_v2.json): two-piece skewed Student-t, two-piece skewed GED và Normal Mixture ba thành phần. Hai luật skew dùng nửa trái/phải của phân phối mẹ với scale khác nhau, sau đó chuẩn hóa mean 0/variance 1; skew bằng 0 trở về luật mẹ. Mixture 3 là sensitivity test, không tự động được ưu tiên hơn mô hình ít tham số. Unit tests dùng dữ liệu tổng hợp; smoke trên 120 residual đầu 2017 cho mỗi timeframe chỉ kiểm tra độ ổn định số, không phải dự báo hay so sánh chất lượng.

API và tham số phân phối tham chiếu tài liệu chính thức [SciPy GH](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.genhyperbolic.html), [NIG](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.norminvgauss.html) và [GED](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.gennorm.html).

Primary comparison: mean quantile/pinball loss trên các tail đã định trước. Secondary: interval score, coverage error và log score khi phù hợp. Guardrails: độc lập của chuỗi vượt band, PIT, độ ổn định theo năm/giờ/regime và tỷ lệ fit thất bại. Nếu khác biệt nằm trong bất định thống kê, ưu tiên mô hình đơn giản hơn.

## Chia dữ liệu và nguyên tắc thời gian

Người dùng đã chốt: phát triển và walk-forward validation đến hết 2024; final untouched test từ 2025-01-01 đến ngày cuối dữ liệu hiện có (2026-07-17). Không dùng final test để chọn tham số, distribution hoặc trading rule. Nếu nguồn dữ liệu được cập nhật, ranh giới final test vẫn bắt đầu 2025-01-01 và mọi thay đổi phạm vi phải được quyết định riêng.

Mỗi forecast chỉ dùng thông tin có sẵn khi bar nguồn đã hoàn tất. Prediction, target, dataset hash, policy hash, config và mã phiên bản phải đi cùng artifact. Full walk-forward, optimization và backtest được cung cấp bằng `.bat` để người dùng chạy theo `PROCESS.md`.

### Phase 5: runner development OOS

[walk_forward_v1.json](../configs/walk_forward_v1.json) khóa cùng EWMA half-life 60 phút giao dịch và rolling warm-up 240 phút như baseline, fit trên residual của **60 phiên trước ngày dự báo** và refit mỗi 5 phiên development. Vòng lặp đọc tối đa đến 2024-12-31, không mở final test 2025–2026. Tại mỗi thanh, EWMA sigma chỉ dùng return của các thanh trước; mô hình fit chỉ dùng những ngày trước ngày phát dự báo. Mỗi lần refit lưu tham số, quantile, train-window, trạng thái thành công/lỗi và checkpoint sau từng ứng viên. Dự báo từng ngày cũng được ghi atomically và checkpoint, cho phép resume không ghi trùng. `run_distribution_walkforward.bat` chạy 1m rồi 5m trên máy người dùng; AI chỉ chạy unit tests và smoke nhỏ.

`metrics.json` báo cáo pinball, coverage và exceedance theo mức/mô hình, cùng `paired_scores` chỉ trên những thanh có đủ tất cả ứng viên. `paired_pinball_ranking` là thứ tự mô tả theo mean pinball trung bình đều năm mức; **không** tự nhận winner nếu chưa xem fit failure, coverage, independence/PIT và độ ổn định. Fit lỗi không được thay bằng Normal; mô hình đó bỏ trống dự báo đến refit kế tiếp, lỗi hiện trong `fit_history.json`. Full job có thể tốn nhiều giờ; checkpoint theo từng mô hình/ngày bảo vệ kết quả. Phase 6 mới đánh giá và khóa winner trên development OOS.

Người dùng đã chạy DISTRIBUTION-WF-V1. Hai timeframe đều được xác minh complete 748/748 ngày (2022-01-04 đến 2024-12-31), tất cả prediction hashes/metrics/fit history hợp lệ, 150 lần fit/ứng viên/timeframe và không có fit failure. Xếp hạng pinball thuần mô tả: GH dẫn ở 1m, Normal Mixture 3 ở 5m, nhưng cải thiện so với empirical EWMA chỉ khoảng 0,06% và 0,29%; chưa phải bằng chứng đủ để chọn winner.

### Phase 6: đánh giá và quyết định trên development OOS

`configs/selection_v1.json` cố định reference `empirical_ewma`, bootstrap block 5 phiên, 2.000 lần lặp, seed, 10 bin PIT và ranh giới final test. `run_selection.bat` kiểm tra lineage/checkpoint rồi phân tích 1m, 5m từ các prediction CSV đã xác minh. Phân tích giữ cả ba baseline và chín phân phối, đối chiếu `TRADING_DATE/session/timestamp/available_at/target` trước khi chấm. Primary score là mean pinball trên năm band, trọng số bằng nhau, tính trên cùng bar. Báo cáo thêm coverage và lower/upper exceedance theo từng band, interval width, loss theo năm, Markov independence của exceedance trong cùng phiên (bỏ p-value nếu expected cell count <5), và PIT histogram của chín phân phối từ CDF fitted của đúng refit quá khứ. Histogram PIT là chẩn đoán, không lấy p-value iid ngây thơ vì serial dependence/parameter refit.

Chênh lệch score của từng phân phối so với empirical EWMA được ước lượng bằng circular block bootstrap theo **ngày giao dịch** (5 ngày/block), lấy tỷ số tổng loss/tổng số bar ở mỗi mẫu. Báo cáo CI 95% chưa hiệu chỉnh và p-value hai phía đã Holm-correct trên chín ứng viên. Nếu thiếu ngày paired vì fit failure, inference tạm dừng, không che mất việc thiếu mẫu. Block length là giả định cố định, không chứng minh bao trùm mọi phụ thuộc dài hạn. Không tự động chọn winner chỉ từ p-value: xem cả hiệu ứng tuyệt đối, calibration, PIT, stability, fit failure và độ phức tạp. Nếu chênh lệch nằm trong bất định thống kê, ưu tiên mô hình đơn giản hơn. Sau khi người dùng duyệt, mới ghi model lock riêng cho 1m/5m; final test vẫn đóng.

Full diagnostics đọc khoảng 1 GiB prediction CSV và PIT của GH có thể chậm; AI không chạy full job. Kết quả `outputs/selection_v1/<timeframe>/{run_manifest.json,latest.json,daily/,report.json}` có checkpoint sau mỗi ngày, và resume phải giữ nguyên code/config/artifact đầu vào.

Người dùng đã chạy SELECTION-V1; cả hai báo cáo hoàn tất 748/748 ngày, daily hashes hợp lệ, báo cáo tính lại từ daily checkpoint khớp chính xác. 1m: GH có mean pinball thấp nhất nhưng không cải thiện rõ so với Empirical EWMA sau Holm (`p=0,145`); Mixture 3 cải thiện khoảng 0,045% (`p=0,007`). 5m: Mixture 3 và 2 cải thiện khoảng 0,293%/0,282% (`p≈0,005`), nhưng Mixture 2 đơn giản hơn và coverage 95% tốt hơn (94,68% so với 94,11%; Empirical EWMA 94,93%). Các cải thiện rất nhỏ và exceedance vẫn tụ thành cụm; chưa khóa winner. Người dùng đồng ý shortlist Empirical EWMA, Mixture 3 (1m), Mixture 2 (5m) cho Phase 7A.

### Phase 7A: sensitivity EWMA half-life, chưa hiệu chỉnh band

Người dùng duyệt grid **30/60/120 phút giao dịch**, giữ fit window 60 phiên và refit mỗi 5 phiên. `configs/phase7a_v1.json` khóa chính sách đó, cùng các coverage trước đây, mốc chọn cấu hình 2022–2023 và 2024 chỉ là retrospective stability check (shortlist đã được xem trên toàn 2022–2024 nên 2024 không còn là holdout độc lập). `run_phase7a.bat` chỉ tạo hai trial mới mỗi timeframe tại `outputs/phase7a_v1/<timeframe>/hl30|hl120`; mốc 60 đọc lại từ SELECTION-V1/Phase 5. Không chạy lại hoặc sửa source/checkpoint của Phase 3–6. Tại half-life mới, sigma luôn dùng return trước thanh hiện tại; residual của 60 **ngày trước ngày dự báo** đi vào Empirical EWMA (cập nhật hằng ngày) và Mixture shortlist (fit lại mỗi 5 ngày). Mọi fit failure được ghi lại, không thay ngầm bằng Normal.

Runner ghi manifest, hash của data/config/code, fit history, forecast CSV và daily metrics/PIT atomically sau từng fit/ngày. Report chỉ xếp theo mean pinball đều năm mức trên **2022–2023 cùng bar**, thêm coverage, two-sided exceedance, dependence, PIT, 2024 và bootstrap day-block 5 phiên/2.000 lần lặp; p-value Holm cho năm lựa chọn khác Empirical EWMA HL60. Nếu thiếu ngày chung do fit failure, tạm bỏ ranking/inference chứ không dùng sample không cân bằng. Các p-value vẫn mang tính khám phá vì shortlist xuất phát từ cùng development data. Không tự chọn half-life, không thử thêm grid và không dùng final test. Phase 7B hiệu chỉnh calibration chỉ được đề xuất sau khi đọc kết quả Phase 7A.

Người dùng đã chạy full PHASE7A-V1: cả bốn trial 748/748 ngày, mỗi trial 150 fit và 0 fit failure; hai báo cáo tính lại khớp artifact. Half-life 30 có pinball thấp nhất ở cả hai khung trong 2022–2023 và xu hướng lặp lại trên 2024 hồi cứu. Tuy nhiên Mixture–30 thiếu coverage so với Empirical–30: trên toàn development, 1m coverage 95% là 94,742% so với 94,990%; 5m là 93,964% so với 94,925%, và dải 99,5% của Mixture 5m chỉ đạt 99,065%. Direct Mixture–30 vs Empirical–30 chỉ hơn khoảng 0,026% pinball 1m và 0,294% 5m trên giai đoạn xếp hạng; chênh lệch 1m không rõ so với bất định. Vì vậy chưa khóa winner, cần thử hiệu chỉnh có kiểm soát.

### Phase 7B: past-only PIT recalibration, một phép thử đã định trước

`configs/phase7b_v1.json` khóa **chỉ half-life 30**, Empirical EWMA làm đối chứng, Mixture 3 ở 1m/Mixture 2 ở 5m, 60 ngày development đầu làm warmup PIT, lịch sử hiệu chỉnh mở rộng theo những ngày đã qua. Không refit Mixture, không thay fit window/tần suất fit hoặc thêm grid. Với dự báo phân phối thô \(F_t\), quan sát ngày trước cho PIT \(u_i=F_i(r_{i+1})\). Trước ngày \(d\), chỉ dùng \(u_i\) của các ngày \(<d\) để ước lượng phân vị PIT \(\hat H_{d-1}^{-1}(p)\); band đã hiệu chỉnh tại mức \(p\) là \(F_d^{-1}(\hat H_{d-1}^{-1}(p))\). Xác suất hiệu chỉnh được chặn vào `(1e-9, 1-1e-9)` để tránh PPF vô hạn, và ánh xạ phải đơn điệu. Ngày hiện tại chỉ được thêm vào lịch sử sau khi dự báo/ngày đó hoàn tất. CDF PIT sau hiệu chỉnh dùng empirical rank có smoothing nhỏ, là chẩn đoán xấp xỉ vì ECDF bậc thang.

Runner `run_phase7b.bat` kiểm tra toàn bộ Phase 7A HL30/checkpoint/báo cáo trước khi chạy, giữ nguyên các artifact nguồn. Mỗi ngày lưu raw PIT `.npy`, prediction CSV khi đủ warmup, daily score và `latest.json` atomically với hash để resume/không nhân đôi. Báo cáo chấm ba phương án trên **cùng ngày/nến sau warmup**, giữ mean pinball bằng trọng số năm band, coverage và exceedance từng phía, PIT, independence, 2024 hồi cứu, bootstrap khối năm ngày/2.000 lần, Holm cho hai Mixture so với Empirical–30 và direct calibrated-vs-raw chỉ như so sánh khám phá. Không tự chọn winner hay dùng 2025+. Ở 5m, 60 phiên đầu có ít quan sát vùng 99,5%; hiệu chỉnh PIT không có bảo đảm coverage dưới serial dependence, nên nếu lợi thế không ổn định hoặc pinball xấu đi, ưu tiên Empirical–30 đơn giản hơn.

### Phase 8: đánh giá final một lần sau quyết định khóa

Người dùng đã chạy và xác minh Phase 7B: mỗi khung 748/748 ngày, 688 ngày chấm điểm sau warmup. Trên cùng nến giai đoạn xếp hạng 2022–2023, lợi thế pinball của Mixture 3 gốc ở 1m so với Empirical–30 chỉ 0,023% và không rõ so với bất định; bản hiệu chỉnh kém hơn 0,003%. Ở 5m, Mixture 2 gốc cải thiện 0,267% nhưng coverage 95% chỉ 93,834%. Hiệu chỉnh PIT cải thiện pinball 0,131% so với Empirical–30, đưa coverage về 94,928% (Holm p=0,023). 2024 chỉ kiểm tra hồi cứu, không phải holdout độc lập.

DEC-005 khóa trước final test: **1m Empirical EWMA HL30** và **5m Normal Mixture 2 HL30, hiệu chỉnh PIT bằng các phiên trước**. `configs/phase8_v1.json` giữ nguyên năm mức coverage, cửa sổ fit 60 phiên, lịch refit mỗi 5 phiên, dải final 2025-01-01–2026-07-17 và hash hai báo cáo Phase 7B đã được duyệt. 5m tiếp tục đúng nhịp refit từ 2022–2024: fit phát sinh khi chỉ số ngày development+final chia hết cho 5, không tự reset ở phiên đầu 2025. Dự báo σ EWMA chỉ dùng target của các nến trước; fit mới dùng 60 phiên hoàn tất trước ngày dự báo. PIT hiệu chỉnh khởi đầu bằng 748 phiên development và chỉ nhận thêm PIT final sau khi ngày tương ứng đã chấm xong. Không thay model khi fit lỗi; giữ checkpoint và dừng để chẩn đoán.

`run_phase8.bat check` là preflight chỉ đọc; `run_phase8.bat` là full job do người dùng chạy trên máy compute. Runner ghi prediction, daily score, 5m PIT và `latest.json` atomically theo mỗi fit/ngày, xác minh hash của data/config/source/upstream trước khi resume. Final report chấm pinball trung bình đều năm band, coverage và vượt band hai phía, independence, PIT, tách 2025/2026 mô tả. 5m có đối chứng Empirical–30 trên cùng nến và bootstrap ngày khối 5; 1m chỉ chấm mô hình đã khóa. Không xếp hạng hay chỉnh lại mô hình từ kết quả final. Artifact Phase 3–7B không bị sửa.

## Quy tắc chạy và checkpoint

AI chạy trực tiếp các kiểm tra nhẹ (unit/smoke tests, audit, benchmark nhỏ). Full fitting, walk-forward, optimization và backtest có thể tốn nhiều thời gian sẽ được đóng gói thành `.bat` dùng đường dẫn portable để chạy trên máy khác. Mỗi job phải kiểm tra checkpoint hợp lệ và resume trước khi bắt đầu mới; lưu tiến độ định kỳ, tối thiểu sau từng fold/window/trial hoàn tất, bằng cách ghi an toàn qua file tạm rồi thay thế. `latest` phục vụ resume, `best` lưu kết quả tốt nhất theo metric đã định nghĩa trước. Checkpoint và manifest ghi dataset/config/code hash, run ID và vị trí tiến độ để tránh mất hoặc ghi trùng kết quả.

## Trạng thái hiện tại

Phase 0–2 đã triển khai và kiểm thử. Phase 3/5/6/7A/7B: full user-run 1m/5m đã xác minh bằng checkpoint/artifact hashes và báo cáo. Phase 4A–4B: thư viện fit đã dùng trong Phase 5. Người dùng đã khóa mô hình qua DEC-005. Phase 8: code, `.bat`, tests và preflight chỉ đọc đã có; full final user-run chưa thực hiện. Phase 9–10 chưa triển khai. Người dùng xác nhận timestamp là đầu nến; timezone nguồn và rollover vẫn chưa xác minh, như ghi trong [data contract](data_contract.md).
