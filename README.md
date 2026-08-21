# Amazon Mail Reader 0.6.10

Ứng dụng Windows chỉ đọc để xem tập trung mail Amazon, cảnh báo bảo mật và thống kê payment.

## An toàn và dữ liệu

- Outlook/Hotmail dùng Microsoft OAuth; Gmail/Yahoo/tên miền có thể dùng luồng hiện có của app.
- App chỉ đọc mail. IMAP dùng chế độ read-only và `BODY.PEEK`.
- Database, token và cấu hình vẫn nằm tại thư mục dữ liệu đã chọn, hiện là `E:\Payment Royalties APP`.
- UI PySide6 không thay đổi schema, định dạng config, provider, parser, webhook hoặc dữ liệu đã lưu.

## Launcher chuẩn trên Windows

Launcher chuẩn là `run_app.vbs`. Shortcut `Amazon Mail Reader.lnk` gọi file này bằng `wscript.exe`, vì vậy không mở cửa sổ CMD.

`run_app.vbs` luôn dùng runtime riêng:

```text
E:\Payment Royalties APP\runtime\amazon-mail-reader\Scripts\pythonw.exe
```

`run_app.bat` chỉ là wrapper tương thích để updater hiện có có thể gọi lại launcher chuẩn. Không mở `app.py` trực tiếp bằng Python khác vì môi trường đó có thể thiếu dependency.

## Cài runtime từ source

```powershell
py -3.14 -m venv "E:\Payment Royalties APP\runtime\amazon-mail-reader"
& "E:\Payment Royalties APP\runtime\amazon-mail-reader\Scripts\python.exe" -m pip install -r requirements.txt
```

Dependency giao diện là `PySide6`. Project không còn dùng Tkinter, CustomTkinter hoặc tksheet.

## Cấu trúc

- `app.py`: tạo `QApplication`, mở kho dữ liệu và cửa sổ chính.
- `amzmail/ui.py`: presentation controller và callback của cửa sổ Qt.
- `amzmail/views/`: Qt Widgets cho Inbox, Payment, Accounts, Cài đặt và model bảng.
- `amzmail/controllers/background.py`: chuyển event từ worker thread về Qt UI thread bằng signal.
- `amzmail/db.py`, `vault.py`, `classifier.py`, provider, webhook và updater: application/business layer hiện có, không bị thay đổi bởi UI migration.
- `amzmail/remote_sync.py`: adapter đồng bộ snapshot mobile qua Cloudflare Worker; UI và luồng quét mail không biết chi tiết D1.
- `cloudflare/`: Worker API và migration D1 của Mobile Dashboard. Không chứa secret thật.

## Mobile Dashboard

Mobile Dashboard dùng luồng `PC -> Cloudflare Worker -> D1 -> GitHub Pages`. D1 chỉ giữ snapshot chỉ-đọc mới nhất; mật khẩu email, OAuth token và database local không được tải lên. Xem `HUONG_DAN_CLOUDFLARE.md` để tạo resource và cấu hình.

## Regression chính

Sau thay đổi UI cần kiểm tra: mở app, load account/config cũ, Inbox, Payment, chọn account, search/filter, đọc body, quét, Google Sheet, Mobile Dashboard, lưu settings, đóng và mở lại.
