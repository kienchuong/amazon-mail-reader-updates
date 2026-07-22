from __future__ import annotations

import json
import urllib.request


def post_mobile_snapshot(function_url: str, sync_secret: str, snapshot: dict) -> tuple[int, str]:
    """Send the current read-only mobile snapshot to a Supabase Edge Function."""
    data = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        function_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-amr-sync-secret": sync_secret,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.status, response.read().decode("utf-8", errors="replace")
