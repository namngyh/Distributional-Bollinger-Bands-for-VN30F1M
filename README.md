# Distributional Bollinger Bands for VN30F1M

**Câu hỏi nghiên cứu:** phân phối xác suất nào của phần dư chuẩn hóa \(z_t\) (trong \(r=\mu+\sigma z\)) cho dự báo ngoài mẫu tốt nhất đối với lợi suất VN30F1M ở khung 1 phút và 5 phút? Đây là nghiên cứu thuần về dự báo phân phối; **tín hiệu giao dịch và backtest nằm ngoài phạm vi** (DEC-006).

**Trạng thái (2026-09-25):** Phase 0–8 hoàn tất và đã xác minh, kể cả lần đánh giá duy nhất trên tập kiểm thử cuối 2025-01-01–2026-07-17 ([đánh giá Phase 8](docs/phase8_final_assessment.md)). Phase 9 (chẩn đoán \(z_t\), so sánh mở rộng, mô phỏng Monte Carlo; mang tính khám phá) đang được đề xuất, chưa duyệt. Phase 10 (tổng hợp và tái lập) chưa bắt đầu.

Tài liệu chính:
- [Kế hoạch nghiên cứu](docs/research_plan.md): bảng phase, phương pháp, kết quả từng phase.
- [Bảng thuật ngữ](docs/thuat_ngu.md): thuật ngữ thống kê dùng trong tài liệu và tên tương ứng trong code.
- [Báo cáo kết quả chính thức](Bao_cao/bao_cao_ket_qua.tex): bản LaTeX để đọc và phản biện.
- [Data contract](docs/data_contract.md): nguồn dữ liệu và cách xây dựng mẫu.

Dữ liệu gốc `ohlc_export.csv` được giữ nguyên tại thư mục gốc và không đưa vào Git.

## Bối cảnh

Dải Bollinger truyền thống có dạng \(MA_t \pm k\sigma_t\), tức ngầm giả định lợi suất có phân phối chuẩn với khoảng cách \(k\sigma\) cố định. Lợi suất tài chính thường có **đuôi dày**, **độ lệch** và **cụm biến động** (giai đoạn biến động mạnh nối tiếp nhau), nên giả định này có thể đánh giá sai xác suất của các biến động cực trị.

Project thay dải truyền thống bằng **khoảng dự báo theo phân phối**, dựa trên phân vị của từng họ phân phối:

\[
L_t=\mu_t+\sigma_tF^{-1}(\alpha),\qquad U_t=\mu_t+\sigma_tF^{-1}(1-\alpha),
\]

với năm khoảng trung tâm 90%, 95%, 97,5%, 99% và 99,5%. Các họ được xét gồm: Chuẩn, Student-t, Student-t lệch, phân phối sai số tổng quát (GED), GED lệch, Normal Inverse Gaussian (NIG), Hyperbolic tổng quát (GH), hỗn hợp chuẩn 2 và 3 thành phần, và phân phối thực nghiệm (phi tham số).

Mỗi phân phối được đánh giá chủ yếu bằng **chất lượng dự báo ngoài mẫu**: tổn thất phân vị, tỷ lệ bao phủ, kiểm định độc lập của chuỗi vượt khoảng và PIT, trong thiết kế đánh giá cửa sổ trượt. Log-likelihood, AIC và BIC trong mẫu chỉ dùng để chẩn đoán.

## Tóm tắt kết quả đến Phase 8

- **\(z_t\) có đuôi dày:** phân phối chuẩn có tổn thất phân vị cao hơn phân phối thực nghiệm 2,3% (1m) và 3,3% (5m), và thiếu bao phủ ở đuôi.
- **Trên tập xác thực, không họ tham số nào tốt hơn phân phối thực nghiệm một cách thuyết phục:** chênh lệch tốt nhất khoảng 0,05% (1m) và 0,3% (5m), thường kèm tỷ lệ bao phủ thấp hơn mức danh nghĩa.
- **Mô hình σ quan trọng hơn lựa chọn \(F\):** đổi chu kỳ bán rã từ 60 xuống 30 phút giảm tổn thất khoảng 3% ở 1m.
- **Tập kiểm thử cuối:** ở 5m, hỗn hợp chuẩn hiệu chỉnh PIT kém hơn đối chứng phân phối thực nghiệm (+0,225% tổn thất, \(p=0{,}022\)). Ở 1m, tỷ lệ bao phủ sát mức danh nghĩa nhưng vượt khoảng tụ cụm.

## Hướng dẫn chạy

Chạy kiểm thử:

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
```

Chỉ kiểm tra dữ liệu (không ghi kết quả):

```powershell
$env:PYTHONPATH = 'src'
python -m distributional_bands.cli audit
```

Để tạo bộ mẫu nghiên cứu chính thức, chạy `run_prepare.bat`. Lệnh này ghi `outputs/data_v1/` và từ chối ghi đè thư mục đã tồn tại.

Trên máy chạy tác vụ dài (Windows, Python 3.11 trở lên), cài thư viện từ repository:

```powershell
python -m pip install -e .
```

Mọi script `.bat` dưới đây đều: kiểm tra môi trường, dữ liệu và dung lượng đĩa trước khi chạy; lưu tiến độ (checkpoint) sau mỗi ngày hoặc mỗi lần ước lượng; tự chạy tiếp từ điểm lưu nếu bị ngắt; từ chối chạy tiếp nếu dữ liệu, cấu hình hoặc mã nguồn khác với lúc bắt đầu. Tham số `check` chỉ kiểm tra, không tính toán. **Không xóa thư mục kết quả khi bị ngắt;** chỉ cần chạy lại cùng lệnh.

### Phase 3: mô hình tham chiếu

Cần `outputs/data_v1/` gồm hai file mẫu và `manifest.json`. Chạy `run_baseline.bat` (yêu cầu ít nhất 2 GiB trống). Kết quả: `outputs/baseline_v1/<khung>/`, dự báo theo ngày trong `predictions/`, `metrics.json` khi hoàn tất. Chỉ dự báo trên tập xác thực 2022–2024. Cấu hình: [baseline_v1.json](configs/baseline_v1.json).

### Phase 4–5: ước lượng phân phối và đánh giá cửa sổ trượt

`distributional_bands.distributions` cung cấp `fit_distribution(model, historical_residuals, config)` cho chín họ phân phối. Kết quả gồm hàm phân phối (`cdf`), hàm phân vị (`ppf`), log mật độ (`logpdf`), tham số và thông tin hội tụ. Đầu vào chỉ gồm phần dư quá khứ. Ước lượng thất bại được ghi rõ, không thay bằng phân phối chuẩn. Cấu hình: [distribution_fit_v2.json](configs/distribution_fit_v2.json), [walk_forward_v1.json](configs/walk_forward_v1.json).

Chạy `.\run_distribution_walkforward.bat` (kiểm tra NumPy/pandas/SciPy, yêu cầu ít nhất 4 GiB trống). Tác vụ có thể kéo dài nhiều giờ vì GH và 150 lần ước lượng lại mỗi khung. Kết quả: `outputs/distribution_wf_v1/<khung>/`. `metrics.json` gồm điểm trên mọi dự báo, điểm so sánh ghép cặp trên các nến mà cả chín họ đều có dự báo, và thứ hạng mô tả theo tổn thất phân vị. `fit_history.json` lưu tham số, cửa sổ ước lượng, trạng thái hội tụ và lỗi của từng lần ước lượng lại.

### Phase 6: so sánh trên tập xác thực

Chạy `run_selection.bat`. Script chỉ đọc DATA-V1, BASELINE-V1 và DISTRIBUTION-WF-V1; kết quả ở `outputs/selection_v1/<khung>/`. `report.json` gồm tổn thất phân vị trên cùng tập nến, tỷ lệ bao phủ và vượt khoảng hai phía, độ rộng khoảng, độ ổn định theo năm, kiểm định độc lập của chuỗi vượt khoảng trong từng phiên, histogram PIT, khoảng tin cậy bootstrap khối theo ngày và giá trị p hiệu chỉnh Holm so với phân phối thực nghiệm.

### Phase 7A: độ nhạy theo chu kỳ bán rã

Chạy `run_phase7a.bat`. [phase7a_v1.json](configs/phase7a_v1.json) cố định \(H\) = 30/60/120 phút giao dịch, cửa sổ ước lượng 60 phiên, ước lượng lại mỗi 5 phiên; mốc 60 phút dùng lại kết quả Phase 5–6. Kết quả ở `outputs/phase7a_v1/<khung>/hl<H>/` và `report.json`: xếp hạng trên 2022–2023, năm 2024 chỉ là kiểm tra ổn định hồi cứu.

*Chuyển đổi checkpoint:* nếu checkpoint Phase 7A được tạo trước bản sửa lỗi làm tròn PIT ngày 2022-11-16, `run_phase7a.bat check` sẽ báo cần chuyển đổi nhưng không ghi dữ liệu. Chạy lại `run_phase7a.bat` sau khi cập nhật mã: script xác minh toàn bộ hash, sao lưu metadata gốc vào `pit_boundary_migration_v1/`, chỉ cập nhật chữ ký mã nguồn và chạy tiếp. Dự báo và điểm đã lưu không bị tính lại hay xóa. Bản sửa chỉ chặn sai số CDF trong phạm vi `1e-12` sát 0 hoặc 1; sai số lớn hơn vẫn làm tác vụ dừng.

### Phase 7B: hiệu chỉnh xác suất bằng PIT quá khứ

Chạy `run_phase7b.bat`. [phase7b_v1.json](configs/phase7b_v1.json) chỉ dùng \(H=30\): lấy PIT của các dự báo hỗn hợp chuẩn trước ngày hiện tại, ước lượng hàm phân vị của PIT theo lịch sử mở rộng, rồi dùng hàm phân vị của hỗn hợp chuẩn hiện tại để tạo khoảng đã hiệu chỉnh. 60 ngày đầu là giai đoạn khởi động. Kết quả ở `outputs/phase7b_v1/<khung>/`.

### Phase 8: tập kiểm thử cuối

Chạy `run_phase8.bat`. [phase8_v1.json](configs/phase8_v1.json) cố định hai mô hình đã chọn theo DEC-005 (1m: phân phối thực nghiệm \(H=30\); 5m: hỗn hợp chuẩn 2 thành phần \(H=30\), hiệu chỉnh PIT), năm khoảng dự báo, giai đoạn 2025-01-01–2026-07-17 và hash của hai báo cáo Phase 7B. Ở 5m, phân phối thực nghiệm \(H=30\) là đối chứng trên cùng nến. Kết quả ở `outputs/phase8_v1/<khung>/`. Không dùng kết quả này để thử tham số khác.

Đã hoàn tất 381/381 phiên mỗi khung. Kết quả âm ở 5m là kết quả hợp lệ của mô hình đã chọn, không phải lý do để chọn lại mô hình trên chính tập này.

## Phase 9 (đề xuất, chưa duyệt)

Chẩn đoán \(z_t\) trên tập xác thực (tự tương quan của \(z\) và \(z^2\), tính mùa vụ trong phiên, PIT theo giờ và trạng thái biến động); so sánh chín họ với \(H=30\); bảng mô tả chín họ trên 2025–2026; mô phỏng Monte Carlo đo độ chính xác của ước lượng và ảnh hưởng của sai dạng mô hình (9E: 4.000 mẫu mô phỏng, 36.000 lần ước lượng, khoảng 16–20 giờ với một tiến trình); độ nhạy theo cách chuẩn hóa thang đo (9F). Mọi kết quả sẽ mang tính khám phá; DEC-005 và PHASE8-V1 giữ nguyên. Chi tiết trong [kế hoạch nghiên cứu](docs/research_plan.md).
