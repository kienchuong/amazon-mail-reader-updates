import { withSupabase } from "npm:@supabase/server";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, x-amr-sync-secret",
};

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {
  status,
  headers: { ...cors, "Content-Type": "application/json; charset=utf-8" },
});

export default {
  // The dashboard uses a private link token instead of Supabase user login.
  // verify_jwt must be disabled for this function in Supabase deployment settings.
  fetch: withSupabase({ auth: "none" }, async (request, ctx) => {
    if (request.method === "OPTIONS") return new Response("ok", { headers: cors });

    const dashboardToken = Deno.env.get("AMR_DASHBOARD_TOKEN") ?? "";
    if (request.method === "POST") {
      const syncSecret = Deno.env.get("AMR_SYNC_SECRET") ?? "";
      if (!syncSecret || request.headers.get("x-amr-sync-secret") !== syncSecret) {
        return json({ error: "Unauthorized" }, 401);
      }
      const payload = await request.json();
      if (!Array.isArray(payload.messages) || !Array.isArray(payload.payments)) {
        return json({ error: "Invalid snapshot" }, 400);
      }
      const { error } = await ctx.supabaseAdmin
        .from("amr_mobile_snapshot")
        .upsert({ id: true, payload, synced_at: new Date().toISOString() });
      return error ? json({ error: error.message }, 500) : json({
        ok: true,
        messages: payload.messages.length,
        payments: payload.payments.length,
      });
    }

    const url = new URL(request.url);
    if (url.searchParams.get("action") !== "snapshot" || !dashboardToken || url.searchParams.get("t") !== dashboardToken) {
      return json({ error: "Not found" }, 404);
    }
    const { data, error } = await ctx.supabaseAdmin
      .from("amr_mobile_snapshot")
      .select("payload")
      .eq("id", true)
      .maybeSingle();
    return error ? json({ error: error.message }, 500) : json(data?.payload ?? { meta: {}, messages: [], payments: [] });
  }),
};
