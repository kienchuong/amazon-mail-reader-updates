# Lấy Microsoft Client ID một lần

Client ID là mã công khai để Microsoft biết ứng dụng nào đang xin quyền. Không tạo Client Secret và không đưa mật khẩu email vào trang nào ngoài trang đăng nhập chính thức của Microsoft.

1. Mở [Microsoft Entra admin center](https://entra.microsoft.com/) và đăng nhập tài khoản Microsoft dùng để quản lý ứng dụng.
2. Mở `Identity` → `Applications` → `App registrations` → `New registration`.
3. Đặt tên, ví dụ `Amazon Mail Reader`.
4. Ở `Supported account types`, chọn:
   `Accounts in any organizational directory and personal Microsoft accounts`.
5. Bấm `Register`.
6. Trong trang `Overview`, sao chép `Application (client) ID`.
7. Mở `Authentication` → `Add a platform` → `Mobile and desktop applications`.
8. Thêm Redirect URI `http://localhost`, sau đó lưu.
9. Mở `API permissions` → `Add a permission` → `Microsoft Graph` → `Delegated permissions`.
10. Thêm `Mail.Read` và `User.Read`. Không thêm `Mail.ReadWrite`, `Mail.Send` hoặc quyền Application.
11. Quay lại Amazon Mail Reader → tab `Cài đặt`, dán Client ID và bấm `Lưu cấu hình`.

Khi bấm `Đăng nhập Microsoft`, địa chỉ trình duyệt phải bắt đầu bằng `https://login.microsoftonline.com/`. Cửa sổ đồng ý quyền chỉ nên hiển thị quyền đọc email và xem thông tin tài khoản cơ bản.

