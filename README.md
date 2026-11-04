# AccessReviewAgent — Windows access-review prototype

This is a starter implementation of an **authorized Windows enterprise access-auditing agent**, plus its **FastAPI + PostgreSQL collector** for the Ubuntu VPS / Coolify. Install on **two test Windows PCs**. The agent is visible in Windows Services and the admin UI; no stealth persistence or keystroke/screenshot collection.

## Features implemented

- C# WinForms administrative setup application (`AccessReviewAgent.UI.exe`).
- Windows Service (`AccessReviewAgent.Service.exe`), always-on after Windows boot.
- Windows Security audit events: 4624, 4625, 4634, 4647, 4672, 4720, 4726, 4728, 4729, 4732, 4733, 4738, 4740, 4767, 4778, 4779.
- Poll every 5 seconds; read missed events after reboot by remembering the Windows event record ID.
- Capture **local** Windows user accounts and local groups/group memberships every 60 minutes.
- On first launch, start from the **current log position** instead of uploading old event history.
- SQLite queue survives network outages; POST with per-device bearer token over HTTPS; deduplication by event_uid on the server.
- FastAPI ingestion endpoints + PostgreSQL tables + protected admin stats endpoint.
- Windows installer PowerShell script and GitHub Actions self-contained Windows EXE build.

## Important scope limits

- This MVP reads **local Windows OS security events and local SAM accounts/groups** only. It does **not** enumerate all Active Directory, Azure/Entra, GitHub, cloud, SaaS or database entitlements; those need separate integrations.
- Windows auditing must be enabled by an authorized administrator to emit the expected events. Some events need additional OS policies; `4624` includes machine/network/service logons, **not necessarily human presence**. Use `logon_type` to distinguish them.
- Windows event records do not prove every application action. Inactivity can only be concluded **within monitored systems and the available collection window**.
- Sample backend and agent are a prototype, not a production security product. Review retention, key management, signed installers, least privilege, rate-limiting, vulnerability patching and data protection before use.

## Architecture

```
 Windows PC 01   Windows PC 02
    |                 |
 AccessReviewAgent Windows Service
    |       \        |
 Windows Security Events + local account/group snapshots
    |
 SQLite offline queue on each PC
    |
 HTTPS + per-device bearer token
    v
 Ubuntu VPS / Coolify: FastAPI container (:8000 internally)
    |
 Private PostgreSQL: agent_events, agent_snapshots
    |
 Your central access-review dashboard / rules engine (next stage)
```

## A. Build the Windows application (easy method: GitHub)

1. Create a **private GitHub repo** and upload the contents of this project folder, preserving `.github/workflows/build-windows.yml`.
2. In GitHub open **Actions → Build Windows Agent → Run workflow** (or push code to trigger build).
3. Open the successful workflow run, under **Artifacts** download `AccessReviewAgent-Windows-win-x64`.
4. Extract the downloaded artifact ZIP; inside the package are `service/`, `ui/`, `install-windows.ps1`, `uninstall-windows.ps1`, `enable-auditing.ps1`.
5. On each Windows 10/11 x64 test PC, open **PowerShell as Administrator**, `cd` to the extracted package and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install-windows.ps1
```

The script installs the background service, restricts the ProgramData configuration/token folder to Administrators + LocalSystem, and opens the UI. No .NET runtime installation should be needed for these self-contained builds.

**Local build alternative:** install the .NET 8 SDK on Windows, then run `./scripts/publish-windows.ps1` in PowerShell, from the project folder. This creates `AccessReviewAgent-Windows-win-x64.zip`.

> This repository includes **source code**, not a precompiled `.exe`. The Windows EXEs are produced when GitHub Actions or `dotnet publish` builds them. Source/build must be validated on Windows before use.

## B. VPS API deployment with your existing Coolify PostgreSQL

1. Put the `backend/` directory in a GitHub repository (or deploy from this same repo in Coolify with its **base directory** set to `backend`).
2. In Coolify create an Application using **Dockerfile** and its internal port `8000`.
3. Add environment variables (secrets):

```env
DATABASE_URL=postgresql://accessreview:YOUR_PASSWORD@your-private-postgres-host:5432/accessreview
AGENT_TOKENS_JSON={"WIN-01":"YOUR_LONG_RANDOM_TOKEN_1","WIN-02":"YOUR_DIFFERENT_LONG_RANDOM_TOKEN_2"}
ADMIN_API_TOKEN=ANOTHER_LONG_RANDOM_SECRET
```

The PostgreSQL user/database must exist. Use Coolify's **private database host**, not an exposed public PostgreSQL port. Set a Coolify HTTPS domain, for example `https://logs.example.com`, with a valid certificate.

To generate a token in Python:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

4. Deploy. Check: `https://logs.example.com/health` should return a JSON status.
5. On Windows PC 01 open the desktop UI and enter:

```
Server URL : https://logs.example.com
Device ID  : WIN-01
Agent Token: YOUR_LONG_RANDOM_TOKEN_1
```

Click **Save Settings** and **Test API** (authenticated token test). Repeat on PC 02, using `WIN-02` and its own token.

6. Optionally enable relevant audit policies on authorized English-language Windows test PCs:

```powershell
.\enable-auditing.ps1
```

7. On Windows, lock/unlock the PC, log in, or deliberately try a failed login. The service polls and sends those events. To inspect service status use the desktop UI or:

```powershell
Get-Service AccessReviewAgent
```

8. Use the private PostgreSQL query tool in Coolify to verify:

```sql
SELECT device_id, event_id, event_category, username, occurred_at_utc
FROM agent_events
ORDER BY occurred_at_utc DESC LIMIT 20;

SELECT device_id, collected_at_utc, jsonb_array_length(payload->'accounts') AS account_count
FROM agent_snapshots
ORDER BY collected_at_utc DESC LIMIT 10;
```

Alternatively, protected admin endpoint:

```bash
curl -H 'X-Admin-Token: YOUR_ADMIN_API_TOKEN' https://logs.example.com/api/admin/summary
```

## C. Common issues

| Problem | Checks |
| --- | --- |
| UI `Test API` fails | Check Coolify HTTPS URL, backend `/health`, DNS, per-device token and `AGENT_TOKENS_JSON` |
| Service `Not installed` | Run `install-windows.ps1` as Administrator from compiled Windows ZIP |
| No login events | Confirm Security auditing is enabled, service is Running, wait for **new** login events; first run skips old history |
| Event queue not draining | Check backend 401/500 error in UI, PostgreSQL connectivity, reverse proxy HTTPS |
| `Invalid settings` | Use HTTPS, valid device id and a token; don't put a path like `/api` in Server URL |
| Local users snapshot missing | Service must have permissions; system service uses LocalSystem; domain members may be temporarily unreachable |
| Build fails | See GitHub Actions compile log; run a Windows validation build and adjust SDK/API differences |

## D. Security and privacy

- Run only on organization-owned, appropriately approved test endpoints with clear employee notice.
- Only Security access events and **local** account/group data are collected. No browsing, screenshots, keystrokes, user files or message content.
- TLS certificate checking is enabled; no hard-coded shared API secrets in source.
- Store tokens using OS ACLs. For production, replace plaintext token storage with protected secrets or certificate-based auth.
- Restrict PostgreSQL to an internal network and secure dashboard/admin endpoints with RBAC, audit trails and retention policy.
- Review uploaded events, account SIDs and source IPs as personal data; purge based on an approved retention policy.
- This prototype performs **read-only** access governance data collection; it never disables accounts or removes access.

## E. Suggested next features

- Correlate employee IDs across Windows, Linux, GitHub, AD and cloud resources.
- Join access entitlements with HR employment status for orphan/termination detection.
- Rules: inactive account, unapproved administrator, failed logon burst, access after employment end, excessive permissions.
- Dashboard and workflow for reviewer approval + audit-ready exports.

---

## F. Linux version (Ubuntu/Debian systemd)

This repository also includes `linux/`, a **compatible Linux agent** that sends Linux SSH/login/sudo and local-account/group snapshot data to the **same VPS FastAPI + PostgreSQL collector**, using `LINUX-01` / `LINUX-02` device IDs and separate access tokens.

Linux runs as a visible `systemd` service, with a simple **optional desktop status UI**. There are no required pip dependencies: Python 3, SQLite, journald and systemd are enough for the background collector.

1. Extend the Coolify `AGENT_TOKENS_JSON` environment variable to include `LINUX-01` and `LINUX-02` with independent tokens; redeploy the backend.
2. For a straightforward Ubuntu installer, download `AccessReviewAgent-Linux_0.1.0_all.deb`, then run:

   ```bash
   sudo apt install ./AccessReviewAgent-Linux_0.1.0_all.deb
   sudo python3 /opt/accessreview-agent/configure.py
   sudo systemctl enable --now accessreview-agent
   ```

   Alternatively, extract `AccessReviewAgent-Linux.zip`, open a terminal in the `linux/` folder, and run:

   ```bash
   chmod +x install-linux.sh
   sudo ./install-linux.sh
   ```

3. Enter the **HTTPS API domain**, unique Linux device ID and corresponding token when prompted. The installer enables the background service.
4. Verify:

   ```bash
   sudo systemctl status accessreview-agent --no-pager
   sudo python3 /opt/accessreview-agent/agent.py test-api
   sudo python3 /opt/accessreview-agent/agent.py status
   ```

5. On Ubuntu Desktop, look for **AccessReviewAgent** in Applications. If the status GUI needs tkinter, install the optional `python3-tk` system package.

See [`linux/README.md`](linux/README.md) for the precise event IDs, security scope, troubleshooting, privacy limits and uninstall instructions. **Use on authorized test machines only.** Linux journald coverage may require SSH/PAM audit settings and varies across distributions; this does not yet enumerate enterprise IAM, GitHub or database entitlements.
