# Data contract — DATA-V1

Thuật ngữ theo [bảng thuật ngữ](thuat_ngu.md).

## Nguồn và bất biến

Nguồn: `ohlc_export.csv` tại root, symbol `VN30F1M`. File gốc chỉ được đọc, không bị chỉnh sửa. Manifest của mỗi lần chuẩn bị lưu SHA-256 của file và policy. Timezone được gắn nhãn `Asia/Ho_Chi_Minh` theo giả định nghiên cứu; nguồn chưa xác nhận timezone. Ngày 2026-09-23, người dùng xác nhận timestamp là **đầu nến**. Xác nhận này được ghi sau khi DATA-V1 đã tạo; không sửa `configs/data_v1.json` hay manifest đã hash để giữ nguyên provenance của artifact.

Input bắt buộc có `SYMBOL`, `TRADING_DATE`, `TRADING_TIME`, OHLC, `VOL`, `BUY_VOL`, `BUY_VAL`, `SELL_VOL`, `SELL_VAL`. Timestamp phải duy nhất và tăng dần; OHLC dương, hữu hạn và hợp lệ. Bất thường về buy/sell volume được báo cáo, không tự sửa giá/volume.

## Phiên được sử dụng

Policy lưu tại `configs/data_v1.json`:

| Session | Phút đầu | Phút cuối | Số bar tối đa |
|---|---|---|---:|
| Morning | 09:00 | 11:29 | 150 |
| Afternoon | 13:00 | 14:29 | 90 |

Các nến 08:59, 11:30, 14:30, 14:45 và thời điểm ngoài hai khoảng trên được ghi là `excluded_non_continuous_rows` trong audit. Lịch phiên thay đổi trong dữ liệu; vì vậy DATA-V1 dùng phần lõi chung giữa các giai đoạn. Các session đặc biệt có thể thành dataset khác sau này.

## Xây dựng mẫu

- 1m: giữ nến trong hai phiên. Chỉ tạo lợi suất mục tiêu khi nến kế tiếp cùng ngày, cùng phiên và cách đúng một phút.
- 5m: nhóm vào bucket năm phút tính từ đầu mỗi session; chỉ giữ bucket có đủ năm timestamp đúng vị trí. OHLC lấy first/max/min/last, volume lấy tổng.
- Lợi suất mục tiêu 5m: chỉ dùng cặp bucket đầy đủ, cùng ngày/phiên và cách nhau đúng năm phút.
- `target_log_return = log(next_close / current_close)`. Lợi suất mục tiêu là giá trị tương lai cần dự báo, không phải biến giải thích.
- `available_at = timestamp + 1 phút` cho 1m hoặc `+ 5 phút` cho 5m. Với timestamp đầu nến đã được người dùng xác nhận, đây là thời điểm nến nguồn hoàn tất; chưa cộng thêm độ trễ nhận dữ liệu hoặc đặt lệnh.
- Không có lợi suất mục tiêu nối qua nghỉ trưa, ATC, qua đêm hoặc qua khoảng trống mất phút. Không winsorize return, không thay thế outlier.

## Rủi ro còn mở

1. **Rollover:** file chỉ có symbol liên tục `VN30F1M`; không có mã hợp đồng gốc hoặc ngày roll. Lợi suất mục tiêu của DATA-V1 không đi qua ranh giới ngày/phiên, nhưng cần xác minh có đổi hợp đồng trong phiên hay không trước khi diễn giải các sự kiện ở đuôi phân phối.
2. **Timezone và latency:** timestamp đầu nến đã được người dùng xác nhận, nhưng timezone nguồn và độ trễ nhận dữ liệu/đặt lệnh chưa được xác minh. Latency chỉ quan trọng với phân tích giao dịch, vốn nằm ngoài phạm vi (DEC-006); timezone vẫn cần xác minh để diễn giải mùa vụ trong phiên.
3. **Bất thường:** một số biến động rất lớn và 2.900 dòng có `BUY_VOL + SELL_VOL != VOL`; audit chỉ thống kê, không tự loại các return trong lõi phiên.
4. **Lịch phiên:** DATA-V1 cố định phần lõi chung. So sánh theo năm và giờ trong ngày cần đánh giá ảnh hưởng của policy này.

Output `samples_1m.csv`, `samples_5m.csv` và `manifest.json` nằm trong thư mục chỉ định. Manifest lưu hash của input, policy, source code và hai output, cùng phiên bản Python/NumPy/pandas. CLI từ chối ghi đè thư mục đã tồn tại. Chỉ `manifest.json` hoàn tất mới được xem là output đầy đủ.
