# AccessReviewAgent — Frontend only

A responsive **React + Vite** security dashboard built for the **existing** AccessReviewAgent FastAPI backend. No backend or database source code is included in this folder.

## What works with the current backend

- Admin token login via `GET /api/admin/summary` using `X-Admin-Token`.
- Live summary: devices with recorded events, cumulative event totals, number of stored snapshots and latest event timestamp.
- Searchable/sortable device list.
- Distribution chart based on actual per-device counts.
- Automatic summary refresh every 30 seconds.
- Export current summary as JSON or device counts as CSV.
- Overview, Devices, Access events, Accounts & roles, Access reviews, Reports, Settings navigation.

**Important:** The existing backend only exposes `/health`, `/api/admin/summary`, and its agent ingestion routes. It **does not** yet expose detailed events or account snapshots to admins or any review-workflow endpoints. The UI labels these sections as *API required* rather than displaying fictional information. Devices without events are not included in summary results, and recent activity does not prove that an agent is online.

## Run locally on Windows

Requires Node.js 20+ and npm.

```powershell
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173`. Enter your backend's `ADMIN_API_TOKEN` when prompted.

Local Vite server automatically proxies `/api/admin/summary` and `/health` to `https://host.pasinduudana.me`. To use another backend, set `DEV_API_ORIGIN` before running Vite (for example, `$env:DEV_API_ORIGIN='https://my-api.example.com'`).

## Deploy ONLY the frontend to Coolify

1. Push the `frontend/` folder to your GitHub repository.
2. Coolify → New Resource → Application → select your GitHub repository.
3. Build pack: **Dockerfile**.
4. **Base Directory:** `/frontend` (or `/` if your new repo contains only the contents of this frontend folder).
5. **Dockerfile location:** `Dockerfile` relative to the base directory.
6. Exposed port: **80**.
7. Domain: `https://dashboard.pasinduudana.me` (after configuring DNS and TLS).
8. Add environment variable `API_UPSTREAM=host.pasinduudana.me` (hostname only, no `https://` or path).
9. Deploy. Open the dashboard and enter the same `ADMIN_API_TOKEN` you configured on the existing backend.

**Do not paste your admin token into the build environment or source code.** It is entered into the UI at runtime and kept in memory, not local storage. Use HTTPS for both dashboard and backend.

### Why an Nginx proxy?

Your existing FastAPI backend does not configure browser CORS. The frontend container's Nginx proxies exactly `/health` and the read-only `/api/admin/summary` to the backend over HTTPS, so no backend CORS changes are necessary. `/api/agents/*` remains blocked by the frontend proxy; Windows/Linux agents should keep sending directly to `https://host.pasinduudana.me`.

If your backend hostname is different, change `API_UPSTREAM` in Coolify. For private-only backend endpoints with custom certificates, adapt the proxy to trust your CA rather than turning off TLS verification.

## Build check

```bash
npm install
npm run build
```

A production website is generated in `dist/`.

## Security notes

- This is an MVP, not a complete enterprise IAM or SOC console.
- The admin token is sent as the `X-Admin-Token` header through the same-origin proxy. It is cleared when the tab is reloaded or disconnected.
- Do not send a production admin token over plain HTTP.
- Consider server-side sessions, role-based authorization, rate limiting, and audit logging for a real enterprise deployment.
- CSV output escapes values that could execute as spreadsheet formulas.
