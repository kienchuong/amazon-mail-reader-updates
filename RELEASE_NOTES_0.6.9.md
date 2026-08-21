# Amazon Mail Reader 0.6.9

## Updater

- Fixed an update loop where the ZIP downloaded successfully but the old app folder remained installed.
- Waits for every app process to close before replacing program files.
- Retries file operations when Windows briefly holds the program directory.
- Restores the previous build and records an error if installation cannot complete.
- Removes the downloaded ZIP only after a successful installation.

Local account, mail, payment, database, and vault data remain unchanged.
