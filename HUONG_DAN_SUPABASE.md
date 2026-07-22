# Mobile Dashboard Supabase

Mobile Dashboard nay khong dung Google Sheet hoac Google Apps Script.

## 1. Tao project

1. Vao https://supabase.com/dashboard va tao mot project moi.
2. Mo `SQL Editor` -> `New query`.
3. Mo file `supabase/schema.sql` trong thu muc app, copy toan bo va bam `Run`.

## 2. Tao Edge Function

1. Trong Supabase, mo `Edge Functions` -> `Create a new function`.
2. Dat ten: `mobile-dashboard`.
3. Mo file `supabase/functions/mobile-dashboard/index.ts` trong thu muc app, copy toan bo vao editor.
4. Tat yeu cau JWT cho function nay, roi deploy. Function chi la API JSON; giao dien mobile nam tren GitHub Pages nen khong bi Supabase doi HTML thanh text.

## 3. Tao ba secret

Trong `Edge Functions` -> `Secrets`, them cac gia tri sau:

- `AMR_SYNC_SECRET`: mot chuoi dai, chi dung trong app PC.
- `AMR_DASHBOARD_TOKEN`: mot chuoi dai khac, dung trong link dien thoai.

Khong chia se hai gia tri nay. Co the dung mat khau dai tu trinh quan ly mat khau de tao.

## 4. Dien vao app PC

Trong `Cai dat` -> `Mobile Dashboard`:

- `Supabase Function URL`:
  `https://PROJECT_REF.supabase.co/functions/v1/mobile-dashboard`
- `Dashboard URL`:
  `https://kienchuong.github.io/amazon-mail-reader-updates/mobile/#api=https://PROJECT_REF.supabase.co/functions/v1/mobile-dashboard&t=AMR_DASHBOARD_TOKEN`
- `Sync Secret`: gia tri `AMR_SYNC_SECRET`.

`PROJECT_REF` nam trong URL project Supabase hoac `Settings` -> `General`.

Bam `Luu cau hinh`, sau do bam `Dong bo ngay`. Dien thoai chi can mo `Dashboard URL` va them shortcut vao man hinh chinh.

## 5. Bat GitHub Pages mot lan

Trong repo `amazon-mail-reader-updates`: `Settings` -> `Pages` -> Source chon `Deploy from a branch` -> branch `main` va folder `/docs` -> `Save`.
Sau vai phut, dia chi dashboard o tren se hoat dong.

## Luu y bao mat

Dashboard khong dung PIN theo yeu cau. Bat ky ai co Dashboard URL deu co the xem snapshot mail hien tai, nhung khong the gui, xoa, sua mail hay sua du lieu tren PC. Neu lo link, doi `AMR_DASHBOARD_TOKEN` trong Supabase Secrets, deploy lai function va cap nhat Dashboard URL tren PC.
