-- Logical single-snapshot schema. Large JSON payloads are split into rows to
-- stay below Cloudflare D1's 2 MB per-string/per-row limit.
CREATE TABLE IF NOT EXISTS amr_mobile_snapshot (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  payload TEXT CHECK (payload IS NULL OR json_valid(payload)),
  chunk_count INTEGER NOT NULL DEFAULT 0 CHECK (chunk_count >= 0),
  payload_size_bytes INTEGER NOT NULL DEFAULT 0 CHECK (payload_size_bytes >= 0),
  synced_at TEXT NOT NULL,
  CHECK (payload IS NOT NULL OR chunk_count > 0)
);

CREATE TABLE IF NOT EXISTS amr_mobile_snapshot_chunk (
  snapshot_id INTEGER NOT NULL CHECK (snapshot_id = 1),
  chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
  payload_chunk TEXT NOT NULL,
  PRIMARY KEY (snapshot_id, chunk_index),
  FOREIGN KEY (snapshot_id) REFERENCES amr_mobile_snapshot(id) ON DELETE CASCADE
);
