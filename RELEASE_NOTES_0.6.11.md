# Amazon Mail Reader 0.6.11

## Updater

- Fixed an installer lock caused by PowerShell inheriting the application directory as its working directory.
- Kept bounded retries, rollback, and error logging from the previous updater fixes.
- Downloaded ZIP files are removed only after a successful installation.

Existing accounts, mail data, OAuth tokens, and settings remain in the external data directory.
