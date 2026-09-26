# Kế hoạch nghiên cứu — Dải Bollinger theo phân phối cho VN30F1M

Thuật ngữ trong tài liệu này theo [bảng thuật ngữ](thuat_ngu.md). Tên trong code và tên file giữ nguyên.

## Câu hỏi nghiên cứu và phạm vi

> **Phân phối xác suất nào của phần dư chuẩn hóa \(z_t\) cho dự báo ngoài mẫu tốt nhất đối với lợi suất VN30F1M ở khung 1 phút và 5 phút?**

Đây là nghiên cứu thuần về **dự báo phân phối**. Tín hiệu giao dịch, backtest, chi phí giao dịch và luật vào/ra lệnh **nằm ngoài phạm vi** (DEC-006, 2026-09-25). Dải giá chỉ là cách trình bày các khoảng dự báo, không phải công cụ giao dịch.

## Mô hình và nguyên tắc chọn mô hình

Tại thời điểm nến \(t\) kết thúc, ta dự báo phân phối của lợi suất kỳ sau:

\[
r_{t+1}=\log(C_{t+1}/C_t),\qquad r_{t+1}=\mu_{t+1\mid t}+\sigma_{t+1\mid t}\,z_{t+1}.
\]

Đối tượng so sánh là phân phối \(F\) của \(z\) (kỳ vọng 0, phương sai 1). Khi so các họ phân phối, \(\mu\) và \(\sigma\) phải giống nhau để khác biệt chỉ đến từ \(F\). Với hai phân vị dự báo \(q^{\text{dưới}}\) và \(q^{\text{trên}}\), dải giá là \(C_t e^{q^{\text{dưới}}}\) và \(C_t e^{q^{\text{trên}}}\). Khung 1m và 5m được nghiên cứu riêng; kết luận có thể khác nhau.

**Tiêu chí chính là chất lượng dự báo ngoài mẫu.** Log-likelihood, AIC và BIC trong mẫu chỉ dùng để chẩn đoán quá trình ước lượng và độ phức tạp.

Năm khoảng dự báo trung tâm: 90%, 95%, 97,5%, 99% và 99,5%. Ví dụ, khoảng 95% dùng phân vị 2,5% và 97,5%. Tỷ lệ vượt khoảng dưới và trên luôn được báo cáo riêng.

## Các phase và điều kiện chuyển bước

Bảng được sửa ngày 2026-09-25 theo DEC-006: bỏ phase "nghiên cứu giao dịch" (chưa từng triển khai), nên số phase trùng với tên đã dùng khi chạy (tập kiểm thử cuối là Phase 8).

| Phase | Nội dung | Điều kiện chuyển bước | Trạng thái |
|---|---|---|---|
| 0. Hợp đồng nghiên cứu | Chốt biến mục tiêu, thời điểm thông tin, tiêu chí chọn, trình tự thời gian | Định nghĩa được ghi lại và đánh phiên bản | ✅ Xong |
| 1. Kiểm tra dữ liệu | Cấu trúc, nguồn, phiên, khoảng trống, phiên đấu giá, bất thường, đáo hạn hợp đồng | Data contract và các điểm chưa biết được ghi rõ | ✅ Xong; múi giờ và đáo hạn còn mở |
| 2. Mẫu 1m/5m | Lợi suất liên tục trong phiên; nến 5m chỉ tạo từ đủ 5 nến 1m | Kiểm thử chống rò rỉ thông tin và kiểm tra gộp nến | ✅ Xong (DATA-V1) |
| 3. Mô hình tham chiếu | Chuẩn + σ EWMA, Chuẩn + σ cửa sổ cố định (kiểu Bollinger truyền thống), phân phối thực nghiệm + σ EWMA | Dự báo tham chiếu tái tạo được | ✅ Đã xác minh (BASELINE-V1) |
| 4. Ước lượng phân phối | Chuẩn, Student-t, GED, Student-t lệch, GED lệch, NIG, GH, hỗn hợp chuẩn 2/3 | Kiểm thử ước lượng, phân vị, hội tụ | ✅ Xong |
| 5. Đánh giá cửa sổ trượt | Dự báo 9 họ theo trình tự thời gian trên cùng \(z\) (σ EWMA, \(H=60\)); ước lượng lại chỉ bằng dữ liệu quá khứ | Dự báo ngoài mẫu và khả năng chạy tiếp được xác minh | ✅ Đã xác minh (DISTRIBUTION-WF-V1) |
| 6. So sánh phân phối | Tổn thất phân vị, tỷ lệ bao phủ, kiểm định độc lập, PIT, bootstrap so với phân phối thực nghiệm | Danh sách ứng viên rút gọn cho 1m/5m từ tập xác thực | ✅ Đã xác minh (SELECTION-V1) |
| 7. Tinh chỉnh | 7A: chu kỳ bán rã 30/60/120 phút; 7B: hiệu chỉnh xác suất bằng PIT quá khứ (thí nghiệm bổ sung) | Mô hình được cố định trước tập kiểm thử cuối | ✅ Đã xác minh; chọn mô hình theo DEC-005 |
| 8. Tập kiểm thử cuối | Đánh giá một lần 2025-01-01–2026-07-17 cho mô hình đã chọn | Báo cáo toàn bộ kết quả, kể cả kết quả âm | ✅ Đã xác minh (PHASE8-V1) |
| 9. Chẩn đoán \(z_t\), so sánh mở rộng và mô phỏng | Xem mục "Phase 9" | Mọi kết quả ghi rõ là mang tính khám phá | 🔄 9A, 9D xong; 9C, 9E, 9F đã duyệt và cài đặt (DEC-010), **chờ chạy** `run_phase9.bat` |
| 10. Tổng hợp và tái lập | Truy nguyên tệp kết quả, cấu hình, script; báo cáo trả lời câu hỏi nghiên cứu | Kết quả truy nguyên và tái tạo được; báo cáo cuối | ⏳ Chưa bắt đầu |

## Vai trò của từng phase với câu hỏi nghiên cứu

- **Phase 0–4:** nền tảng dữ liệu, mô hình tham chiếu và thư viện ước lượng; được dùng lại cho mọi bước sau.
- **Phase 5–6 là bằng chứng chính.** Chín họ được so trên cùng \(z\) (\(H=60\)), cùng tập nến, trong 748 phiên của tập xác thực. Không họ tham số nào tốt hơn phân phối thực nghiệm một cách rõ ràng. GH có tổn thất thấp nhất ở 1m nhưng không có ý nghĩa thống kê sau hiệu chỉnh Holm; hỗn hợp chuẩn 2/3 thành phần tốt hơn khoảng 0,28–0,29% ở 5m.
- **Phase 7A:** mô hình σ (chu kỳ bán rã) ảnh hưởng tới chất lượng khoảng dự báo nhiều hơn lựa chọn \(F\). Hạn chế: chỉ thử trên phân phối thực nghiệm và hỗn hợp chuẩn.
- **Phase 7B:** thí nghiệm bổ sung. Sau khi hiệu chỉnh bằng PIT, mô hình là dạng lai giữa hỗn hợp chuẩn và một ánh xạ thực nghiệm, không còn là một họ phân phối thuần. Kết quả dùng để chẩn đoán tính hiệu chuẩn ở đuôi, không trả lời câu hỏi "họ nào".
- **Phase 8:** lần đánh giá trên tập kiểm thử cuối duy nhất, nhưng phạm vi hẹp: chỉ 2 mô hình đã chọn. Ở 5m, mô hình hiệu chỉnh PIT kém hơn đối chứng phân phối thực nghiệm; ở 1m, tỷ lệ bao phủ tổng thể sát mức danh nghĩa nhưng vượt khoảng tụ cụm. Không có bảng xếp hạng 9 họ trên tập này.

### Phase 3: mô hình tham chiếu

`configs/baseline_v1.json` cố định lần chạy trên tập xác thực. Dữ liệu từ 2017 được cập nhật tuần tự; dự báo chỉ được ghi từ 2022-01-01 đến 2024-12-31. Tập kiểm thử cuối bắt đầu 2025-01-01. Ba mô hình:

- **Chuẩn + σ EWMA** (`normal_ewma`): \(\mu=0\); phương sai EWMA cập nhật sau khi quan sát lợi suất; \(H=60\) phút giao dịch.
- **Chuẩn + σ cửa sổ cố định** (`normal_rolling`): \(\mu=0\); σ là căn bậc hai của trung bình bình phương lợi suất trong 240 phút giao dịch gần nhất.
- **Phân phối thực nghiệm + σ EWMA** (`empirical_ewma`): phân vị mẫu của \(z=r/\sigma_{\text{EWMA}}\) trong tối đa 60 phiên trước, cố định trong ngày dự báo; cần ít nhất 20 phiên lịch sử.

Phân vị chuẩn lấy từ phân phối chuẩn tắc. Cả ba mô hình dùng cùng năm khoảng dự báo và lưu cả phân vị lợi suất lẫn dải giá. Dự báo cho nến hiện tại luôn được tạo trước khi lợi suất mục tiêu đi vào EWMA, cửa sổ cố định hoặc lịch sử thực nghiệm.

*Vận hành:* `run_baseline.bat` chạy hai khung theo thứ tự, ghi dự báo từng ngày và lưu checkpoint `latest.json` sau mỗi ngày. Khi chạy tiếp, chương trình đối chiếu hash của dữ liệu đầu vào, manifest, cấu hình, mã nguồn và mọi dự báo đã lưu. Người dùng đã chạy đầy đủ; cả hai khung hoàn tất 1.790 ngày, với 177.939 dự báo 1m và 34.344 dự báo 5m trong 2022–2024.

## Phương pháp ước lượng

Mô hình \(r_{t+1}=\mu_{t+1\mid t}+\sigma_{t+1\mid t}z_{t+1}\). Vòng so sánh đầu tiên đặt \(\mu=0\), dùng cùng một ước lượng σ EWMA trong mỗi khung, và ước lượng \(F\) trên \(z\). Tham số hình dạng được ước lượng trên cửa sổ dài hơn cửa sổ cập nhật σ. Mốc ban đầu là 60 phiên và ước lượng lại mỗi 5 phiên.

- **Chuẩn:** ước lượng hợp lý cực đại (MLE) dạng đóng.
- **Student-t, GED, Student-t lệch, GED lệch, NIG, GH:** MLE bằng tối ưu số có ràng buộc (L-BFGS-B), 3 điểm khởi tạo, chọn nghiệm có log-likelihood cao nhất. GH cần ràng buộc và kiểm tra nghiệm kỹ hơn.
- **Hỗn hợp chuẩn:** 2 thành phần ước lượng bằng thuật toán EM; 3 thành phần là phân tích độ nhạy. Dùng nhiều điểm khởi tạo, chặn dưới phương sai và trọng số, kiểm tra hội tụ.
- **Phân phối thực nghiệm:** phân vị mẫu của phần dư chuẩn hóa trong quá khứ; không giả định dạng phân phối.

NIG là trường hợp riêng của GH nhưng vẫn được so riêng, để xem tham số bổ sung của GH có cải thiện dự báo ngoài mẫu không. Mọi phân phối được chuẩn hóa về kỳ vọng 0, phương sai 1 trước khi tính khoảng dự báo.

### Phase 4A–4B: thư viện ước lượng

`src/distributional_bands/distributions.py` triển khai các họ nêu trên. GH và NIG giữ ràng buộc \(|b|<a\) qua một tham số tỷ lệ bị chặn. Phân vị của hỗn hợp chuẩn được tính bằng cách giải phương trình \(F(q)=p\). Kết quả lưu tham số, log-likelihood **của phân phối sau chuẩn hóa**, số điểm khởi tạo hội tụ và cảnh báo khi tham số chạm biên. Ước lượng thất bại được báo lỗi, không thay thế ngầm bằng phân phối chuẩn.

Sau khi ước lượng, mỗi phân phối được biến đổi tuyến tính về kỳ vọng 0, phương sai 1 bằng **mô-men lý thuyết của chính nó**. Như vậy đây là MLE/EM cho họ gốc rồi chuẩn hóa, không phải tối ưu lại likelihood dưới ràng buộc về kỳ vọng và phương sai.

Cấu hình [distribution_fit_v1.json](../configs/distribution_fit_v1.json) cố định sáu ứng viên của Phase 4A. Ngưỡng hội tụ EM `1e-5` được chọn sau một lần chạy thử rất nhỏ, để tránh hàng trăm vòng lặp khi hai thành phần gần như không phân biệt được; ngưỡng này **không** được chọn theo kết quả ngoài mẫu. Phase 4B mở rộng bằng [distribution_fit_v2.json](../configs/distribution_fit_v2.json): Student-t lệch, GED lệch (dạng hai nửa, two-piece) và hỗn hợp chuẩn 3 thành phần. Phân phối lệch dạng hai nửa dùng nửa trái và nửa phải của phân phối gốc với tham số thang đo khác nhau, sau đó chuẩn hóa; khi tham số lệch bằng 0 thì trở về phân phối gốc. Hỗn hợp 3 thành phần là phân tích độ nhạy, không tự động được ưu tiên hơn mô hình ít tham số.

Tham số hóa theo tài liệu SciPy: [GH](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.genhyperbolic.html), [NIG](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.norminvgauss.html), [GED](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.gennorm.html).

## Tiêu chí đánh giá

- **Tiêu chí chính:** tổn thất phân vị trung bình trên 10 phân vị đuôi đã định trước (hai cận của 5 khoảng), trọng số bằng nhau, tính trên cùng tập nến.
- **Tiêu chí phụ:** điểm khoảng (interval score), sai lệch tỷ lệ bao phủ và điểm log dự báo khi phù hợp.
- **Kiểm tra bổ sung:** kiểm định độc lập của chuỗi vượt khoảng, PIT, độ ổn định theo năm, giờ và trạng thái biến động, tỷ lệ ước lượng thất bại.
- Nếu khác biệt nằm trong phạm vi bất định thống kê, ưu tiên mô hình đơn giản hơn.

## Chia dữ liệu và nguyên tắc thời gian

Người dùng đã chốt: tập xác thực đến hết 2024; tập kiểm thử cuối từ 2025-01-01 đến ngày cuối dữ liệu hiện có (2026-07-17). Không dùng tập kiểm thử cuối để chọn tham số, mô hình σ hoặc phân phối. Nếu dữ liệu được cập nhật, ranh giới vẫn bắt đầu 2025-01-01; mọi thay đổi phạm vi phải được quyết định riêng.

Mỗi dự báo chỉ dùng thông tin có sẵn khi nến nguồn đã kết thúc. Dự báo, biến mục tiêu, hash dữ liệu, hash chính sách dữ liệu, cấu hình và phiên bản mã phải đi cùng tệp kết quả. Các tác vụ ước lượng và đánh giá dài được đóng gói thành `.bat` để người dùng chạy theo `PROCESS.md`.

### Phase 5: đánh giá cửa sổ trượt trên tập xác thực

[walk_forward_v1.json](../configs/walk_forward_v1.json) cố định \(H=60\) phút giao dịch và giai đoạn khởi động σ 240 phút như mô hình tham chiếu. Tham số được ước lượng trên phần dư của **60 phiên trước ngày dự báo** và ước lượng lại mỗi 5 phiên. Vòng lặp chỉ đọc dữ liệu đến 2024-12-31. Tại mỗi nến, σ EWMA chỉ dùng lợi suất của các nến trước; mô hình chỉ được ước lượng từ các ngày trước ngày dự báo. Nếu ước lượng thất bại, mô hình đó bỏ trống dự báo cho tới lần ước lượng lại tiếp theo và lỗi được ghi vào `fit_history.json`; không thay bằng phân phối chuẩn.

`metrics.json` báo cáo tổn thất phân vị, tỷ lệ bao phủ và tỷ lệ vượt khoảng theo từng mức và từng mô hình, cùng điểm so sánh ghép cặp chỉ trên các nến mà mọi ứng viên đều có dự báo. Thứ hạng trong `paired_pinball_ranking` chỉ mang tính mô tả.

*Vận hành:* mỗi lần ước lượng lại và mỗi ngày dự báo đều lưu checkpoint; `run_distribution_walkforward.bat` chạy 1m rồi 5m.

**Kết quả:** người dùng đã chạy DISTRIBUTION-WF-V1. Cả hai khung hoàn tất 748/748 ngày (2022-01-04 đến 2024-12-31); mỗi ứng viên được ước lượng 150 lần mỗi khung, không lần nào thất bại. Thứ hạng mô tả: GH đứng đầu ở 1m, hỗn hợp chuẩn 3 thành phần ở 5m, nhưng chỉ tốt hơn phân phối thực nghiệm khoảng 0,06% và 0,29%.

### Phase 6: đánh giá và quyết định trên tập xác thực

`configs/selection_v1.json` cố định mô hình tham chiếu `empirical_ewma`, bootstrap khối 5 phiên với 2.000 lần lặp, seed, 10 ô histogram PIT và ranh giới tập kiểm thử cuối. Phân tích gồm cả ba mô hình tham chiếu và chín họ phân phối; trước khi chấm điểm, ngày, phiên, thời điểm và biến mục tiêu được đối chiếu giữa các tệp.

Các chỉ tiêu:
- tổn thất phân vị trung bình trên năm khoảng, trọng số bằng nhau, tính trên cùng tập nến;
- tỷ lệ bao phủ, tỷ lệ vượt khoảng dưới/trên và độ rộng khoảng theo từng mức;
- tổn thất theo năm;
- kiểm định độc lập Markov của chuỗi vượt khoảng trong cùng phiên (bỏ giá trị p nếu tần số kỳ vọng của một ô nhỏ hơn 5);
- histogram PIT của chín họ, tính từ CDF của đúng lần ước lượng quá khứ tương ứng. Histogram PIT chỉ dùng để chẩn đoán; không tính giá trị p theo giả định độc lập cùng phân phối, vì có phụ thuộc chuỗi và tham số được ước lượng lại.

Chênh lệch tổn thất của mỗi họ so với phân phối thực nghiệm được suy luận bằng bootstrap khối vòng theo **ngày giao dịch** (khối 5 ngày), lấy tỷ số tổng tổn thất trên tổng số nến ở mỗi mẫu bootstrap. Báo cáo khoảng tin cậy 95% chưa hiệu chỉnh và giá trị p hai phía đã hiệu chỉnh Holm trên chín ứng viên. Độ dài khối là một giả định cố định, không bảo đảm bao quát mọi phụ thuộc dài hạn. Không chọn mô hình chỉ dựa vào giá trị p: cần xét cả độ lớn khác biệt, tính hiệu chuẩn, PIT, độ ổn định, tỷ lệ ước lượng thất bại và độ phức tạp.

**Kết quả:** người dùng đã chạy SELECTION-V1; cả hai báo cáo hoàn tất 748/748 ngày và khớp khi tính lại. Ở 1m, GH có tổn thất thấp nhất nhưng không có ý nghĩa sau hiệu chỉnh Holm (\(p=0{,}145\)); hỗn hợp chuẩn 3 thành phần tốt hơn khoảng 0,045% (\(p=0{,}007\)). Ở 5m, hỗn hợp 3 và 2 thành phần tốt hơn khoảng 0,293% và 0,282% (\(p\approx0{,}005\)); hỗn hợp 2 thành phần đơn giản hơn và có tỷ lệ bao phủ 95% tốt hơn (94,68% so với 94,11%; phân phối thực nghiệm 94,93%). Các cải thiện rất nhỏ và vượt khoảng vẫn tụ cụm. Người dùng đồng ý danh sách rút gọn: phân phối thực nghiệm, hỗn hợp 3 thành phần (1m), hỗn hợp 2 thành phần (5m).

### Phase 7A: phân tích độ nhạy theo chu kỳ bán rã

Người dùng duyệt lưới \(H\) = **30/60/120 phút giao dịch**, giữ cửa sổ ước lượng 60 phiên và ước lượng lại mỗi 5 phiên. `configs/phase7a_v1.json` cố định lựa chọn này. Giai đoạn xếp hạng là 2022–2023; năm 2024 chỉ là kiểm tra ổn định hồi cứu, vì danh sách rút gọn đã được chọn khi nhìn toàn bộ 2022–2024 nên 2024 không còn là dữ liệu độc lập. Mốc \(H=60\) dùng lại kết quả Phase 5–6; chỉ chạy mới \(H=30\) và \(H=120\). Khi đổi \(H\), cả σ, phần dư chuẩn hóa và các phân vị đều được tính lại theo trình tự thời gian.

Báo cáo xếp hạng theo tổn thất phân vị trung bình trên **cùng tập nến 2022–2023**, kèm tỷ lệ bao phủ, vượt khoảng hai phía, kiểm định độc lập, PIT, năm 2024 và bootstrap; giá trị p hiệu chỉnh Holm cho năm cấu hình so với phân phối thực nghiệm \(H=60\). Các giá trị p mang tính khám phá vì danh sách rút gọn xuất phát từ cùng tập xác thực.

**Kết quả:** cả bốn cấu hình mới hoàn tất 748/748 ngày, mỗi cấu hình 150 lần ước lượng, không lần nào thất bại. \(H=30\) có tổn thất thấp nhất ở cả hai khung trong 2022–2023, và xu hướng này lặp lại ở 2024. Tuy nhiên hỗn hợp chuẩn với \(H=30\) có tỷ lệ bao phủ thấp hơn phân phối thực nghiệm: trên toàn tập xác thực, khoảng 95% ở 1m đạt 94,742% so với 94,990%; ở 5m đạt 93,964% so với 94,925%; khoảng 99,5% của hỗn hợp chuẩn ở 5m chỉ đạt 99,065%. Hỗn hợp chuẩn chỉ tốt hơn phân phối thực nghiệm (cùng \(H=30\)) khoảng 0,026% ở 1m và 0,294% ở 5m; chênh lệch ở 1m không vượt quá bất định thống kê.

*Ghi chú kỹ thuật:* checkpoint Phase 7A tạo trước khi sửa lỗi làm tròn PIT ngày 2022-11-16 đã được chuyển đổi có kiểm soát; chi tiết trong `PROCESS.md` và README.

### Phase 7B: hiệu chỉnh xác suất bằng PIT quá khứ (thí nghiệm bổ sung)

`configs/phase7b_v1.json` chỉ dùng \(H=30\); phân phối thực nghiệm là đối chứng; hỗn hợp 3 thành phần ở 1m và 2 thành phần ở 5m. 60 ngày đầu của tập xác thực là giai đoạn khởi động; lịch sử hiệu chỉnh mở rộng dần theo các ngày đã qua. Không ước lượng lại hỗn hợp chuẩn, không đổi cửa sổ hay tần suất ước lượng.

Với phân phối dự báo gốc \(F_t\), mỗi quan sát cho một giá trị PIT \(u_i=F_i(r_{i+1})\). Trước ngày \(d\), chỉ các \(u_i\) của những ngày trước \(d\) được dùng để ước lượng hàm phân vị của PIT, \(\hat H_{d-1}^{-1}(p)\). Phân vị đã hiệu chỉnh ở mức \(p\) là \(F_d^{-1}\bigl(\hat H_{d-1}^{-1}(p)\bigr)\). Xác suất hiệu chỉnh bị chặn trong \((10^{-9},\,1-10^{-9})\) để tránh phân vị vô hạn, và ánh xạ phải đơn điệu. Dữ liệu của ngày hiện tại chỉ được thêm vào lịch sử sau khi ngày đó đã được dự báo và chấm điểm. Hiệu chỉnh này không bảo đảm tỷ lệ bao phủ khi quan sát phụ thuộc theo thời gian.

Báo cáo so ba phương án trên **cùng ngày và cùng nến sau khởi động**: phân phối thực nghiệm, hỗn hợp chuẩn gốc và hỗn hợp chuẩn đã hiệu chỉnh.

**Kết quả:** mỗi khung hoàn tất 748/748 ngày, 688 ngày được chấm điểm sau khởi động. Trên giai đoạn xếp hạng 2022–2023, hỗn hợp 3 thành phần gốc ở 1m chỉ tốt hơn phân phối thực nghiệm 0,023% và không vượt bất định thống kê; bản hiệu chỉnh kém hơn 0,003%. Ở 5m, hỗn hợp 2 thành phần gốc tốt hơn 0,267% nhưng tỷ lệ bao phủ 95% chỉ đạt 93,834%; bản hiệu chỉnh tốt hơn 0,131% và đưa tỷ lệ bao phủ về 94,928% (\(p_\text{Holm}=0{,}023\)).

### Phase 8: đánh giá một lần trên tập kiểm thử cuối

DEC-005 chọn trước khi mở tập kiểm thử cuối: **1m — phân phối thực nghiệm, \(H=30\)**; **5m — hỗn hợp chuẩn 2 thành phần, \(H=30\), hiệu chỉnh PIT bằng các phiên trước**. `configs/phase8_v1.json` giữ nguyên năm khoảng dự báo, cửa sổ ước lượng 60 phiên, lịch ước lượng lại mỗi 5 phiên, giai đoạn 2025-01-01–2026-07-17 và hash của hai báo cáo Phase 7B. Ở 5m, lịch ước lượng lại tiếp nối từ 2022–2024 (không đặt lại ở phiên đầu 2025). σ EWMA chỉ dùng lợi suất của các nến trước; mỗi lần ước lượng mới dùng 60 phiên trước ngày dự báo. Lịch sử PIT bắt đầu từ 748 phiên của tập xác thực và chỉ nhận thêm dữ liệu mới sau khi ngày tương ứng đã được chấm điểm. Nếu ước lượng thất bại, chương trình dừng; không thay mô hình.

Báo cáo cuối gồm tổn thất phân vị trung bình, tỷ lệ bao phủ, vượt khoảng hai phía, kiểm định độc lập, PIT và phân tách mô tả theo 2025/2026. Ở 5m có đối chứng phân phối thực nghiệm \(H=30\) trên cùng nến và bootstrap khối 5 ngày; ở 1m chỉ chấm mô hình đã chọn. Kết quả chi tiết ở [đánh giá Phase 8](phase8_final_assessment.md).

## Phase 9: chẩn đoán \(z_t\), so sánh mở rộng và mô phỏng

9A đã được người dùng duyệt và hoàn thành ngày 2026-09-25. Các mục 9B–9F là đề xuất, **chưa phải cho phép triển khai**; mỗi mục cần thảo luận và duyệt riêng. Vì tập kiểm thử cuối 2025–2026 đã dùng một lần, mọi kết quả Phase 9 đều **mang tính khám phá**. DEC-005 và PHASE8-V1 giữ nguyên.

- **9A — Chẩn đoán \(z_t\) trên tập xác thực 2022–2024 (đã xong, PHASE9A-V1).**
  - *Cách làm:* `src/distributional_bands/phase9a.py`, cấu hình `configs/phase9a_v1.json`. Chỉ đọc dự báo đã xác minh (đối chiếu hash từng file với checkpoint), không ước lượng lại, không đọc dữ liệu từ 2025. Nguồn chính: \(z\) với σ \(H=30\) của Phase 7A, kèm phân vị của phân phối thực nghiệm và hỗn hợp chuẩn; \(z\) với \(H=60\) của Phase 5 để so sánh. Chẩn đoán gồm: tự tương quan của \(z\) và \(z^2\) chỉ trên các cặp nến trong cùng phiên; trung bình \(z^2\) theo khối 15 phút với sai số chuẩn gom cụm theo ngày; tự tương quan của \(z^2\) sau khi chia \(z\) cho căn bậc hai trung bình \(z^2\) theo khối giờ (điều chỉnh mùa vụ, tính trong mẫu); tỷ lệ bao phủ theo khối giờ, theo ngũ phân vị của σ và theo \(|z|\) của nến trước. Kết quả ở `outputs/phase9a_v1/<khung>/` và mục 8 của [báo cáo](../Bao_cao/bao_cao_ket_qua.tex).
  - *Kết quả 1 — tính mùa vụ trong phiên mà σ EWMA không theo kịp:* trung bình \(z^2\) tăng gần như đơn điệu trong ngày, từ khoảng 0,46–0,48 (1m) và 0,57 (5m) đầu phiên sáng lên khoảng 2,0 (1m) và 2,5–2,8 (5m) lúc 14:00–14:29. Nguyên nhân: σ EWMA chạy liên tục qua đêm nên đầu phiên sáng kế thừa mức biến động cao của cuối phiên chiều hôm trước (1m, 09:00: σ = 7,83×10⁻⁴ so với lợi suất thực tế 5,72×10⁻⁴), còn cuối phiên chiều không theo kịp mức biến động tăng (14:15: 7,72×10⁻⁴ so với 11,9×10⁻⁴). Tỷ lệ bao phủ 95% của phân phối thực nghiệm giảm từ 98,7% xuống 87,2% (1m) và từ 98,8% xuống 85,3% (5m) trong ngày; tỷ lệ tổng thể gần 95% chỉ do bù trừ. Hỗn hợp chuẩn có cùng mô hình sai lệch, nên nguồn gốc là σ chứ không phải \(F\).
  - *Kết quả 2 — phụ thuộc chuỗi của \(z^2\):* ở 5m (\(H=30\)), điều chỉnh mùa vụ làm thống kê \(Q\) (30 hoặc 12 độ trễ, dạng Box–Pierce) giảm từ 119 xuống 7, dưới ngưỡng tham chiếu 21,0. Ở 1m, \(Q\) giảm 79% (6.632 xuống 1.389), nhưng tự tương quan ở độ trễ 1–4 vẫn khoảng 0,03–0,05, và sau một nến có \(|z|\ge3\), tỷ lệ bao phủ 95% của nến kế tiếp chỉ 88,6%: còn cụm biến động ngắn hạn. \(H=30\) để lại ít phụ thuộc hơn \(H=60\).
  - *Kết quả 3 — dạng đuôi:* sau điều chỉnh mùa vụ, độ nhọn vượt chuẩn gần như không đổi (1m: 4,65 → 4,35; 5m: 5,34 → 5,58). Tính mùa vụ chủ yếu ảnh hưởng tới thang đo của \(z\) theo giờ; đuôi dày là đặc tính riêng của \(z\).
  - *Quan sát gợi ý (chưa kiểm định):* độ lệch chuẩn hai thành phần của hỗn hợp chuẩn 2 thành phần gần với \(\sqrt{\overline{z^2}}\) của đầu phiên sáng và cuối phiên chiều; hỗn hợp chuẩn có thể đang mô tả một phần sự trộn lẫn các mức biến động trong ngày.
  - *Hệ quả:* nguồn sai lệch hiệu chuẩn lớn nhất là tính mùa vụ trong phiên của σ, lớn hơn nhiều mọi khác biệt giữa các họ \(F\) ở Phase 6. Đề xuất ưu tiên **9D trước 9B**.
- **9B — So sánh 9 họ với \(H=30\) trên tập xác thực:** được 9D bao gồm (9D so 9 họ trên \(z\) với σ đã điều chỉnh mùa vụ, \(H=30\) và \(H=60\)). Bản với σ chưa điều chỉnh chỉ cần nếu muốn đối chiếu riêng.
- **9C — Bảng mô tả 9 họ trên 2025–2026:** chỉ để xem thứ hạng có ổn định sang giai đoạn mới không. Không chọn lại mô hình và không gọi là kiểm thử độc lập.
- **9D — σ có điều chỉnh mùa vụ trong phiên (đã duyệt 2026-09-25, DEC-008; đã chạy xong và xác minh 2026-09-26, PHASE9D-V1).**
  - *Mô hình:* \(\sigma_t = s_{b(t)}\,\tilde\sigma_t\). Hệ số mùa vụ \(s_b\) của khối 15 phút \(b\) (theo giờ bắt đầu của nến mục tiêu) là \(\sqrt{\overline{r^2_b}/\overline{r^2}}\), tính trên **250 phiên liền trước ngày dự báo**, cập nhật mỗi ngày; khối có dưới 20 quan sát hoặc lịch sử dưới 20 phiên dùng hệ số 1 (chỉ xảy ra trong giai đoạn khởi động, không được chấm điểm). \(\tilde\sigma_t\) là EWMA của \(r/s_b\) trên các nến trước \(t\), với chu kỳ bán rã **\(H=30\) và \(H=60\)**. Giờ của nến mục tiêu biết trước nên dự báo vẫn đúng trình tự thời gian.
  - *Đánh giá:* trên \(z=r/\sigma\) mới, ước lượng lại **cả 9 họ** cùng phân phối thực nghiệm (cửa sổ 60 phiên, ước lượng lại mỗi 5 phiên, cùng cấu hình `distribution_fit_v2.json`), nên 9D bao gồm luôn nội dung của 9B. Báo cáo so ghép cặp với **phân phối thực nghiệm, σ \(H=30\) chưa điều chỉnh** (Phase 7A) và giữa các họ với nhau ở cùng \(H\): tổn thất phân vị trung bình (xếp hạng 2022–2023, năm 2024 hồi cứu), tỷ lệ bao phủ tổng thể và theo khối giờ, kiểm định độc lập, PIT, bootstrap khối theo ngày với hiệu chỉnh Holm.
  - *Cài đặt:* `src/distributional_bands/phase9d.py`, `phase9d_report.py`, `configs/phase9d_v1.json`, `run_phase9d.bat`, `tests/test_phase9d.py`. Checkpoint sau mỗi lần ước lượng và mỗi ngày; chạy tiếp được; ước lượng thất bại được ghi lại, không thay thế ngầm.
  - *Chi phí (đo trên dữ liệu thật ngày 2026-09-25):* mỗi lần ước lượng 9 họ khoảng 50 giây (1m) và 7 giây (5m); mỗi ngày dự báo dưới 1 giây. Tổng khoảng **5 giờ** với một tiến trình (1m khoảng 2,2 giờ mỗi \(H\); 5m khoảng 20 phút mỗi \(H\)).
  - *Chạy thử:* 5 ngày đầu 2022 trên dữ liệu thật chạy đúng; hệ số mùa vụ ước lượng từ năm 2021 thấp ở đầu phiên sáng (khoảng 0,76–0,91) và cao ở cuối phiên chiều (khoảng 1,20–1,26).
  - *Kết quả (người dùng chạy xong 2026-09-26; 4 checkpoint 748/748, 2 báo cáo tính lại khớp):*
    - Phân phối thực nghiệm + σ mùa vụ giảm tổn thất phân vị so với tham chiếu (thực nghiệm, σ \(H=30\) chưa điều chỉnh) **−7,38%** (1m, \(H=30\)) và **−9,63%** (5m, \(H=60\)) trên 2022–2023; năm 2024 hồi cứu: −7,44% và −8,53%. Ở 1m, cả 20 cấu hình mùa vụ tốt hơn tham chiếu với \(p_\text{Holm}\approx0{,}01\).
    - Tỷ lệ bao phủ 95% theo khối giờ: 93,3–96,3% (trước: 85–99%). Tụ cụm giảm nhưng ở 1m vẫn còn (p kiểm định độc lập từ \(10^{-76}\) lên \(10^{-44}\)).
    - \(H\) tốt nhất: 30 ở 1m, 60 ở 5m.
    - So các họ ở 1m (cùng \(H\), Holm trên 9 họ): không họ nào tốt hơn phân phối thực nghiệm có ý nghĩa (tốt nhất −0,04 đến −0,09%, \(p_\text{Holm}\ge0{,}11\)); Chuẩn kém +1,2% (\(p=0{,}004\)); GED lệch kém +0,12% (\(p=0{,}03\), \(H=30\)).
    - 5m: hỗn hợp 3 thành phần ước lượng thất bại 6 lần mỗi \(H\) (2 lần trong giai đoạn xếp hạng ở \(H=30\)); theo quy tắc định trước và quyết định của người dùng (DEC-009), 5m **chỉ báo cáo mô tả**, không xếp hạng ghép cặp hay suy luận. Mô tả: với \(H=60\), NIG/GED/GH thấp hơn thực nghiệm khoảng 0,2–0,25% tổn thất nhưng bao phủ 90–95% thấp hơn danh nghĩa.
    - Chi tiết, bảng và hình: mục 9 của [báo cáo](../Bao_cao/bao_cao_ket_qua.tex).
  - Kết quả mang tính khám phá; chỉ khẳng định được trên dữ liệu sau 2026-07-17.
- **9E — Mô phỏng Monte Carlo kiểm tra độ chính xác của ước lượng và ảnh hưởng của sai dạng mô hình** (thêm 2026-09-25). Hiện chưa có bước nào đo độ chính xác của ước lượng; các unit test chỉ kiểm tra tính đúng về mặt số học (CDF và hàm phân vị khớp nhau, mô-men sau chuẩn hóa, hội tụ). 9E chỉ dùng dữ liệu mô phỏng hoặc lấy mẫu lại từ \(z\) của tập xác thực, **không dùng tập kiểm thử cuối**.
  - *Thiết kế:* 2 khung, cỡ mẫu \(n\) bằng trung vị cửa sổ ước lượng thực tế (1m: 14.271; 5m: 2.753) × 10 phân phối sinh mẫu × \(R=200\) lần lặp. Mười phân phối sinh mẫu gồm 9 họ tại tham số bằng trung vị của 150 lần ước lượng ở Phase 5 (với hỗn hợp chuẩn, sắp thành phần theo σ để tránh hoán đổi nhãn), cộng 1 phân phối thực nghiệm lấy mẫu lại có hoàn lại (bootstrap độc lập cùng phân phối) từ \(z\) của tập xác thực (\(H=60\)), đã chuẩn hóa về kỳ vọng 0, phương sai 1. Mỗi mẫu được ước lượng bằng cả 9 họ và phân vị thực nghiệm, dùng đúng hàm `fit_distribution` và cấu hình `distribution_fit_v2.json` của Phase 5.
  - *9E-a, độ chính xác khi mô hình đúng dạng* (phân phối sinh mẫu trùng họ ước lượng): độ chệch và RMSE của từng tham số; tỷ lệ chạm biên và ước lượng thất bại; độ chệch và RMSE của 10 phân vị chuẩn hóa; hiệu quả tương đối (tỷ số RMSE phân vị so với phân vị thực nghiệm). Chỉ tiêu cuối cho biết, ở cỡ mẫu này, mô hình tham số đúng dạng có thực sự chính xác hơn phân vị thực nghiệm hay không.
  - *9E-b, ảnh hưởng của sai dạng* (phân phối sinh mẫu khác họ ước lượng): sai lệch phân vị so với phân vị thật; tỷ lệ bao phủ đúng của 5 khoảng, tính bằng CDF của phân phối sinh mẫu; tổn thất phân vị vượt mức so với phân vị thật, tính trên một mẫu đánh giá cố định \(10^6\) điểm cho mỗi phân phối sinh mẫu. Kết quả là thứ hạng các họ theo từng phân phối sinh mẫu.
  - *9E-c (tùy chọn), bootstrap trên cửa sổ thật:* 3 cửa sổ 60 phiên mỗi khung × \(B=100\) mẫu bootstrap × 9 họ, để có khoảng bất định của tham số và phân vị trên dữ liệu thật.
  - *Quy mô:* 9E-a/b gồm 4.000 mẫu mô phỏng, 36.000 lần ước lượng tham số và 4.000 lần tính phân vị thực nghiệm; 9E-c gồm 600 mẫu và 5.400 lần ước lượng.
  - *Chi phí (đo trên máy cục bộ ngày 2026-09-25, một tiến trình):* ước lượng đủ 9 họ mất khoảng 5,5 giây mỗi mẫu với \(n=2.753\) và 23,7 giây với \(n=14.271\); GH chiếm khoảng 75–80% thời gian. 9E-a/b cần khoảng 16–20 giờ với một tiến trình, hoặc khoảng 2,5–3 giờ với 8 tiến trình song song. 9E-c cần khoảng 2,5 giờ với một tiến trình. Nên chạy thử với \(R=20\) trước (khoảng 10% chi phí).
  - *Vận hành:* seed xác định theo (khung, phân phối sinh mẫu, lần lặp); lưu checkpoint sau mỗi mẫu; chạy tiếp được theo hash mã và cấu hình; `.bat` do người dùng chạy. Ước lượng thất bại, ví dụ hỗn hợp 3 thành phần chạm chặn dưới của trọng số khi dữ liệu không phải hỗn hợp (đã thấy khi đo thời gian), được ghi lại như một kết quả, không thay thế ngầm.
- **9F — Độ nhạy theo cách chuẩn hóa thang đo** (thêm 2026-09-25). Hiện mỗi phân phối sau ước lượng bị ép về phương sai 1 bằng mô-men lý thuyết của nó, trong khi \(z\) ngoài mẫu có độ lệch chuẩn 1,018 (1m) và 1,076 (5m). Với Student-t có bậc tự do gần 3, cách chuẩn hóa này làm khoảng 90–95% quá hẹp. 9F so lại 9 họ khi giữ tham số thang đo đã ước lượng, hoặc chuẩn hóa theo phân vị, để tách sai số do dạng \(F\) khỏi sai số do thang đo σ. Chỉ dùng tập xác thực; mang tính khám phá.

### Cài đặt 9C, 9E, 9F (người dùng duyệt 2026-09-26, DEC-010; chạy tuần tự bằng `run_phase9.bat`)

- **9F** (`phase9f.py`, `configs/phase9f_v1.json`): không ước lượng lại. Dùng đúng các lần ước lượng và σ của 9D (\(H=30\) và \(H=60\)); với mỗi họ, so hai cách tạo phân vị: chuẩn hóa phương sai bằng 1 theo mô-men lý thuyết (như 9D) và giữ nguyên tham số vị trí và thang đo đã ước lượng (\(q = \sigma(m + s\,q_\text{chuẩn})\)). So ghép cặp từng họ trên các ngày họ đó có dự báo, bootstrap khối theo ngày, hiệu chỉnh Holm trên 9 họ. Chạy thử 5m: giữ thang đo đưa tỷ lệ bao phủ 95% về khoảng 95,0–95,5% (chuẩn hóa: 92,9–94,8%). Vài phút.
- **9C** (`phase9c.py`, `configs/phase9c_v1.json`): 2025-01-02–2026-07-17, chỉ mô tả, không giá trị p, không chọn lại mô hình. σ điều chỉnh mùa vụ với \(H\) tốt nhất từ 9D (1m: 30; 5m: 60), ước lượng 9 họ và phân phối thực nghiệm như 9D. Tham chiếu: phân phối thực nghiệm σ \(H=30\) chưa điều chỉnh từ Phase 8 trên cùng nến. Báo cáo thêm tương quan hạng giữa thứ hạng trên tập xác thực và trên giai đoạn này. Khoảng 1–1,5 giờ.
- **9E** (`phase9e.py`, `configs/phase9e_v1.json`): điều chỉnh so với thiết kế ban đầu: phân phối sinh mẫu lấy từ **9D** (σ đã điều chỉnh; 1m \(H=30\), 5m \(H=60\)) thay vì Phase 5, dùng **lần ước lượng đại diện** (lần có vectơ 10 phân vị gần trung vị nhất) thay vì trung vị từng tham số để giữ tham số hợp lệ; bỏ phần tùy chọn 9E-c. Quy mô 2 khung × 10 phân phối sinh mẫu × \(R=200\); \(n\) = trung vị cỡ cửa sổ 9D (1m 14.274; 5m 2.756). Mỗi trường hợp là một file riêng (chạy tiếp được), chạy song song (mặc định số luồng CPU − 2). CDF thật tính trên lưới 12.001 điểm trong \([-30, 30]\); tổn thất phân vị vượt mức so với phân vị thật tính qua tích phân của CDF. Đo trên máy này: khoảng 10 giây mỗi trường hợp 5m và 68 giây mỗi trường hợp 1m (một luồng); ước tính 5–7 giờ với 10 tiến trình trên CPU i5-1235U.
- Lưu ý khi đọc 9E: sau khi chuẩn hóa phương sai về 1, phân vị của họ Chuẩn không phụ thuộc dữ liệu, nên họ Chuẩn cho sai số 0 khi phân phối sinh mẫu là chuẩn; các họ khác chỉ ước lượng tham số hình dạng.

## Quy tắc chạy và lưu tiến độ

AI tự chạy các kiểm tra nhẹ: unit test, chạy thử quy mô nhỏ, kiểm tra dữ liệu, đo thời gian nhỏ. Các tác vụ ước lượng và đánh giá dài được đóng gói thành `.bat` dùng đường dẫn tương đối để chạy trên máy khác. Mỗi tác vụ phải kiểm tra checkpoint hợp lệ và chạy tiếp trước khi bắt đầu mới; lưu tiến độ định kỳ, ít nhất sau mỗi cửa sổ hoặc cấu hình hoàn tất, bằng cách ghi qua file tạm rồi thay thế. Checkpoint và manifest ghi hash của dữ liệu, cấu hình, mã nguồn, mã lần chạy và vị trí tiến độ để tránh mất hoặc ghi trùng kết quả.

## Trạng thái hiện tại

Phase 0–2 đã triển khai và kiểm thử. Phase 3, 5, 6, 7A, 7B và 8 đã được người dùng chạy đầy đủ cho cả 1m/5m và được xác minh bằng hash của checkpoint, tệp kết quả và báo cáo. Thư viện Phase 4A–4B đã dùng trong Phase 5. DEC-005 đã cố định hai mô hình trước khi mở tập kiểm thử cuối. [Đánh giá Phase 8](phase8_final_assessment.md) ghi nhận: ở 5m, hỗn hợp chuẩn hiệu chỉnh PIT không tốt hơn phân phối thực nghiệm \(H=30\) theo tiêu chí chính; ở 1m, tỷ lệ bao phủ tổng thể gần mức danh nghĩa nhưng vượt khoảng vẫn tụ cụm. Không chọn lại mô hình hoặc tham số từ dữ liệu 2025–2026.

Từ 2026-09-25 (DEC-006), phạm vi chỉ còn câu hỏi về phân phối của \(z_t\). Phase 9A đã xong (mang tính khám phá): phương sai của \(z_t\) thay đổi 4–5 lần theo giờ trong phiên vì σ EWMA không mô tả tính mùa vụ, còn dạng đuôi dày vẫn giữ nguyên sau điều chỉnh. 9D (σ điều chỉnh mùa vụ, 9 họ, \(H=30\) và \(H=60\)) đã chạy xong: tổn thất giảm 7,4% (1m) và 9,6% (5m), tỷ lệ bao phủ theo giờ gần như phẳng; khi σ đã đúng, không họ tham số nào tốt hơn phân phối thực nghiệm có ý nghĩa ở 1m (5m chỉ mô tả, DEC-009). Câu trả lời tạm thời: phân phối thực nghiệm của \(z_t\) kết hợp σ điều chỉnh mùa vụ. 9C, 9E, 9F vẫn là đề xuất; Phase 10 chưa bắt đầu. Báo cáo tổng hợp kết quả chính thức: [Bao_cao/bao_cao_ket_qua.tex](../Bao_cao/bao_cao_ket_qua.tex). Người dùng đã xác nhận mốc thời gian là đầu nến; múi giờ nguồn và quy tắc đáo hạn hợp đồng vẫn chưa xác minh (xem [data contract](data_contract.md)).
