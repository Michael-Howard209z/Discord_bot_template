# Discord Bot
## 🌐 Lựa chọn ngôn ngữ

[<img src="https://upload.wikimedia.org/wikipedia/commons/2/21/Flag_of_Vietnam.svg" alt="Tiếng Việt" width="40"/>](README_vi.md)
[<img src="https://upload.wikimedia.org/wikipedia/en/a/a4/Flag_of_the_United_States.svg" alt="English" width="40"/>](README_en.md)

VI
Một bot Discord giàu tính năng được xây dựng bằng Python và `discord.py`, cung cấp hơn 100 lệnh cho thông tin, giải trí, âm nhạc, kiểm duyệt, tiết kiệm và các tiện ích nâng cao. Bot này được thiết kế để tăng cường tương tác với máy chủ với các tính năng như tìm kiếm GIF, rút gọn URL, dịch thuật, tìm kiếm podcast, v.v.

## Tính năng
- **Thông tin & Tiện ích**: Các lệnh như `!ping`, `!translate`, `!shorten`, `!qr`, v.v.
- **Giải trí & Trò chơi**: Bao gồm `!gif`, `!joke`, `!trivia`, `!hangman`, v.v.
- **Âm nhạc & Phương tiện truyền thông**: Hỗ trợ `!podcast` với mô tả văn bản thành giọng nói tiếng Việt.
- **Kiểm duyệt**: Các lệnh như `!ban`, `!kick`, `!mute`, v.v. (yêu cầu quyền quản trị).

- **Kinh tế & Lên cấp**: Các tính năng `!daily`, `!balance`, `!leaderboard`, v.v.
- **Tiện ích Nâng cao**: Bao gồm `!remind`, `!timer`, `!news` (đang chờ tích hợp API), v.v.
- **Trạng thái Động**: Bot chuyển đổi qua các trạng thái như "Đang chơi trò chơi vui nhộn", "Đang xem phim", v.v.

## Điều kiện tiên quyết
- Python 3.12 trở lên
- Mã thông báo bot Discord (từ [Cổng thông tin dành cho nhà phát triển Discord](https://discord.com/developers/applications))
- Khóa API tùy chọn cho các tính năng nâng cao:
- [API Bitly](https://dev.bitly.com/) để rút ngắn URL (`!shorten`)
- [API Listen Notes](https://www.listennotes.com/api/) để tìm kiếm podcast (`!podcast`)
- [Tenor API](https://tenor.com/developer/keyregistration) để tìm kiếm GIF (`!gif`)

## Cài đặt
1. **Sao chép Kho lưu trữ**:
```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

2. **Cài đặt các Phụ thuộc**:
```bash
pip install -r requirements.txt
```

3. **Thiết lập Biến Môi trường**:
- Tạo tệp ``.env` trong thư mục gốc của dự án.
- Thêm nội dung sau:
```plaintext
DISCORD_BOT_TOKEN=your_discord_bot_token
BITLY_API_KEY=your_bitly_api_key
LISTENNOTES_API_KEY=your_listennotes_api_key
TENOR_API_KEY=your_tenor_api_key
```
- Thay thế ``your_discord_bot_token`, v.v., bằng các khóa thực tế. Để biết hướng dẫn về cách lấy khóa, hãy xem [Điều kiện tiên quyết](#điều kiện tiên quyết).

4. **Chạy Bot**:
```bash
python main.py
```

## Cấu hình
- **Quyền của Bot Discord**:
- Kích hoạt **Ý định Hiện diện**, **Ý định Thành viên Máy chủ** và **Ý định Nội dung Tin nhắn** trong Cổng thông tin Nhà phát triển Discord.
- Đảm bảo bot có các quyền: `send_messages`, `embed_links`, `attach_files` (cho `!podcast`) và quyền kiểm duyệt cho các lệnh như `!ban`.

- **Cơ sở dữ liệu**: Bot sử dụng SQLite (`bot_data.db`) cho dữ liệu người dùng, lời nhắc và ghi chú. Không cần thiết lập thêm; cơ sở dữ liệu được tạo tự động.

## Cách sử dụng
1. **Mời Bot**:
- Sử dụng liên kết mời của bot từ Cổng thông tin Nhà phát triển Discord để thêm bot vào máy chủ của bạn.
2. **Lệnh**:
- Tiền tố: `!`
- Xem tất cả lệnh: `!help_all`
- Ví dụ:
- `!gif funny cat`: Tìm kiếm ảnh GIF mèo ngộ nghĩnh.
- `!translate vi Hello`: Dịch "Hello" sang tiếng Việt.
- `!shorten https://example.com`: Rút gọn URL.
- `!podcast tech`: Tìm kiếm podcast công nghệ có mô tả TTS tiếng Việt.
3. **Trạng thái động**: Bot sẽ chuyển đổi qua các trạng thái sau mỗi 30 giây (ví dụ: "Đang xem phim", "Đang nghe nhạc").

## Đóng góp
- Phân nhánh kho lưu trữ.
- Tạo nhánh mới (`git checkout -b feature/your-feature`).
- Cam kết thay đổi (`git commit -m "Thêm tính năng của bạn"`).
- Đẩy lên nhánh (`git push origin feature/your-feature`).
- Mở Yêu cầu Kéo.

## Giấy phép
Bản quyền (c) 2025 Nguyễn Hoàng

Phần mềm này được sử dụng, chỉnh sửa và chia sẻ miễn phí
cho mục đích cá nhân hoặc phi thương mại.

Mọi hình thức sử dụng thương mại (bán, cho thuê, dịch vụ trả phí)
đều bị nghiêm cấm nếu không có sự đồng ý bằng văn bản của tác giả.

## Liên hệ

<img src="qr.png">