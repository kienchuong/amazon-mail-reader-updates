# Ket noi Gmail bang Google OAuth

## 1. Tao du an Google Cloud

1. Mo `https://console.cloud.google.com/` va tao mot project moi, vi du `Amazon Mail Reader`.
2. Mo `APIs & Services` -> `Library`, tim `Gmail API` va chon `Enable`.
3. Mo `APIs & Services` -> `OAuth consent screen`.
4. Chon `External` neu co Gmail ca nhan. Dien ten app, email ho tro va email lien he, sau do luu.
5. Tai `Data Access` / `Scopes`, them scope `https://www.googleapis.com/auth/gmail.readonly`.
6. Khi app con o `Testing`, them cac Gmail can ket noi vao danh sach `Test users`.
7. Mo `Credentials` -> `Create credentials` -> `OAuth client ID` -> `Desktop app`.
8. Sao chep `Client ID` va dan vao tab `Cai dat` cua Amazon Mail Reader, muc `Ket noi Gmail`.

## 2. Dang nhap Gmail trong app

1. Trong tab `Accounts`, chon `Gmail`.
2. Nhap ten account de de theo doi.
3. Bam `Dang nhap Google`.
4. Edge InPrivate se mo trang Google chinh thuc. Dang nhap dung Gmail va dong y quyen chi doc mail.
5. Sau khi quay lai app, Gmail xuat hien trong danh sach account. Bam `Kiem tra Google` hoac `Quet tat ca`.

## Luu y ve Google Testing

- App dung duy nhat scope `gmail.readonly`; khong gui, xoa, sua hoac danh dau mail da doc.
- Neu OAuth consent screen dang o `Testing`, Google chi cap refresh token trong 7 ngay. Sau do app se bao can dang nhap Google lai.
- De dung lau dai, can chuyen OAuth consent screen sang `In production`. Scope Gmail readonly la restricted, Google co the hien canh bao chua xac minh va ap dung gioi han nguoi dung cho app chua duoc xac minh.
