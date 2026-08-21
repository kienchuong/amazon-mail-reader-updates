export interface Env {
  DB: D1Database;
  AMR_SYNC_SECRET: string;
  AMR_DASHBOARD_TOKEN: string;
}

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, x-amr-sync-secret",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

const MAX_INLINE_BYTES = 1_000_000;
const CHUNK_CHARACTERS = 400_000;

function json(value: unknown, status = 200): Response {
  return Response.json(value, { status, headers: cors });
}

function sameSecret(actual: string | null, expected: string): boolean {
  if (!actual || !expected || actual.length !== expected.length) return false;
  let difference = 0;
  for (let index = 0; index < actual.length; index += 1) {
    difference |= actual.charCodeAt(index) ^ expected.charCodeAt(index);
  }
  return difference === 0;
}

function validSnapshot(value: unknown): value is Record<string, unknown> & {
  messages: unknown[];
  payments: unknown[];
} {
  if (!value || typeof value !== "object") return false;
  const snapshot = value as Record<string, unknown>;
  return Array.isArray(snapshot.messages) && Array.isArray(snapshot.payments);
}

function splitPayload(value: string): string[] {
  const chunks: string[] = [];
  for (let start = 0; start < value.length;) {
    let end = Math.min(start + CHUNK_CHARACTERS, value.length);
    if (end < value.length) {
      const lastCodeUnit = value.charCodeAt(end - 1);
      if (lastCodeUnit >= 0xD800 && lastCodeUnit <= 0xDBFF) end -= 1;
    }
    chunks.push(value.slice(start, end));
    start = end;
  }
  return chunks;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (request.method === "GET" && path.endsWith("/health")) {
      try {
        await env.DB.prepare("SELECT 1 AS ok").first();
        return json({ ok: true, service: "amazon-mail-reader-mobile", database: "connected" });
      } catch {
        return json({ ok: false, service: "amazon-mail-reader-mobile", database: "unavailable" }, 503);
      }
    }

    if (request.method === "POST" && (path === "/" || path.endsWith("/snapshot"))) {
      if (!sameSecret(request.headers.get("x-amr-sync-secret"), env.AMR_SYNC_SECRET ?? "")) {
        return json({ error: "Unauthorized" }, 401);
      }

      let snapshot: unknown;
      try {
        snapshot = await request.json();
      } catch {
        return json({ error: "Malformed JSON" }, 400);
      }
      if (!validSnapshot(snapshot)) return json({ error: "Invalid snapshot" }, 400);

      const syncedAt = new Date().toISOString();
      const serialized = JSON.stringify(snapshot);
      const payloadSizeBytes = new TextEncoder().encode(serialized).byteLength;
      const chunks = payloadSizeBytes > MAX_INLINE_BYTES ? splitPayload(serialized) : [];
      const inlinePayload = chunks.length ? null : serialized;
      const statements = [
        env.DB.prepare(
          `INSERT INTO amr_mobile_snapshot
             (id, payload, chunk_count, payload_size_bytes, synced_at)
           VALUES (1, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             payload = excluded.payload,
             chunk_count = excluded.chunk_count,
             payload_size_bytes = excluded.payload_size_bytes,
             synced_at = excluded.synced_at`,
        ).bind(inlinePayload, chunks.length, payloadSizeBytes, syncedAt),
        env.DB.prepare("DELETE FROM amr_mobile_snapshot_chunk WHERE snapshot_id = 1"),
        ...chunks.map((chunk, index) => env.DB.prepare(
          `INSERT INTO amr_mobile_snapshot_chunk (snapshot_id, chunk_index, payload_chunk)
           VALUES (1, ?, ?)`,
        ).bind(index, chunk)),
      ];
      try {
        await env.DB.batch(statements);
      } catch {
        return json({ error: "Snapshot database write failed" }, 503);
      }

      return json({
        ok: true,
        messages: snapshot.messages.length,
        payments: snapshot.payments.length,
        synced_at: syncedAt,
      });
    }

    const readsSnapshot = request.method === "GET"
      && (path.endsWith("/snapshot") || url.searchParams.get("action") === "snapshot");
    if (readsSnapshot) {
      if (!sameSecret(url.searchParams.get("t"), env.AMR_DASHBOARD_TOKEN ?? "")) {
        return json({ error: "Not found" }, 404);
      }
      let row: { payload: string | null; chunk_count: number } | null;
      try {
        row = await env.DB.prepare(
          "SELECT payload, chunk_count FROM amr_mobile_snapshot WHERE id = 1",
        ).first<{ payload: string | null; chunk_count: number }>();
      } catch {
        return json({ error: "Snapshot database read failed" }, 503);
      }
      if (!row) return json({ range_days: 7, synced_at: "", messages: [], payments: [] });
      let serialized = row.payload;
      if (serialized === null) {
        let chunkRows: Array<{ payload_chunk: string }>;
        try {
          const result = await env.DB.prepare(
            `SELECT payload_chunk FROM amr_mobile_snapshot_chunk
             WHERE snapshot_id = 1 ORDER BY chunk_index ASC`,
          ).all<{ payload_chunk: string }>();
          chunkRows = result.results;
        } catch {
          return json({ error: "Snapshot chunks could not be read" }, 503);
        }
        if (chunkRows.length !== row.chunk_count) {
          return json({ error: "Stored snapshot is incomplete" }, 500);
        }
        serialized = chunkRows.map((item) => item.payload_chunk).join("");
      }
      try {
        return json(JSON.parse(serialized));
      } catch {
        return json({ error: "Stored snapshot is malformed" }, 500);
      }
    }

    return json({ error: "Not found" }, 404);
  },
};
