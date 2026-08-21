# Mobile Dashboard Cloudflare

Backend moi chi giu snapshot mobile moi nhat. Database local, account, OAuth token va App Password van nam tren PC.

## Resource can tao

- Worker: `amazon-mail-reader-mobile`
- D1 database: `amazon-mail-reader-mobile`
- D1 binding trong Worker: `DB`
- Worker secrets: `AMR_SYNC_SECRET`, `AMR_DASHBOARD_TOKEN`
- Environment: production mac dinh

Khong dung Cloudflare Global API Key hoac API token quyen cao trong app PC.

## Trien khai bang Wrangler

Thuc hien trong thu muc `cloudflare/worker` sau khi da dang nhap dung Cloudflare account:

```powershell
npx wrangler login
npx wrangler d1 create amazon-mail-reader-mobile
```

Copy `database_id` Cloudflare tra ve vao `wrangler.toml`, sau do:

```powershell
npx wrangler d1 migrations apply amazon-mail-reader-mobile --remote
npx wrangler secret put AMR_SYNC_SECRET
npx wrangler secret put AMR_DASHBOARD_TOKEN
npx wrangler deploy
```

Hai secret nen la hai chuoi ngau nhien khac nhau, toi thieu 32 ky tu. Khong commit secret vao Git.

## Kiem tra Worker

Mo:

```text
https://WORKER.workers.dev/health
```

Ket qua dung:

```json
{"ok":true,"service":"amazon-mail-reader-mobile","database":"connected"}
```

## Cau hinh app PC

Trong `Cai dat` > `Mobile Dashboard - Cloudflare`:

- Cloudflare Worker URL: `https://WORKER.workers.dev`
- Dashboard URL: `https://kienchuong.github.io/amazon-mail-reader-updates/mobile/#api=https%3A%2F%2FWORKER.workers.dev&t=DASHBOARD_TOKEN`
- Sync Secret: cung gia tri da dat cho `AMR_SYNC_SECRET`
- Timeout: `20`

Dashboard token trong URL phai dung bang `AMR_DASHBOARD_TOKEN`. Dashboard token chi cho phep doc snapshot; Sync Secret chi cho phep PC thay snapshot.

## D1 schema

Migration `cloudflare/migrations/0001_initial.sql` tao hai table:

```text
amr_mobile_snapshot
  id         INTEGER PRIMARY KEY, luon bang 1
  payload    TEXT JSON hop le neu snapshot nho
  chunk_count INTEGER so chunk neu snapshot lon
  payload_size_bytes INTEGER kich thuoc JSON UTF-8
  synced_at  TEXT ISO-8601 UTC

amr_mobile_snapshot_chunk
  snapshot_id INTEGER, luon bang 1
  chunk_index INTEGER
  payload_chunk TEXT
  PRIMARY KEY (snapshot_id, chunk_index)
```

Moi lan dong bo la mot D1 batch atomic: UPSERT id `1`, xoa chunk cu va ghi chunk moi. Snapshot moi thay snapshot cu va khong tao du lieu trung. Payload lon duoc chia chunk de khong vuot gioi han 2 MB moi row cua D1; JSON mobile khi doc ra van giu nguyen.
