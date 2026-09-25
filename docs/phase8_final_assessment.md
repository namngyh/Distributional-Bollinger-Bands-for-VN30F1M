# Đánh giá trên tập kiểm thử cuối — Phase 8 (PHASE8-V1)

Ngày ghi nhận: 2026-09-23; thuật ngữ được chuẩn hóa ngày 2026-09-25 theo [bảng thuật ngữ](thuat_ngu.md), số liệu không đổi. Đây là báo cáo **một lần** cho các mô hình đã được chọn theo DEC-005 trước khi đánh giá dữ liệu 2025–2026. Không dùng kết quả này để chọn lại mô hình hoặc tham số rồi tiếp tục gọi cùng giai đoạn là tập kiểm thử độc lập.

## Tính toàn vẹn và phạm vi

- `run_phase8.bat check` xác minh nguồn gốc, dữ liệu đầu vào và checkpoint 381/381 phiên ở cả 1m và 5m. Hai báo cáo được tính lại bằng `phase8_report --check-only` và khớp với tệp đã lưu.
- Giai đoạn thực tế: 2025-01-02 đến 2026-07-17, 381 phiên. 1m có 90.478 nến được chấm điểm; 5m có 17.474 nến. Ở 5m có 76 lần ước lượng mới, không lần nào thất bại. Mã, cấu hình và mô hình không thay đổi sau khi mở tập kiểm thử.
- Mô hình 1m: phân phối thực nghiệm của \(z\), σ EWMA với chu kỳ bán rã 30 phút giao dịch. Mô hình 5m: hỗn hợp chuẩn 2 thành phần, cùng chu kỳ bán rã, hiệu chỉnh xác suất bằng PIT của các phiên *trước* ngày dự báo. Phân phối thực nghiệm với \(H=30\) ở 5m là đối chứng được định trước trên cùng tập nến.
- SHA-256 của checkpoint: 1m `5e14485f91d1ccf5a85121b18a1681454875c0eed44ff83cac74e72b22275cf1`; 5m `fdb55d674b3a643b03fdf9a9b3d26c830abbc34cd03dce52d12ee8d199b29826`.
- SHA-256 của báo cáo: 1m `007974095dc4a79c49b8dba42a3d1e28a7b23587c077325a1fb130e579a8f9f7`; 5m `9598c90301a23baf424253dcae64edaa6118defb578e5fd8c2eb96a159a2ff42`.

## Kết quả của các mô hình đã chọn

Tiêu chí chính là tổn thất phân vị trung bình trên năm khoảng dự báo 90%, 95%, 97,5%, 99% và 99,5%, trọng số bằng nhau; nhỏ hơn là tốt hơn.

| Khung và mô hình | Tổn thất phân vị trung bình | Bao phủ 90% | Bao phủ 95% | Bao phủ 99,5% |
|---|---:|---:|---:|---:|
| 1m — phân phối thực nghiệm, \(H=30\) (đã chọn) | 3,015375 × 10⁻⁵ | 89,964% | 94,968% | 99,488% |
| 5m — hỗn hợp chuẩn 2 thành phần, \(H=30\), hiệu chỉnh PIT (đã chọn) | 7,259693 × 10⁻⁵ | 89,493% | 94,678% | 99,565% |
| 5m — phân phối thực nghiệm, \(H=30\) (đối chứng) | 7,243372 × 10⁻⁵ | 90,025% | 94,941% | 99,416% |

Ở 5m, mô hình đã chọn có tổn thất **cao hơn 0,2253%** so với đối chứng trên cùng 17.474 nến (chênh lệch tổn thất trung bình \(+1{,}6321\times10^{-7}\)). Bootstrap khối vòng theo ngày (khối 5 phiên, 2.000 lần lặp) cho khoảng tin cậy 95% chưa hiệu chỉnh \([+2{,}8320\times10^{-8};\ +3{,}0234\times10^{-7}]\) và giá trị p hai phía 0,02249. Chênh lệch bất lợi cũng xuất hiện riêng ở 2025 (+0,2995%) và ở 2026 đến 17/07 (+0,0736%); hai phân đoạn này chỉ để mô tả, không phải các tập kiểm thử mới. Tỷ lệ bao phủ 90% và 95% của hỗn hợp chuẩn thấp hơn đối chứng, trong khi khoảng 99,5% hơi rộng hơn mức danh nghĩa. Lợi thế của hỗn hợp chuẩn hiệu chỉnh ở 5m trên tập xác thực **không tổng quát hóa** sang tập kiểm thử cuối theo tiêu chí chính.

Ở 1m, tỷ lệ bao phủ tổng thể gần mức danh nghĩa ở mọi khoảng. Tuy nhiên, kiểm định độc lập Markov cho chuỗi vượt khoảng 95% trong cùng phiên có giá trị p rất nhỏ ở cả hai phía: các lần vượt khoảng tụ cụm. Vì Phase 8 chỉ chọn một mô hình cho 1m, không có so sánh ghép cặp với ứng viên khác trên tập này. Cũng không nên so trực tiếp mức tổn thất tuyệt đối giữa 2022–2024 và 2025–2026, vì mức biến động thị trường có thể khác nhau.

## Diễn giải và giới hạn

PHASE8-V1 là kết quả hợp lệ nhưng **âm đối với giả thuyết "hỗn hợp chuẩn hiệu chỉnh PIT dự báo ngoài mẫu tốt hơn phân phối thực nghiệm ở 5m"**. Không được đổi sang phân phối thực nghiệm ở 5m rồi gọi đó là mô hình được chọn cuối cùng: có thể báo cáo rằng đối chứng tốt hơn trong phép so sánh đã định trước, nhưng chọn lại cấu hình dựa trên tập kiểm thử sẽ làm mất tính độc lập của chính tập đó. Ở 1m, tính hiệu chuẩn không điều kiện (tính trên toàn giai đoạn) tương đối tốt, nhưng tính hiệu chuẩn có điều kiện và phụ thuộc chuỗi chưa được giải quyết.

Bootstrap dựa trên giả định khối 5 phiên; khoảng tin cậy và giá trị p không bao quát mọi phụ thuộc dài hạn hoặc thay đổi trạng thái thị trường. Histogram PIT gần phẳng không thay thế kiểm tra từng khoảng và kiểm định tụ cụm. Nguồn dữ liệu vẫn thiếu xác nhận về múi giờ và quy tắc đáo hạn hợp đồng; điều này đặc biệt quan trọng khi diễn giải đuôi phân phối. Mốc thời gian là đầu nến theo xác nhận của người dùng; lợi suất mục tiêu không nối qua phiên.

## Hệ quả cho nghiên cứu tiếp theo

1. Giữ nguyên PHASE8-V1, DEC-005 và mọi tệp kết quả; không điều chỉnh mô hình trên 2025–2026 rồi dùng lại giai đoạn này làm tập kiểm thử.
2. Muốn khẳng định có mô hình 5m tốt hơn, cần dữ liệu **mới trong tương lai** hoặc một thiết kế đánh giá cửa sổ trượt được cố định trước. Có thể phân tích 2025–2026 để hình thành giả thuyết, nhưng mọi mô hình phát sinh từ phân tích đó phải ghi rõ là mang tính khám phá và được kiểm tra trên dữ liệu khác.
3. *(Sửa 2026-09-25 theo DEC-006.)* Phạm vi project chỉ là phân phối của \(z_t\); nghiên cứu tín hiệu giao dịch đã bỏ khỏi kế hoạch. Phase 9 được đề xuất gồm chẩn đoán \(z_t\) (phụ thuộc còn lại, tính mùa vụ trong phiên), so sánh mở rộng chín họ và mô phỏng Monte Carlo, tất cả mang tính khám phá. Phase 8 chỉ chấm hai mô hình đã chọn nên chưa cho thứ hạng chín họ trên tập kiểm thử cuối.

Tệp nguồn: `outputs/phase8_v1/1m/report.json`, `outputs/phase8_v1/5m/report.json` và các checkpoint tương ứng.
