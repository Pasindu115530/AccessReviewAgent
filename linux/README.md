# AccessReviewAgent Linux — Ubuntu/Debian access review prototype

This is a **visible, read-only, authorized security-audit agent** for two Ubuntu Linux endpoints. It is compatible with the *same* FastAPI + PostgreSQL backend used by the companion Windows agent. It uses **Python 3 standard library only**, `journalctl`, `systemd` and SQLite; no Fluent Bit, Java, .NET or third-party pip dependencies.

## What it does

- Reads **new** `systemd-journald` entries every ~5 seconds and identifies SSH successful/failed login, SSH session close, interactive PAM login, sudo invocation (not command arguments), and account/group tool change events when present in the journal.
- Creates a local `/etc/passwd` and `/etc/group` account and membership snapshot every hour. Reports membership in `sudo` / `wheel` groups, **not a full effective sudoers/LDAP/PAM permissions audit**.
- Sends JSON events to `POST /api/agents/events` and account snapshots to `POST /api/agents/snapshot` using per-device bearer tokens over **TLS-verified HTTPS**. Authenticates via `/api/agents/ping` at startup and during idle periods.
- Buffers unsent records in an SQLite database, keeps a journal cursor across reboots, deduplicates by event UID on the existing VPS API, and starts at the latest record on the first run.
- Installs an auto-start `systemd` service, plus an **optional** Ubuntu desktop status window (requires `python3-tk`).
- **Does not** collect keystrokes, screenshots, browsing history, files, SSH keys, hashed passwords, full sudo commands, or any other full journal message. Does not change accounts or permissions.

## Quick install (Ubuntu 22.04/24.04 Desktop/Server, and comparable Debian systemd hosts)

**Simplest for Ubuntu: install the prebuilt `.deb` package**:

```bash
sudo apt install ./AccessReviewAgent-Linux_0.1.0_all.deb
sudo python3 /opt/accessreview-agent/configure.py
sudo systemctl enable --now accessreview-agent
sudo python3 /opt/accessreview-agent/agent.py test-api
```

The `.deb` is architecture-independent; it installs the files, service and optional desktop launcher but **does not automatically start collection until you configure credentials and enable the service**. Because this build was created for the prototype, it is **not signed or tested on a target Ubuntu desktop yet**; validate it on your own test PC before any larger rollout. Generate and register the Linux device's token in Coolify first, as explained next.

**Alternative: source ZIP installer**:

1. Deploy the included backend once to your Ubuntu VPS using the existing instructions. Add two distinct Linux device tokens to its Coolify environment variable:

   ```env
   AGENT_TOKENS_JSON={"WIN-01":"WINDOWS_TOKEN","WIN-02":"WINDOWS_TOKEN_2","LINUX-01":"LINUX_TOKEN_1","LINUX-02":"LINUX_TOKEN_2"}
   ```

   Each token should be an independently generated 32+ byte random value; the example values above are placeholders. Generate one with: `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`.

2. Download/extract **AccessReviewAgent-Linux.zip** onto each **authorized** Linux PC. In a terminal opened inside the extracted `linux/` folder:

   ```bash
   chmod +x install-linux.sh
   sudo ./install-linux.sh
   ```

3. When asked, supply the URL of your deployed HTTPS API (example: `https://logs.example.com`), device ID `LINUX-01` or `LINUX-02`, and the corresponding token from the VPS. The token is entered hidden and written to `/etc/accessreview-agent/config.json` (root read-only).

4. Service starts automatically. Check:

   ```bash
   sudo systemctl status accessreview-agent --no-pager
   sudo journalctl -u accessreview-agent -f
   sudo python3 /opt/accessreview-agent/agent.py test-api
   sudo python3 /opt/accessreview-agent/agent.py status
   ```

5. On Ubuntu Desktop, the launcher **AccessReviewAgent** displays read-only status and queue size. If it cannot open, install the optional Tk UI dependency: `sudo apt install python3-tk`.

6. Trigger a test login through SSH to your Ubuntu test machine, or run a harmless authorized `sudo -l` command. After a short interval, use Coolify/PostgreSQL:

   ```sql
   SELECT device_id, event_id, event_category, username, source_ip, occurred_at_utc
   FROM agent_events ORDER BY occurred_at_utc DESC LIMIT 30;

   SELECT device_id, collected_at_utc,
          jsonb_array_length(payload->'accounts') AS accounts,
          jsonb_array_length(payload->'groups') AS groups
   FROM agent_snapshots ORDER BY collected_at_utc DESC LIMIT 10;
   ```

   Or query the protected backend `/api/admin/summary` with its `X-Admin-Token` header.

## Modify settings, restart, uninstall

```bash
sudo python3 /opt/accessreview-agent/configure.py
sudo systemctl restart accessreview-agent
sudo systemctl stop accessreview-agent
sudo systemctl start accessreview-agent
sudo ./uninstall-linux.sh
```

The uninstall script leaves the private configuration and SQLite queue in place to avoid accidental data loss. Deleting those paths is an **intentional, separate** administrative step.

## Event IDs (Linux-specific; synthetic IDs for compatibility with Windows API schema)

| ID | Category | Linux source |
| --- | --- | --- |
| 1001 | `login_success` | SSH accepted authentication |
| 1002 | `login_failed` | SSH failed/invalid-user authentication |
| 1003 | `logout` | SSH PAM session closed |
| 1010 | `login_success` | PAM interactive login/su session opened |
| 1101 | `privileged_action` | A sudo invocation (command string excluded) |
| 1201 | `account_changed` | useradd/usermod/userdel/passwd/chage tools when journalled |
| 1202 | `group_changed` | groupadd/groupmod/groupdel/gpasswd tools when journalled |

**Important coverage limits:** The agent monitors events **written into systemd-journald**. Whether these entries exist depends on OS version, SSH/PAM/audit configuration, and local logging policy. Successful SSH logins can be checked from `sudo journalctl -u ssh -n 30`, and authentication-related journal messages from `sudo journalctl -t sudo -n 30`. Direct edits to `/etc/passwd`, permissions configured outside `sudo`/`wheel`, AD/LDAP identity, Docker/Kubernetes/GitHub and DB roles are **not** fully covered. Account-change events may not be emitted on some distributions; the hourly local snapshot still captures local account state changes. Journal retention/rotation can create gaps; this MVP does not backfill rotated-away data.

## HTTPS, privacy, and authorization

- Use only on organization-owned machines with appropriate permission and employee notice. This is not a covert monitoring agent.
- Create separate API tokens for each machine and don't publish them to GitHub or logs. The installed config is root-only (`0600`).
- Only authenticated, TLS-verified HTTPS and a private PostgreSQL backend are supported. Don't expose PostgreSQL publicly.
- Agent runs as root for access to system journal and account metadata. The service has basic systemd sandboxing; perform a proper least-privilege hardening review before production.
- **Status file**, accessible from the optional desktop GUI, only contains connection/queue/hostname information; **token and collected logs stay private**.
- Don't treat journal inactivity as proof an employee hasn't used other apps; access reviews must combine observed usage with authoritative entitlement lists.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No events | Confirm `journalctl -u ssh` contains SSH records; restart after enabling SSH/PAM logging. First start intentionally skips historical events. |
| HTTP 401 | Check the `AGENT_TOKENS_JSON` device/token pair in Coolify and restart the backend after changing it. |
| No GUI | `sudo apt install python3-tk`, or use the CLI instead. |
| API SSL error | Use a valid HTTPS domain with a trusted certificate. Do not disable certificate verification. |
| Queue increasing | Network/backend unavailable or token invalid; inspect `sudo journalctl -u accessreview-agent -n 40`. |
| journal access denied | Verify service is root and inspect the systemd journal configuration. |

## Source and testing

`agent.py` (journal classifier, SQLite queue, TLS API client), `configure.py` (root-only setup), `desktop.py` (optional status UI), scripts and systemd unit. Built-in unit tests:

```bash
python3 -m unittest discover -s tests -v
bash -n install-linux.sh uninstall-linux.sh
```

This is a starter prototype, **not** a production-ready EDR / SIEM agent. Build an approved retention and data-minimization policy before collecting real employee security data.
