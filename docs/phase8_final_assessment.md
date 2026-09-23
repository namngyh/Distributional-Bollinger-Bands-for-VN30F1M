# Đánh giá final test Phase 8 — PHASE8-V1

Ngày ghi nhận: 2026-09-23. Đây là báo cáo **một lần** cho các mô hình đã khóa bằng DEC-005 trước khi đánh giá dữ liệu 2025–2026. Không dùng kết quả này để chọn lại mô hình hoặc tham số và tiếp tục gọi cùng giai đoạn là final test độc lập.

## Tính toàn vẹn và phạm vi

- `run_phase8.bat check` xác minh lineage, input và checkpoint 381/381 phiên trên cả 1m và 5m. Hai báo cáo `phase8_report --check-only` được tính lại và khớp artifact đã lưu.
- Giai đoạn thực tế: 2025-01-02 đến 2026-07-17; 381 phiên. 1m có 90.478 nến được chấm; 5m có 17.474 nến. 5m có 76 lần fit mới, không có fit failure. Không có thay đổi code/config/model sau khi mở final.
- Mô hình 1m: Empirical EWMA, half-life 30 phút giao dịch. Mô hình 5m: Normal Mixture 2, cùng half-life, hiệu chỉnh PIT bằng các phiên *trước* ngày dự báo. Empirical EWMA HL30 5m là đối chứng được định trước trên cùng các nến.
- Checkpoint SHA-256: 1m `5e14485f91d1ccf5a85121b18a1681454875c0eed44ff83cac74e72b22275cf1`; 5m `fdb55d674b3a643b03fdf9a9b3d26c830abbc34cd03dce52d12ee8d199b29826`.
- Report SHA-256: 1m `007974095dc4a79c49b8dba42a3d1e28a7b23587c077325a1fb130e579a8f9f7`; 5m `9598c90301a23baf424253dcae64edaa6118defb578e5fd8c2eb96a159a2ff42`.

## Kết quả đã khóa

Primary score là mean pinball trên năm mức coverage 90%, 95%, 97,5%, 99% và 99,5%, trọng số bằng nhau; thấp hơn là tốt hơn.

| Khung và mô hình | Mean pinball | Coverage 90% | Coverage 95% | Coverage 99,5% |
|---|---:|---:|---:|---:|
| 1m — Empirical EWMA HL30 đã khóa | 3,015375 × 10⁻⁵ | 89,964% | 94,968% | 99,488% |
| 5m — Mixture 2 HL30 hiệu chỉnh PIT đã khóa | 7,259693 × 10⁻⁵ | 89,493% | 94,678% | 99,565% |
| 5m — Empirical EWMA HL30 đối chứng | 7,243372 × 10⁻⁵ | 90,025% | 94,941% | 99,416% |

Ở 5m, mô hình đã khóa có pinball **cao hơn 0,2253%** so với đối chứng trên cùng 17.474 nến (chênh lệch loss trung bình +1,6321 × 10⁻⁷). Circular day-block bootstrap với block 5 phiên, 2.000 lần lặp cho CI 95% chưa hiệu chỉnh `[+2,8320 × 10⁻⁸, +3,0234 × 10⁻⁷]`, p hai phía = 0,02249. Chênh lệch bất lợi cũng xuất hiện riêng ở 2025 (+0,2995%) và 2026 đến 17/07 (+0,0736%); hai phân đoạn này chỉ là mô tả, không phải các holdout mới. Coverage 90% và 95% của Mixture thấp hơn đối chứng, trong khi band 99,5% hơi rộng hơn mức danh nghĩa. Kết quả development dương của 5m **không tổng quát hóa** sang final test theo primary score đã khóa.

Ở 1m, coverage tổng thể gần mức danh nghĩa ở các band được nêu. Tuy nhiên, kiểm định independence cho các lần vượt band 95% trong cùng phiên có p rất nhỏ ở cả hai phía; vượt band còn tụ thành cụm. Vì Phase 8 chỉ khóa một mô hình 1m, không có so sánh paired 1m với một ứng viên khác trên final. Cũng không nên so trực tiếp mức pinball tuyệt đối giữa 2022–2024 và 2025–2026 để kết luận hơn/kém, vì mức biến động thị trường có thể khác nhau.

## Diễn giải và giới hạn

PHASE8-V1 là kết quả final hợp lệ nhưng **âm đối với tuyên bố 5m Mixture hiệu chỉnh PIT vượt Empirical về dự báo OOS**. Không đổi sang Empirical 5m rồi tuyên bố đó là “winner final”: đối chứng có thể được báo cáo là tốt hơn trong phép so sánh đã định trước, nhưng chọn lại cấu hình dựa trên final sẽ làm mất tính độc lập của chính final set. 1m cho calibration vô điều kiện tương đối sát, song chưa giải quyết conditional calibration/serial dependence.

Bootstrap phụ thuộc giả định block 5 phiên; p-value và CI không đo lường mọi phụ thuộc dài hạn hoặc rủi ro thay đổi chế độ. PIT histogram gần đều không thay thế kiểm tra từng band và clustering. Nguồn dữ liệu vẫn thiếu xác nhận về timezone và quy tắc điều chỉnh hợp đồng/rollover; điều này đặc biệt quan trọng nếu diễn giải tail hoặc nghiên cứu giao dịch. Timestamp là đầu nến theo xác nhận của người dùng, và target không nối qua phiên.

## Hệ quả cho nghiên cứu tiếp theo

1. Giữ nguyên PHASE8-V1, DEC-005 và mọi artifact; không retune trên 2025–2026 rồi tái sử dụng khoảng này như final.
2. Trước khi tuyên bố có mô hình 5m tốt hơn, cần một giai đoạn dữ liệu **mới trong tương lai** hoặc một giao thức đánh giá tiến về trước được khóa trước. Có thể phân tích 2025–2026 để tìm giả thuyết, nhưng mọi mô hình phát sinh từ phân tích đó phải được dán nhãn exploratory và kiểm tra trên dữ liệu khác.
3. Nếu nghiên cứu Phase 9 về tín hiệu giao dịch, phải lập kế hoạch/điều kiện đánh giá riêng. Band xác suất tốt không tự động tạo chiến lược có lợi nhuận, và 5m Mixture hiện chưa vượt qua tiêu chí dự báo final đã chọn.

Artifact nguồn: `outputs/phase8_v1/1m/report.json`, `outputs/phase8_v1/5m/report.json` và checkpoint tương ứng. Chưa có thí nghiệm tiếp theo nào được khởi chạy từ báo cáo này.
