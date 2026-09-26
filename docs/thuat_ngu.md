# Bảng thuật ngữ thống kê

Tài liệu của project dùng thuật ngữ thống kê tiếng Việt theo bảng này (quyết định DEC-007, 2026-09-25). Tên biến, khóa JSON, tên file và tên mô hình trong code **giữ nguyên** vì các checkpoint và báo cáo đã được ràng buộc bằng hash; cột cuối cho biết tên tương ứng trong code.

## Mô hình và dữ liệu

| Thuật ngữ dùng trong tài liệu | Ý nghĩa | Thuật ngữ cũ / tên trong code |
|---|---|---|
| Lợi suất kỳ sau \(r_{t+1}\) | \(\log(C_{t+1}/C_t)\), lợi suất logarit của nến kế tiếp; là biến mục tiêu cần dự báo | target, `target_log_return` |
| Nến | Một quan sát giá theo khung 1 phút hoặc 5 phút | bar |
| Độ biến động có điều kiện \(\sigma_t\) | Độ lệch chuẩn dự báo của lợi suất, ước lượng từ các lợi suất trước \(t\) | volatility, `sigma_ewma` |
| Trung bình trượt lũy thừa (EWMA) | \(\sigma_t^2=\lambda\sigma_{t-1}^2+(1-\lambda)r_{t-1}^2\); quan sát càng cũ trọng số càng giảm theo cấp số nhân | EWMA |
| Chu kỳ bán rã \(H\) | Số phút giao dịch để trọng số giảm còn một nửa; \(\lambda=2^{-\Delta/H}\) | half-life, HL30/HL60/HL120 |
| Phần dư chuẩn hóa \(z_t\) | \(z_t=r_t/\sigma_t\); đối tượng nghiên cứu chính | standardized residual |
| Phân phối của \(z\), ký hiệu \(F\) | Luật xác suất của \(z\), chuẩn hóa về kỳ vọng 0 và phương sai 1 | distribution, law |
| Họ phân phối tham số | Chín họ: Chuẩn, Student-t, phân phối sai số tổng quát (GED), Student-t lệch, GED lệch, NIG, Hyperbolic tổng quát (GH), hỗn hợp chuẩn 2 và 3 thành phần | `normal`, `student_t`, `ged`, `skewed_t`, `skewed_ged`, `nig`, `gh`, `normal_mixture_2`, `normal_mixture_3` |
| Phân phối thực nghiệm của \(z\) | Phân vị mẫu của \(z\) trong 60 phiên trước, không giả định dạng phân phối (phi tham số) | Empirical EWMA, `empirical_ewma` |
| Chuẩn với σ cửa sổ cố định | Phân phối chuẩn với độ lệch chuẩn tính từ 240 phút gần nhất; tương tự Bollinger truyền thống | Normal rolling, `normal_rolling` |
| Tham số vị trí / thang đo / hình dạng | loc / scale / các tham số như df, β, skew, a, b, p | loc, scale, shape |
| Đuôi dày | Xác suất giá trị cực trị lớn hơn phân phối chuẩn | heavy tail, fat tail |
| Hoán đổi nhãn thành phần | Các thành phần của hỗn hợp chuẩn có thể đổi thứ tự giữa các lần ước lượng | label switching |

## Dự báo và đánh giá

| Thuật ngữ dùng trong tài liệu | Ý nghĩa | Thuật ngữ cũ / tên trong code |
|---|---|---|
| Phân vị (mức \(p\)) | \(q(p)=\sigma_t F^{-1}(p)\) | quantile, `q_low`, `q_high` |
| Khoảng dự báo trung tâm mức \(c\) | Khoảng \([q(\tfrac{1-c}{2}),\,q(\tfrac{1+c}{2})]\), với \(c\) = 90%, 95%, 97,5%, 99%, 99,5%. Quy đổi ra giá là dải Bollinger theo phân phối | band, central coverage |
| Tỷ lệ bao phủ | Tần suất lợi suất thực tế rơi vào khoảng dự báo; lý tưởng bằng \(c\) | coverage, `observed_coverage` |
| Tỷ lệ vượt khoảng dưới / trên | Tần suất lợi suất thấp hơn cận dưới / cao hơn cận trên; lý tưởng bằng \((1-c)/2\) mỗi phía | exceedance, `lower_exceedance`, `upper_exceedance` |
| Hàm tổn thất phân vị \(\rho_\tau(u)=u(\tau-\mathbf 1\{u<0\})\) | Hàm tổn thất của hồi quy phân vị (Koenker và Bassett, 1978). Kỳ vọng của nó nhỏ nhất khi dự báo đúng bằng phân vị thật, nên là thước đo phù hợp để so sánh các dự báo phân vị | pinball loss, check loss |
| Tổn thất phân vị trung bình | Tiêu chí chính: trung bình tổn thất phân vị trên 10 phân vị (hai cận của 5 khoảng), trọng số bằng nhau, tính trên cùng tập nến; nhỏ hơn là tốt hơn | mean pinball, primary score, `mean_pinball_equal_weight` |
| Chênh lệch tổn thất tương đối (Δ) | \((L_\text{mô hình}/L_\text{tham chiếu}-1)\times100\%\); âm là tốt hơn tham chiếu | Δ pinball |
| Biến đổi tích phân xác suất (PIT) | \(u_t=F_t(z_t)\). Nếu \(F_t\) đúng thì \(u_t\) có phân phối đều trên [0, 1]; histogram PIT lệch khỏi dạng phẳng cho thấy sai dạng phân phối | PIT, `pit_histogram` |
| Tính hiệu chuẩn | Mức khớp giữa xác suất dự báo và tần suất thực tế | calibration |
| Kiểm định độc lập Markov | Kiểm định tỷ số hợp lý (Christoffersen, 1998) xem một lần vượt khoảng có làm tăng xác suất vượt khoảng ở nến kế tiếp không; thống kê có phân phối \(\chi^2(1)\) | independence test, `lower_independence` |
| Vượt khoảng tụ cụm | Các lần vượt khoảng phụ thuộc chuỗi, không độc lập theo thời gian | clustering |
| So sánh ghép cặp | So các mô hình trên đúng cùng một tập nến | paired |
| Bootstrap khối vòng theo ngày | Lấy mẫu lại theo khối 5 phiên liên tiếp để giữ phụ thuộc chuỗi trong khối; dùng để tính khoảng tin cậy và giá trị p | circular day-block bootstrap |
| Hiệu chỉnh Holm | Hiệu chỉnh giá trị p cho kiểm định bội khi so nhiều mô hình với cùng một tham chiếu (Holm, 1979) | Holm correction, `p_holm` |
| Hàm tự tương quan (ACF) | Tương quan giữa một chuỗi và chính nó trễ \(k\) nến; ở Phase 9A chỉ tính trên các cặp nến trong cùng phiên | autocorrelation, `acf` |
| Thống kê \(Q\) (dạng Box–Pierce) | \(Q=\sum_k n_k\hat\rho_k^2\); so với \(\chi^2\) chỉ để tham chiếu vì giả định độc lập | portmanteau, `portmanteau` |
| Tính mùa vụ trong phiên | Mức biến động trung bình thay đổi có quy luật theo giờ trong phiên giao dịch | intraday seasonality |
| Điều chỉnh mùa vụ | Chia \(z\) cho căn bậc hai trung bình \(z^2\) của khối giờ tương ứng | seasonal adjustment, `z2_seasonally_adjusted` |
| Hệ số mùa vụ \(s_b\) (Phase 9D) | \(\sqrt{\overline{r^2_b}/\overline{r^2}}\) của khối giờ \(b\), tính trên 250 phiên trước ngày dự báo | seasonal factor, `seasonal_factor` |
| Mức biến động chung \(\tilde\sigma\) | EWMA của lợi suất đã khử mùa vụ \(r/s_b\); σ dự báo \(=s_b\tilde\sigma\) | deseasonalized EWMA, `sigma_tilde` |
| Sai số chuẩn gom cụm theo ngày | Sai số chuẩn của trung bình cho phép các quan sát trong cùng ngày tương quan với nhau | day-clustered standard error, `se` |
| Độ nhọn vượt chuẩn | Độ nhọn trừ 3; bằng 0 với phân phối chuẩn, lớn hơn 0 khi đuôi dày | excess kurtosis |
| Trong mẫu / ngoài mẫu | Đánh giá trên dữ liệu đã dùng để ước lượng / trên dữ liệu sau thời điểm ước lượng | in-sample / out-of-sample (OOS) |

## Thiết kế thực nghiệm

| Thuật ngữ dùng trong tài liệu | Ý nghĩa | Thuật ngữ cũ / tên trong code |
|---|---|---|
| Giai đoạn khởi động | 2017–2021: chỉ dùng để cập nhật σ và tạo lịch sử phần dư, không đánh giá | warm-up |
| Tập xác thực | 04/01/2022–31/12/2024 (748 phiên): dùng để so sánh và chọn mô hình | development |
| Tập kiểm thử cuối | 02/01/2025–17/07/2026 (381 phiên): chỉ dùng một lần sau khi đã chọn mô hình | final test |
| Đánh giá cửa sổ trượt | Ước lượng trên 60 phiên gần nhất, dự báo 5 phiên kế tiếp, rồi trượt cửa sổ; mọi dự báo đều ngoài mẫu | walk-forward |
| Ước lượng lại | Một lần ước lượng tham số trên cửa sổ mới; 150 lần trên tập xác thực | refit |
| Ước lượng thất bại | Thuật toán tối ưu không hội tụ hoặc chạm ràng buộc; được ghi lại, không thay thế ngầm | fit failure |
| Phân tích độ nhạy | Thay đổi một lựa chọn thiết kế (ví dụ \(H\)) để xem kết quả thay đổi thế nào | sensitivity test |
| Danh sách ứng viên rút gọn | Các mô hình được giữ lại sau Phase 6 | shortlist |
| Mô hình được chọn | Mô hình được cố định trước tập kiểm thử cuối (quyết định DEC-005) | winner, model lock |
| Thí nghiệm bổ sung | Thí nghiệm kiểm tra một thành phần riêng, không phải câu trả lời chính | ablation |
| Mang tính khám phá | Kết quả gợi ý giả thuyết, không đủ để khẳng định vì dữ liệu đã được dùng trước đó | exploratory |

## Mô phỏng (Phase 9E)

| Thuật ngữ dùng trong tài liệu | Ý nghĩa | Thuật ngữ cũ |
|---|---|---|
| Mô phỏng Monte Carlo | Sinh nhiều mẫu ngẫu nhiên từ một phân phối đã biết rồi ước lượng lại, để đo sai số của phương pháp | simulation |
| Phân phối sinh mẫu | Phân phối "thật", với tham số đã biết, dùng để sinh mẫu mô phỏng | DGP (data-generating process) |
| Độ chệch | \(\mathbb E[\hat\theta]-\theta\) | bias |
| Căn sai số bình phương trung bình (RMSE) | \(\sqrt{\mathbb E[(\hat\theta-\theta)^2]}\); gồm cả độ chệch lẫn phương sai | RMSE |
| Hiệu quả tương đối | Tỷ số RMSE của phân vị tham số so với phân vị thực nghiệm; nhỏ hơn 1 nghĩa là ước lượng tham số chính xác hơn | efficiency |
| Mô hình sai dạng | Họ dùng để ước lượng không chứa phân phối sinh mẫu | misspecification |
| Phân vị thật | Phân vị của phân phối sinh mẫu, dùng làm chuẩn so sánh | oracle quantile |

## Thuật ngữ kỹ thuật (chỉ dùng trong phần vận hành)

Checkpoint (điểm lưu tiến độ), resume (chạy tiếp từ điểm lưu), artifact (tệp kết quả), `.bat` (script chạy trên Windows), smoke test (chạy thử quy mô nhỏ), hash (mã băm dùng để xác minh tệp không bị thay đổi).
