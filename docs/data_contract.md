# Data contract — DATA-V1

## Nguồn và bất biến

Nguồn: `ohlc_export.csv` tại root, symbol `VN30F1M`. File gốc chỉ được đọc, không bị chỉnh sửa. Manifest của mỗi lần chuẩn bị lưu SHA-256 của file và policy. Timezone được gắn nhãn `Asia/Ho_Chi_Minh` theo giả định nghiên cứu, nhưng nguồn chưa xác nhận timezone và timestamp convention.

Input bắt buộc có `SYMBOL`, `TRADING_DATE`, `TRADING_TIME`, OHLC, `VOL`, `BUY_VOL`, `BUY_VAL`, `SELL_VOL`, `SELL_VAL`. Timestamp phải duy nhất và tăng dần; OHLC dương, hữu hạn và hợp lệ. Bất thường về buy/sell volume được báo cáo, không tự sửa giá/volume.

## Phiên được sử dụng

Policy lưu tại `configs/data_v1.json`:

| Session | Phút đầu | Phút cuối | Số bar tối đa |
|---|---|---|---:|
| Morning | 09:00 | 11:29 | 150 |
| Afternoon | 13:00 | 14:29 | 90 |

Các bar 08:59, 11:30, 14:30, 14:45 và thời điểm ngoài hai khoảng trên được ghi là `excluded_non_continuous_rows` trong audit. Lịch phiên thay đổi trong dữ liệu; vì vậy DATA-V1 dùng phần lõi chung giữa các giai đoạn. Các session đặc biệt có thể thành dataset khác sau này.

## Xây dựng mẫu

- 1m: giữ bar trong hai session. Chỉ tạo target khi bar kế tiếp cùng ngày, cùng session và timestamp cách đúng một phút.
- 5m: nhóm vào bucket năm phút tính từ đầu mỗi session; chỉ giữ bucket có đủ năm timestamp đúng vị trí. OHLC lấy first/max/min/last, volume lấy tổng.
- 5m target: chỉ dùng cặp bucket đầy đủ, cùng ngày/phiên và cách nhau đúng năm phút.
- `target_log_return = log(next_close / current_close)`. Target là nhãn tương lai, không phải feature.
- `available_at = timestamp + 1 phút` cho 1m hoặc `+ 5 phút` cho 5m. Đây là quy tắc **bảo thủ** khi chưa xác nhận nhãn thời gian là đầu hay cuối bar.
- Không có target qua lunch, ATC, overnight hoặc qua gap mất phút. Không winsorize return, không thay thế outlier.

## Rủi ro còn mở

1. **Rollover:** file chỉ có symbol liên tục `VN30F1M`; không có mã hợp đồng gốc hoặc ngày roll. Target DATA-V1 không đi qua ranh giới ngày/phiên, nhưng cần xác minh có đổi hợp đồng trong phiên hay không trước khi diễn giải tail events.
2. **Timestamp:** chưa xác nhận nhãn là đầu hay cuối phút. Quy tắc `available_at` cộng đủ thời lượng bar ngăn dùng bar 5m chưa đóng trong nghiên cứu.
3. **Anomalies:** một số biến động rất lớn và 2.900 dòng có `BUY_VOL + SELL_VOL != VOL`; audit chỉ thống kê, không tự loại các return trong lõi phiên.
4. **Lịch phiên:** DATA-V1 cố định phần lõi chung. So sánh theo năm và giờ trong ngày cần đánh giá ảnh hưởng của policy này.

Output `samples_1m.csv`, `samples_5m.csv` và `manifest.json` nằm trong thư mục chỉ định. Manifest lưu hash của input, policy, source code và hai output, cùng phiên bản Python/NumPy/pandas. CLI từ chối ghi đè thư mục đã tồn tại. Chỉ `manifest.json` hoàn tất mới được xem là output đầy đủ.
