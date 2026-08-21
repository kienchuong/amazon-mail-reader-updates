## UI

- Migrated the desktop interface to PySide6.
- Improved table behavior and Windows DPI support.
- Added a consistent application icon for the window, taskbar, and launcher.

## Mobile Sync

- Replaced the inactive Supabase mobile sync with Cloudflare Worker and D1.
- Kept the existing Mobile Dashboard workflow through the new backend.

## Payment

- Fixed false-positive Payment classification.
- Recognizes `Remittance Advice` payment notices correctly.
- Excludes payment-declined notices and support `[CASE]` threads from Payment.

## Stability

- Existing local account and mail data remain compatible.
- The canonical Windows launcher opens the app without a command window.
