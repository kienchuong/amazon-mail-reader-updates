# Amazon Mail Reader 0.5.0

Ứng dụng Windows chỉ đọc để xem tập trung mail Amazon, cảnh báo bảo mật và thống kê payment.

## An toàn

- Outlook/Hotmail đăng nhập trên trang chính thức của Microsoft bằng OAuth 2.0 + PKCE.
- Chỉ xin quyền Microsoft Graph `Mail.Read` và `User.Read`.
- App chỉ gọi các API `GET`; không gửi, xóa, di chuyển, sửa hoặc đánh dấu mail đã đọc.
- IMAP dùng `SELECT readonly=True` và `BODY.PEEK`.
- Token Microsoft, App Password và Google Sheet Secret được mã hóa bằng mật khẩu chính.
- Mật khẩu email Microsoft không đi qua ứng dụng.

## Lần chạy đầu

1. Mở `run_app.bat`.
2. Chọn thư mục dữ liệu ở ổ khác ổ C, ví dụ `D:\AmazonMailReaderData`.
3. Tạo mật khẩu chính ít nhất 8 ký tự và nhớ kỹ mật khẩu này.
4. Nếu cài lại Windows, mở app, chọn lại đúng thư mục dữ liệu cũ và nhập mật khẩu chính.

Không có cách khôi phục nếu quên mật khẩu chính. Hãy sao lưu toàn bộ thư mục dữ liệu sang nơi an toàn.

## Đăng nhập Outlook/Hotmail

1. Làm một lần theo file `HUONG_DAN_MICROSOFT.md` để lấy Microsoft Client ID.
2. Mở mục `Cài đặt`, nhập Client ID rồi bấm `Lưu cấu hình`.
3. Mở mục `Accounts`, chọn `Outlook` và bấm `Đăng nhập Microsoft`.
4. Trình duyệt mở trang Microsoft. Chọn account và đồng ý quyền đọc mail.
5. Lặp lại bước 3-4 cho từng Outlook/Hotmail.

Token được lưu trong kho mã hóa và tự làm mới. Thông thường không phải đăng nhập lại sau khi đóng app, cập nhật app hoặc sang tháng mới. Microsoft có thể yêu cầu đăng nhập lại nếu quyền bị thu hồi hoặc thay đổi bảo mật account.

## Gmail, Yahoo và email tên miền

Phiên bản này chưa có OAuth cho Gmail/Yahoo. Các loại này vẫn dùng IMAP + App Password. Outlook không còn dùng password IMAP.

## Đọc và thống kê

- Mục `Inbox`: quét, tìm kiếm và lọc Payment, Reject, Amazon Account, Security.
- Nội dung đầy đủ chỉ được tải khi cần và không lưu lâu dài trong database.
- Mục `Payment`: tổng hợp riêng theo từng loại tiền, xuất CSV hoặc Google Sheet.
- Google Sheet tự đồng bộ sau khi quét khi tùy chọn `Tự đồng bộ sau khi quét` được bật.
- Google Sheet dùng Apps Script trong file `google_sheets_webhook.gs`.
- Mobile Dashboard dùng cùng Apps Script, đồng bộ snapshot sau khi quét và không đăng nhập email trên điện thoại. Xem `HUONG_DAN_MOBILE.md`.

## Dữ liệu và cập nhật

Chương trình và dữ liệu nằm riêng. Database, token, cấu hình và lịch sử quét đều nằm trong thư mục dữ liệu đã chọn. Windows chỉ giữ một tệp nhỏ không nhạy cảm để nhớ đường dẫn.

Mục `Cài đặt` dùng sẵn kho `kienchuong/amazon-mail-reader-updates`. Mỗi release cần có:

- gói ZIP, ưu tiên tên kết thúc bằng `win64.zip`;
- file `<tên-gói>.sha256` hoặc `SHA256SUMS.txt`;
- file `run_app.bat` ở cấp gốc của ZIP.

App kiểm tra SHA-256 trước khi cài, giữ bản chương trình cũ ở thư mục `.backup` và tự phục hồi nếu giải nén lỗi.

## Chạy từ mã nguồn

Yêu cầu Python 3.12 trên Windows có Tkinter và thư viện trong `requirements.txt`. File `run_app.bat` ưu tiên Python đi kèm Codex, sau đó tự tìm Python đã cài trên Windows. Nếu thiếu CustomTkinter hoặc tksheet, file này tự cài thư viện trước khi mở app.

## Cấu trúc chính

- `app.py`: khởi động ứng dụng.
- `amzmail/ui.py`: khung cửa sổ, điều hướng và các thao tác chung.
- `amzmail/views/`: giao diện riêng cho Inbox, Payment, Accounts và Cài đặt.
- `amzmail/google_sheets.py`: xuất CSV và đồng bộ Google Sheet.
- `amzmail/microsoft_graph.py`: đăng nhập OAuth và đọc Outlook.
- `amzmail/imap_reader.py`: đọc Gmail, Yahoo và email tên miền qua IMAP.
