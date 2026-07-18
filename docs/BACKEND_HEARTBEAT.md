# Backend: ANPR agent heartbeat (remote monitoring)

Edge agents POST a health snapshot every 30s (configurable via `HEARTBEAT_INTERVAL_SECONDS`).
Staff can see whether the site PC, camera, and backend link are OK without VPN to `127.0.0.1:8080`.

## Agent → backend

**`POST /api/anpr/sites/:siteId/heartbeat`**

- Auth: same `Authorization: Bearer <ANPR_AGENT_TOKEN>` as events / expected-plates
- `:siteId` must match body `site.siteId` (e.g. `borlange`, `falun`)

Example payload (abbreviated):

```json
{
  "version": "1.0.20",
  "reportedAt": "2026-05-19T08:00:00.000Z",
  "uptimeSeconds": 3600,
  "agent": { "state": "running", "uptimeSeconds": 1800 },
  "site": { "siteId": "borlange", "cameraId": "entrance-1", "direction": "entry" },
  "camera": {
    "status": "connected",
    "lastFrameAt": "2026-05-19T07:59:55.000Z",
    "framesCaptured": 1204
  },
  "backend": { "ok": true, "code": "ok", "reachable": true },
  "lastDetection": { "plate": "ABC123", "seen_at": "2026-05-19T07:45:00.000Z" },
  "queue": { "size": 0 }
}
```

**Response:** `200` with `{ "ok": true }` (or store and return stored row).

## Staff → backend

**`GET /api/v1/staff/locations/:locationId/anpr-agent`**

- Auth: staff session (same as location dashboard)
- Resolve `locationId` → site slug (`borlange`, etc.) via existing location/anpr mapping
- Return latest heartbeat row for that site (or `404` / `{ "status": "never_seen" }`)

Suggested response shape:

```json
{
  "siteId": "borlange",
  "lastSeenAt": "2026-05-19T08:00:00.000Z",
  "agentVersion": "1.0.20",
  "summary": {
    "pc": "ok",
    "camera": "ok",
    "backend": "ok",
    "reading": "ok"
  },
  "agent": { "state": "running" },
  "camera": { "status": "connected", "lastFrameAt": "..." },
  "lastDetection": { "plate": "ABC123", "seen_at": "..." }
}
```

### Summary rules (server-side)

| Field | OK when | Warning | Error |
|-------|---------|---------|-------|
| `pc` | heartbeat &lt; 3 min ago | 3–10 min | &gt; 10 min or never |
| `camera` | `camera.status === "connected"` and `lastFrameAt` &lt; 2 min (only if `agent.state === "running"`) | stale frames or `reconnecting` | `disconnected` / `error` |
| `backend` | `backend.ok === true` in last heartbeat | — | `ok === false` |
| `reading` | `agent.state === "running"` | `stopped` | `error` |

## Storage (minimal)

Table `anpr_agent_heartbeats` (one row per site, upsert on each POST):

- `site_id` (PK)
- `location_id` (nullable FK, for staff queries)
- `reported_at`, `agent_version`, `payload` (jsonb) or normalized columns
- `created_at` / `updated_at`

Or Redis key `anpr:heartbeat:{siteId}` with TTL 15 minutes (staff sees “offline” when key missing).

## Railway HTTP logs (until staff UI exists)

Search:

```text
@method:POST borlange heartbeat
```

or:

```text
@path:/api/anpr/sites/borlange/heartbeat
```

One hit per minute ≈ agent + PC + network OK.

## NestJS sketch (`auto-care-joy`)

```typescript
// POST /api/anpr/sites/:siteId/heartbeat  — AnprAgentGuard
async upsertHeartbeat(siteId: string, body: AnprHeartbeatDto) {
  await this.anprService.saveHeartbeat(siteId, body);
  return { ok: true };
}

// GET /api/v1/staff/locations/:id/anpr-agent — StaffGuard
async getAgentStatus(locationId: string) {
  return this.anprService.getHeartbeatForLocation(locationId);
}
```

Deploy backend **before** rolling out agent builds that send heartbeats (otherwise agents log `heartbeat_failed` with 404).
