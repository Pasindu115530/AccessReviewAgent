# AccessReviewAgent — ඉක්මන් Setup Guide

මෙය Windows PC එකක login / failed login / logout / access changes සහ local user/group permissions VPS එකට යවන **prototype agent එකක්**. ඒකට Windows background service එකක් සහ settings දාන්න GUI එකක් තියෙනවා.

## 1) Windows EXE එක GitHub හරහා build කරන්න

1. මේ project folder එක private GitHub repository එකකට upload කරන්න (`.github` folder එකත් ඇතුළුව).
2. GitHub → **Actions** → **Build Windows Agent** → **Run workflow**.
3. Run එක සාර්ථක වුණාට පස්සේ **Artifacts** section එකේ `AccessReviewAgent-Windows-win-x64` download කරන්න.
4. ZIP extract කරන්න. `service`, `ui`, `install-windows.ps1` files ලැබේවි.
5. Windows 10/11 PC එකේ PowerShell **Run as Administrator**:

```powershell
cd "C:\path\to\extracted-folder"
Set-ExecutionPolicy -Scope Process Bypass
.\install-windows.ps1
```

## 2) Coolify VPS API එක deploy කරන්න

1. Coolify → **New Application** → GitHub repo → Dockerfile (`backend/Dockerfile`; base directory `backend`) → internal port `8000`.
2. කලින් තියෙන PostgreSQL එකේ private hostname එක යොදාගෙන environment variables දාන්න:

```text
DATABASE_URL=postgresql://accessreview:PASSWORD@postgres-host:5432/accessreview
AGENT_TOKENS_JSON={"WIN-01":"TOKEN_01","WIN-02":"TOKEN_02"}
ADMIN_API_TOKEN=ADMIN_SECRET
```

3. **HTTPS domain** එක configure කරලා deploy කරන්න. `https://YOUR-DOMAIN/health` එකෙන් check කරන්න. Existing applications overwrite නොකර වෙනම service එකක් ලෙසත් deploy කරන්න පුළුවන්.

## 3) Windows app එක configure කරන්න

Windows app එකේ:

- **Server URL:** `https://YOUR-DOMAIN`
- **Device ID:** `WIN-01`
- **Agent Token:** `TOKEN_01`
- Click **Save Settings** → **Test API**.

Authorized test PC එකේ auditing enable කරන්න:

```powershell
.\enable-auditing.ps1
```

PC lock/unlock කරලා අලුත් events generate කරන්න. App එකේ **Uploaded events** value වැඩි වෙන්න ඕන. Windows PC 02 එකට `WIN-02` සහ `TOKEN_02` දාලා repeat කරන්න.

## 4) Database එකේ confirm කරන්න

```sql
SELECT device_id, event_id, username, occurred_at_utc
FROM agent_events ORDER BY occurred_at_utc DESC LIMIT 20;
```

**සැලකිලිමත් වන්න:** මේක තමන්ට අයිති / අවසර තියෙන test PCs වලට පමණක් install කරන්න. Domain / GitHub / cloud entitlements integration තවම මේ MVP එකේ නැහැ. මේ folder එක source code; compiled EXE එක GitHub Actions හෝ Windows .NET SDK build කිරීමෙන් ලැබෙනවා.

## 5) Ubuntu / Linux agent එක install කිරීම

Linux PC 01 / PC 02 සඳහා **same VPS API එකම** භාවිතා කරනවා. Coolify හි `AGENT_TOKENS_JSON` එකට වෙනම devices දෙකක් add කරන්න:

```env
AGENT_TOKENS_JSON={"WIN-01":"WIN_TOKEN_1","WIN-02":"WIN_TOKEN_2","LINUX-01":"LINUX_TOKEN_1","LINUX-02":"LINUX_TOKEN_2"}
```

මෙහි token strings උදාහරණ පමණි. සෑම device එකකටම unique, strong random token එකක් generate කරන්න. Coolify backend නැවත deploy කරන්න.

**Easy Ubuntu .deb method:** `AccessReviewAgent-Linux_0.1.0_all.deb` download කරලා එහි directory එකේ:

```bash
sudo apt install ./AccessReviewAgent-Linux_0.1.0_all.deb
sudo python3 /opt/accessreview-agent/configure.py
sudo systemctl enable --now accessreview-agent
```

**Alternative ZIP method:** Linux machine එකේ `AccessReviewAgent-Linux.zip` extract කරලා, `linux/` directory එකෙන්:

```bash
chmod +x install-linux.sh
sudo ./install-linux.sh
```

Prompts එනකොට `https://YOUR-DOMAIN`, `LINUX-01` (දෙවෙනි PC එකට `LINUX-02`) සහ අදාල token එක දෙන්න. Installer එකෙන් systemd background service එක enable වෙනවා. Check කරන්න:

```bash
sudo systemctl status accessreview-agent --no-pager
sudo python3 /opt/accessreview-agent/agent.py test-api
sudo python3 /opt/accessreview-agent/agent.py status
sudo journalctl -u accessreview-agent -n 30 --no-pager
```

Ubuntu Desktop එකේ `AccessReviewAgent` status UI එකක් තියෙනවා (`sudo apt install python3-tk` optional dependency). SSH login එකක් test කරලා `agent_events` table එකේ `LINUX-01` records check කරන්න. Linux Event IDs Windows event IDs නොවෙයි: Linux agent එක synthetic event IDs `1001`–`1202` භාවිතා කරනවා. **Linux user activity එකේ සෑම දෙයක්ම collect වෙන්නේ නැහැ**; journald එකේ audit/login events සහ local accounts/groups විතරයි. See `linux/README.md`.
