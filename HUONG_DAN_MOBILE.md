# Mobile Dashboard

Mobile Dashboard la trang web rieng cho dien thoai. Dien thoai khong dang nhap Gmail, Outlook hoac Yahoo. App PC gui snapshot chi-doc qua Cloudflare Worker va D1; Google Sheet van chi dung cho bao cao payment.

## Cai dat backend

Lam theo `HUONG_DAN_CLOUDFLARE.md` de tao Worker, D1 va hai secret rieng. Khong dan Cloudflare API token vao app PC.

## Cau hinh tren PC

1. Mo **Cai dat** > **Mobile Dashboard - Cloudflare**.
2. Dien `Cloudflare Worker URL` do Cloudflare cap.
3. Dien Dashboard URL GitHub Pages, trong do tham so `api` tro den Worker va `t` la dashboard token.
4. Dien `Sync Secret` dung bang `AMR_SYNC_SECRET` cua Worker.
5. Giu timeout mac dinh 20 giay, sau do bam **Luu cau hinh**.
6. Bam **Dong bo ngay** hoac bat **Tu dong dong bo sau khi quet**.
7. Bam **Mo dashboard**, sau do mo cung URL nay tren dien thoai.

## Them shortcut

- Android Chrome: mo menu 3 cham > **Them vao man hinh chinh**.
- iPhone Safari: bam **Chia se** > **Them vao Man hinh chinh**.
- Mac Safari/Chrome: mo URL va dung **Add to Dock** hoac **Create shortcut**.

## An toan

- App dien thoai chi doc snapshot do PC dong bo; khong co thong tin dang nhap email.
- Dashboard khong co chuc nang gui, xoa hoac sua mail.
- Dashboard URL chua token xem rieng. Khong chia se link nay.
- Neu lo link, doi `AMR_DASHBOARD_TOKEN` tai Worker va cap nhat Dashboard URL.
- Neu lo Sync Secret, doi `AMR_SYNC_SECRET` tai Worker va cap nhat Sync Secret trong app PC.
