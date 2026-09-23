# Distributional Bollinger Bands for VN30F1M

**Trạng thái:** Phase 0–2 đã hoàn thành phần nền tảng; phase 3 baseline 1m/5m đã được người dùng chạy và xác minh artifact. Phase 4 có chín ứng viên và runner walk-forward OOS đã kiểm thử nhẹ; **full distribution run và backtest chưa chạy**.

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

## Phase 4: fit phân phối và development OOS walk-forward

`distributional_bands.distributions` cung cấp `fit_distribution(model, historical_residuals, config)` cho Normal, Student-t, GED, two-piece skewed-t/GED, NIG, GH, Normal Mixture 2 và 3 thành phần. Kết quả có `cdf`, `ppf`, `logpdf`, tham số và diagnostics hội tụ. Đầu vào fit chỉ gồm residual quá khứ. Fit thất bại được ghi rõ, không thay ngầm bằng Normal. Cấu hình runner chính thức ở [distribution_fit_v2.json](configs/distribution_fit_v2.json) và [walk_forward_v1.json](configs/walk_forward_v1.json); V1 của thư viện vẫn được giữ nguyên.

Trên máy chạy, cập nhật Git và cài dependency bằng `python -m pip install -e .`; đảm bảo `outputs/data_v1/` gồm `manifest.json` và cả hai file `samples_*.csv` (không nằm trong Git). Sau đó chạy:

```powershell
.\run_distribution_walkforward.bat
```

Script kiểm tra Python >=3.11, NumPy/pandas/SciPy, dữ liệu, config, checkpoint và >=4 GiB đĩa trống; chạy 1m rồi 5m. Job có thể kéo dài nhiều giờ vì GH và các lần refit trên 60 phiên lịch sử mỗi 5 phiên. Sau **mỗi mô hình fit** và **mỗi ngày dự báo** sẽ ghi checkpoint `outputs/distribution_wf_v1/<timeframe>/latest.json`. Nếu dừng, chạy lại cùng `.bat`; không xóa output. Không sửa source/config/input giữa chừng vì resume sẽ từ chối hash khác. Một fit lỗi được ghi lại và mô hình đó tạm không phát dự báo đến lần refit kế tiếp; không dùng fallback.

Có thể chạy `.\run_distribution_walkforward.bat check` để chỉ kiểm tra môi trường/dữ liệu/checkpoint mà **không** bắt đầu fit.

Khi hoàn tất, gửi lại toàn bộ `outputs/distribution_wf_v1/` để kiểm tra. `metrics.json` gồm điểm trên mọi dự báo khả dụng, điểm **paired** trên các thanh mà cả chín mô hình đều fit thành công, và bảng xếp hạng pinball mô tả. `fit_history.json` giữ tham số, cửa sổ train, hội tụ và lỗi từng lần refit. Đây **chưa phải** quyết định winner cuối cùng: cần xét coverage, fit failure, ổn định theo thời gian; 2025–2026 tiếp tục là final test chưa đụng tới.

## Phase 6: đánh giá development OOS

Hai run distribution walk-forward 1m/5m đã được người dùng chạy và kiểm tra hoàn tất 748/748 ngày, với 0 fit failure trên cả chín ứng viên. Chạy `run_selection.bat check` để kiểm tra nguồn và checkpoint mà không phân tích; chạy `run_selection.bat` để tính đầy đủ. Script chỉ đọc DATA-V1, BASELINE-V1 và DISTRIBUTION-WF-V1; kết quả lưu riêng ở `outputs/selection_v1/<timeframe>/`. Mỗi ngày phân tích xong được ghi atomically vào `daily/` và `latest.json`; chạy lại cùng lệnh để resume. Full run có thể tốn thời gian vì PIT của GH; AI chỉ chạy smoke giới hạn.

`report.json` gồm pinball trên cùng thanh dự báo, coverage và exceedance hai phía, độ rộng band, độ ổn định theo năm, independence của các lần vượt band trong từng phiên, histogram PIT của các phân phối, cùng khoảng tin cậy day-block bootstrap/giá trị p hiệu chỉnh Holm so với empirical EWMA. Đây là **chẩn đoán trên development OOS**, không tự động khóa winner hay mở final test. Cần trao đổi kết quả và ghi quyết định chọn mô hình trước khi dùng dữ liệu 2025+.

## Phase 7A: kiểm tra half-life của volatility

Người dùng đã chạy đầy đủ SELECTION-V1 cho 1m và 5m; checkpoint 748/748 và báo cáo được xác minh. Shortlist nghiên cứu (chưa phải winner): Empirical EWMA làm đối chứng, Normal Mixture 3 cho 1m và Normal Mixture 2 cho 5m. [phase7a_v1.json](configs/phase7a_v1.json) khóa EWMA half-life 30/60/120 phút giao dịch, cửa sổ fit 60 phiên và refit mỗi 5 phiên. Mốc 60 phút **dùng lại** artifact Phase 5–6 đã xác minh; Phase 7A chỉ chạy mới mốc 30/120. Cả hai mô hình được dự báo lại nhân quả cho từng mốc, vì thay sigma cũng thay standardized residual và quantile fit.

Chạy `run_phase7a.bat check` để kiểm tra mà không fit, sau đó `run_phase7a.bat` trên máy tính dành cho job nặng. Bốn trial ghi prediction CSV, daily score/PIT và checkpoint atomically sau từng lần fit/ngày vào `outputs/phase7a_v1/<timeframe>/hl<half_life>/`; chạy lại cùng lệnh để resume. Kết thúc sẽ tạo `outputs/phase7a_v1/<timeframe>/report.json`: xếp hạng bằng pinball 2022–2023, còn 2024 là kiểm tra độ ổn định hồi cứu, **không** phải holdout sạch vì shortlist đã được xem trên toàn bộ 2022–2024. Báo cáo vẫn giữ coverage, exceedance clustering, PIT, fit failure và bootstrap so với Empirical EWMA half-life 60. Không tự khóa tham số hoặc mở final test 2025+.

Nếu checkpoint Phase 7A được tạo bằng bản code trước sửa lỗi PIT ngày 2022-11-16, `run_phase7a.bat check` sẽ xác minh và báo cần migration nhưng **không ghi dữ liệu**. Chạy lại `run_phase7a.bat` sau khi cập nhật code: script tự xác minh toàn bộ hash, sao lưu metadata gốc vào `pit_boundary_migration_v1/`, ghi record nguồn gốc, chỉ cập nhật source signature của trial và resume từ ngày kế tiếp. Prediction/daily đã checkpoint và fit state không bị tính lại hoặc xóa. Nếu migration bị ngắt, chạy lại cùng file để hoàn tất; không xóa output. Bản sửa chỉ chặn sai số CDF trong phạm vi `1e-12` sát 0/1 trước khi lập PIT; CDF sai lớn hơn vẫn làm job dừng.

## Phase 7B: hiệu chỉnh PIT bằng dữ liệu quá khứ

Phase 7A đã được người dùng chạy đủ bốn trial và hai báo cáo đã được kiểm tra lại. Half-life 30 phút đứng đầu pinball development trên cả 1m/5m, nhưng Mixture–30 bị thiếu coverage, đặc biệt ở 5m; **chưa khóa winner**. [phase7b_v1.json](configs/phase7b_v1.json) cố định một phép thử hiệu chỉnh, không mở grid mới: chỉ lấy PIT của các dự báo Mixture–30 đã xảy ra trước ngày hiện tại, xây ánh xạ phân vị PIT theo lịch sử mở rộng, rồi đảo CDF của fit Mixture hiện tại để tạo band đã hiệu chỉnh. Không fit lại distribution hay đụng vào Phase 7A. 60 ngày development đầu chỉ dùng khởi động và không được chấm là dự báo hiệu chỉnh; ba phương án Empirical–30, Mixture–30 gốc và Mixture–30 hiệu chỉnh được so trên cùng các nến còn lại. 2022–2023 là giai đoạn xếp hạng, 2024 chỉ kiểm tra ổn định hồi cứu; final test 2025+ vẫn đóng. Hiệu chỉnh PIT này không bảo đảm coverage khi quan sát phụ thuộc theo thời gian.

Chạy `run_phase7b.bat check` để kiểm tra chỉ đọc Phase 7A và checkpoint 7B; sau đó chạy `run_phase7b.bat` trên máy dành cho tác vụ dài. Runner lưu PIT, prediction, daily diagnostics và `latest.json` atomically sau **mỗi ngày**, kiểm tra hash khi resume, rồi tạo báo cáo riêng 1m/5m trong `outputs/phase7b_v1/`. Không xóa output khi bị ngắt; chạy lại cùng file để tiếp tục. Báo cáo giữ pinball, coverage hai phía, PIT, independence, bootstrap và mọi kết quả âm, không tự chốt mô hình.

Phase 7B đã được người dùng chạy xong và kiểm tra lại: 748/748 ngày mỗi khung, 688 ngày được chấm sau warmup. Theo quyết định khóa DEC-005, final test dùng **Empirical EWMA HL30 (1m)** và **Normal Mixture 2 HL30 hiệu chỉnh PIT quá khứ (5m)**. Đây là quyết định dựa trên development; 2025–2026 chưa được dùng để điều chỉnh mô hình.

## Phase 8: final test đã khóa

`configs/phase8_v1.json` cố định hai mô hình, 5 mức coverage, giai đoạn 2025-01-01–2026-07-17 và hash của hai báo cáo Phase 7B. Runner nối tiếp EWMA và lịch refit Mixture 5 phiên từ development (không reset ngày đầu final); mỗi fit mới chỉ dùng 60 phiên trước đó. PIT hiệu chỉnh ở 5m bắt đầu từ lịch sử Phase 7B và chỉ bổ sung quan sát của một phiên **sau khi** phiên đó được dự báo/chấm xong. Empirical HL30 ở 5m được giữ làm đối chứng cùng nến; 1m chỉ đánh giá mô hình đã khóa. Nếu fit 5m thất bại, job dừng với checkpoint, không thay mô hình ngầm.

Chạy `run_phase8.bat check` để kiểm tra chỉ-đọc, rồi `run_phase8.bat` trên máy dành cho tác vụ dài. Dự báo, điểm theo ngày, PIT 5m và checkpoint được lưu atomically tại `outputs/phase8_v1/<timeframe>/`; chạy lại cùng file để resume, **không xóa output**. Báo cáo cuối tại `report.json` gồm pinball, coverage, hai phía vượt band, PIT/independence, phân tách năm mô tả và so sánh 5m với Empirical. Không dùng kết quả final để thử tham số khác; gửi lại toàn bộ `outputs/phase8_v1/` để kiểm tra artifact và diễn giải kết quả một lần.

Phase 8 đã được người dùng chạy xong và kiểm tra lại 381/381 phiên mỗi khung. Kết luận và số liệu đầy đủ nằm trong [đánh giá final Phase 8](docs/phase8_final_assessment.md): 1m có coverage tổng thể gần danh nghĩa nhưng vượt band còn tụ thành cụm; 5m Mixture hiệu chỉnh PIT **kém hơn** Empirical HL30 trên primary pinball final (+0,2253% loss, bootstrap p=0,02249) và coverage 95% (94,678% so với 94,941%). Đây là kết quả âm của mô hình đã khóa, không phải lý do để chọn lại winner trên final test. Chưa triển khai Phase 9.

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
