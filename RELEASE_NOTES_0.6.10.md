# Amazon Mail Reader 0.6.10

## Updater

- Fixes the remaining Windows update blocker caused by an unrelated process match.
- Waits for the running app process, then uses bounded filesystem retries as the authoritative lock check.
- Preserves automatic rollback and detailed error logging.
- Removes the downloaded ZIP only after installation succeeds.

Local account, mail, payment, database, and vault data remain unchanged.
