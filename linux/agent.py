#!/usr/bin/env python3
"""AccessReviewAgent for systemd Linux — authorized access-log collection.

Python 3 standard library only. Sends the same event/snapshot schema consumed
by the existing AccessReviewAgent FastAPI backend. Never reads file contents,
browsing history, keys or password hashes. Does not remediate accounts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import socket
import sqlite3
import ssl
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

LOG = logging.getLogger("accessreview")
DEFAULT_CONFIG = "/etc/accessreview-agent/config.json"
DEFAULT_STATE = "/var/lib/accessreview-agent"
SUDO_GROUPS = {"sudo", "wheel"}
SSH_ACCEPT = re.compile(r"^Accepted \S+ for (?P<user>[^\s]+) from (?P<ip>\S+)", re.I)
SSH_FAILED = re.compile(r"^Failed \S+ for (?:invalid user )?(?P<user>[^\s]+) from (?P<ip>\S+)", re.I)
SSH_INVALID = re.compile(r"^Invalid user (?P<user>[^\s]+) from (?P<ip>\S+)", re.I)
SSH_CLOSED = re.compile(r"session closed for user (?P<user>[^\s(]+)", re.I)
PAM_OPEN = re.compile(r"pam_unix\((?P<via>[^:]+):session\): session opened for user (?P<user>[^\s(]+)", re.I)
SUDO_EXEC = re.compile(r"^\s*(?P<user>[^\s:]+)\s*:\s*TTY=.*?;\s*PWD=.*?;\s*USER=(?P<target>[^\s;]+)\s*;\s*COMMAND=", re.I)
ACCOUNT_TOOLS = {"useradd", "userdel", "usermod", "passwd", "chage", "adduser", "deluser"}
GROUP_TOOLS = {"groupadd", "groupdel", "groupmod", "gpasswd", "addgroup", "delgroup"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_config(raw: dict) -> dict:
    for field in ("server_url", "device_id", "agent_token"):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise ValueError(f"Configuration requires {field}")
    url = raw["server_url"].strip().rstrip("/")
    p = urlsplit(url)
    if (p.scheme != "https" or not p.hostname or p.username or p.password
            or p.query or p.fragment or p.path not in ("", "/")):
        raise ValueError("Server URL must be an HTTPS origin like https://logs.example.com")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", raw["device_id"]):
        raise ValueError("Device ID can contain letters, numbers, _, . and -")
    if len(raw["agent_token"]) < 24:
        raise ValueError("Agent token must be at least 24 characters")
    return {"server_url": url, "device_id": raw["device_id"],
            "agent_token": raw["agent_token"]}


def load_config(path: str) -> dict:
    return validate_config(json.loads(Path(path).read_text(encoding="utf-8")))


def api_post(cfg: dict, endpoint: str, data: dict) -> dict:
    request = Request(
        cfg["server_url"] + endpoint,
        data=json.dumps(data, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + cfg["agent_token"]},
        method="POST",
    )
    # urllib verifies the HTTPS server certificate and hostname by default.
    with urlopen(request, timeout=15, context=ssl.create_default_context()) as response:
        if not (200 <= response.status < 300):
            raise RuntimeError(f"HTTP {response.status}")
        return json.load(response)


class QueueStore:
    def __init__(self, state_dir: str):
        state = Path(state_dir)
        state.mkdir(parents=True, exist_ok=True)
        self.state = state
        self.conn = sqlite3.connect(state / "queue.sqlite3", timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.executescript("""
          CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events (
            uid TEXT PRIMARY KEY, body TEXT NOT NULL, saved_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS snapshots (
            collected_at TEXT PRIMARY KEY, body TEXT NOT NULL);
        """)

    def close(self):
        self.conn.close()

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str):
        with self.conn:
            self.conn.execute("INSERT INTO metadata(key,value) VALUES(?,?) "
                              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def save_entry(self, cursor: str, payload: dict | None):
        # The durable journal cursor and queued event commit in one transaction.
        with self.conn:
            if payload:
                self.conn.execute("INSERT OR IGNORE INTO events(uid,body,saved_at) VALUES(?,?,?)",
                                  (payload["event_uid"], json.dumps(payload), utc_now()))
            self.conn.execute("INSERT INTO metadata(key,value) VALUES('journal_cursor',?) "
                              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (cursor,))

    def save_snapshot(self, data: dict):
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO snapshots(collected_at,body) VALUES(?,?)",
                              (data["collected_at_utc"], json.dumps(data)))

    def batch_events(self, limit=100):
        return [(uid, json.loads(body)) for uid, body in self.conn.execute(
            "SELECT uid,body FROM events ORDER BY rowid LIMIT ?", (limit,)).fetchall()]

    def ack_events(self, uids):
        with self.conn:
            self.conn.executemany("DELETE FROM events WHERE uid=?", [(x,) for x in uids])

    def pending_snapshots(self, limit=5):
        return [(date, json.loads(body)) for date, body in self.conn.execute(
            "SELECT collected_at,body FROM snapshots ORDER BY collected_at LIMIT ?", (limit,)).fetchall()]

    def ack_snapshot(self, collected_at):
        with self.conn:
            self.conn.execute("DELETE FROM snapshots WHERE collected_at=?", (collected_at,))

    def pending_counts(self):
        ev = self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        sn = self.conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        return ev, sn


def classify_journal(entry: dict, device_id: str) -> dict | None:
    msg = entry.get("MESSAGE", "")
    if not isinstance(msg, str):
        return None
    identifier = str(entry.get("SYSLOG_IDENTIFIER", "")).lower()
    unit = str(entry.get("_SYSTEMD_UNIT", ""))
    exe = str(entry.get("_COMM", "")).lower()
    category = None
    eid = None
    username = None
    source_ip = None
    detail = {"source": "systemd-journal"}
    if (identifier in ("sshd", "ssh") or exe == "sshd" or unit in ("ssh.service", "sshd.service")):
        m = SSH_ACCEPT.search(msg)
        if m:
            category, eid = "login_success", 1001
            username, source_ip = m["user"], m["ip"]
            detail["method"] = "ssh"
        else:
            m = SSH_FAILED.search(msg) or SSH_INVALID.search(msg)
            if m:
                category, eid = "login_failed", 1002
                username, source_ip = m["user"], m["ip"]
                detail["method"] = "ssh"
            else:
                m = SSH_CLOSED.search(msg)
                if m:
                    category, eid = "logout", 1003
                    username = m["user"]
                    detail["method"] = "ssh"
    if not category and identifier == "sudo":
        m = SUDO_EXEC.search(msg)
        if m:
            category, eid = "privileged_action", 1101
            username = m["user"]
            detail["target_user"] = m["target"]
            detail["method"] = "sudo"
            # Command arguments intentionally omitted — may contain passwords/secrets.
    if not category and (identifier in ("login", "su") or "pam_unix(" in msg):
        m = PAM_OPEN.search(msg)
        if m and m["via"] in ("login", "su"):
            category, eid = "login_success", 1010
            username = m["user"]
            detail["method"] = m["via"]
    if not category and identifier in ACCOUNT_TOOLS:
        category, eid = "account_changed", 1201
        detail["tool"] = identifier
    if not category and identifier in GROUP_TOOLS:
        category, eid = "group_changed", 1202
        detail["tool"] = identifier
    if not category:
        return None
    cursor = str(entry.get("__CURSOR", ""))
    if not cursor:
        return None
    micros = entry.get("__REALTIME_TIMESTAMP") or entry.get("_SOURCE_REALTIME_TIMESTAMP")
    try:
        occurred = datetime.fromtimestamp(int(micros) / 1_000_000, tz=timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError, OSError):
        occurred = utc_now()
    uid = hashlib.sha256((device_id + "|" + cursor).encode()).hexdigest()
    return {
        "event_uid": uid,
        "record_id": int(uid[:15], 16),  # Positive, stable 60-bit number for existing backend.
        "event_id": eid,
        "occurred_at_utc": occurred,
        "computer": socket.gethostname(),
        "username": username,
        "domain": None,
        "source_ip": source_ip,
        "logon_type": detail.get("method"),
        "event_category": category,
        "details": detail,
    }


def journal_latest_cursor() -> str | None:
    result = subprocess.run(["journalctl", "--no-pager", "-o", "json", "-n", "1"],
                            text=True, capture_output=True, timeout=25, check=False)
    if result.returncode:
        raise RuntimeError("journalctl failed to read the journal; check service permissions")
    for line in result.stdout.splitlines():
        try:
            cursor = json.loads(line).get("__CURSOR")
        except ValueError:
            continue
        if cursor:
            return str(cursor)
    return None


def poll_journal(cfg: dict, store: QueueStore):
    cursor = store.get_meta("journal_cursor")
    start_since = store.get_meta("started_since")
    if cursor is None and not start_since:
        # First run begins at the latest journal record, avoiding old history.
        cursor = journal_latest_cursor()
        if cursor:
            store.set_meta("journal_cursor", cursor)
            return 0
        # Empty journal: remember the wall-clock starting point and read any
        # subsequent records on the next cycle (don't skip the first new one).
        start_since = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        store.set_meta("started_since", start_since)
        return 0
    cmd = ["journalctl", "--no-pager", "-o", "json"]
    if cursor:
        cmd.append("--after-cursor=" + cursor)
    else:
        cmd.append("--since=" + start_since)
    count = 0
    processed = 0
    # Stream JSON rather than buffering the entire journal in RAM.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, errors="replace")
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            new_cursor = entry.get("__CURSOR")
            if not new_cursor:
                continue
            payload = classify_journal(entry, cfg["device_id"])
            store.save_entry(str(new_cursor), payload)
            processed += 1
            if payload:
                count += 1
        stderr = proc.stderr.read(1024) if proc.stderr is not None else ""
        rc = proc.wait(timeout=30)
        if rc:
            raise RuntimeError("journalctl returned an error: " + stderr[:200])
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
    return count


def collect_accounts() -> tuple[list[dict], list[dict]]:
    """Read local /etc/passwd and /etc/group only; no shadow/password hashes."""
    groups = []
    members = {}
    for line in Path("/etc/group").read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split(":")
        if len(parts) != 4:
            continue
        name, _unused, gid, raw_members = parts
        if not gid.isdigit():
            continue
        group_members = [x for x in raw_members.split(",") if x]
        groups.append({"name": name, "gid": int(gid), "members": group_members,
                       "privileged_group": name in SUDO_GROUPS})
        for member in group_members:
            members.setdefault(member, []).append(name)
    accounts = []
    for line in Path("/etc/passwd").read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split(":")
        if len(parts) != 7:
            continue
        name, _unused, uid, gid, _gecos, _home, shell = parts
        if not uid.isdigit() or not gid.isdigit():
            continue
        accounts.append({"username": name, "uid": int(uid), "gid": int(gid),
                         "shell": shell, "is_system_account": int(uid) < 1000 and int(uid) != 0,
                         "supplementary_groups": members.get(name, []),
                         "is_sudo_group_member": any(g in SUDO_GROUPS for g in members.get(name, []))})
    return accounts, groups


def snapshot_now(cfg: dict, store: QueueStore):
    accounts, groups = collect_accounts()
    at = utc_now()
    store.save_snapshot({"device_id": cfg["device_id"], "collected_at_utc": at,
                         "accounts": accounts, "groups": groups, "error": None})
    store.set_meta("last_snapshot_utc", at)
    return len(accounts), len(groups)


def send_pending(cfg: dict, store: QueueStore):
    sent = 0
    reached_server = False
    for _ in range(20):  # At most 2,000 events per sync pass.
        events = store.batch_events()
        if not events:
            break
        api_post(cfg, "/api/agents/events", {"device_id": cfg["device_id"],
                                               "events": [x[1] for x in events]})
        reached_server = True
        store.ack_events([x[0] for x in events])
        sent += len(events)
    for collected_at, data in store.pending_snapshots():
        api_post(cfg, "/api/agents/snapshot", data)
        reached_server = True
        store.ack_snapshot(collected_at)
    # An idle system should still test its API connection every 60 seconds.
    last_ping = store.get_meta("last_ping_utc")
    is_due = (not last_ping or (datetime.now(timezone.utc) -
               datetime.fromisoformat(last_ping)).total_seconds() >= 60)
    if not reached_server and is_due:
        api_post(cfg, "/api/agents/ping", {"device_id": cfg["device_id"]})
        reached_server = True
    if reached_server:
        store.set_meta("last_ping_utc", utc_now())
    return sent, reached_server


def status_write(cfg: dict, store: QueueStore, error: str | None = None,
                 sent: int = 0, captured: int = 0):
    pending, snapshots = store.pending_counts()
    dest = store.state / "status.json"
    data = {"device_id": cfg["device_id"], "hostname": socket.gethostname(),
            "checked_at_utc": utc_now(), "pending_events": pending,
            "pending_snapshots": snapshots, "last_snapshot_utc": store.get_meta("last_snapshot_utc"),
            "last_successful_sync_utc": store.get_meta("last_successful_sync_utc"),
            "events_captured_this_cycle": captured, "events_sent_this_cycle": sent,
            "error": error}
    tmp = store.state / "status.json.tmp"
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o644)
    tmp.replace(dest)
    # The root-owned SQLite store stays private; status-only data is made
    # readable by the optional desktop UI through systemd's RuntimeDirectory.
    runtime = Path("/run/accessreview-agent")
    if runtime.is_dir():
        public_tmp = runtime / "status.json.tmp"
        public_tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.chmod(public_tmp, 0o644)
        public_tmp.replace(runtime / "status.json")


def run_cycle(cfg: dict, store: QueueStore):
    captured = 0
    sent = 0
    errors = []
    try:
        captured = poll_journal(cfg, store)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        errors.append(f"journal read: {exc}")
    try:
        last = store.get_meta("last_snapshot_utc")
        if not last or (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() >= 3600:
            snapshot_now(cfg, store)
    except (OSError, ValueError) as exc:
        errors.append(f"account snapshot: {exc}")
    try:
        sent, reached_server = send_pending(cfg, store)
        if reached_server:
            store.set_meta("last_successful_sync_utc", utc_now())
    except (HTTPError, URLError, OSError, RuntimeError, ValueError) as exc:
        if isinstance(exc, HTTPError):
            desc = f"HTTP {exc.code}"
        else:
            desc = str(exc)
        errors.append("upload: " + desc[:180])
    error = "; ".join(errors) if errors else None
    status_write(cfg, store, error, sent, captured)
    if error:
        LOG.warning("%s", error)
    elif captured or sent:
        LOG.info("Captured=%d sent=%d", captured, sent)


def main(argv=None):
    parser = argparse.ArgumentParser(description="AccessReviewAgent Linux journald collector")
    parser.add_argument("action", choices=["run", "once", "test-api", "status", "snapshot"])
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--state-dir", default=DEFAULT_STATE)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.action == "status":
        path = Path(args.state_dir) / "status.json"
        print(path.read_text(encoding="utf-8") if path.exists() else "No status yet — start the service.")
        return 0
    cfg = load_config(args.config)
    if args.action == "test-api":
        result = api_post(cfg, "/api/agents/ping", {"device_id": cfg["device_id"]})
        print(json.dumps(result, indent=2))
        return 0
    store = QueueStore(args.state_dir)
    try:
        if args.action == "snapshot":
            ac, gr = snapshot_now(cfg, store)
            print(f"Queued local snapshot: {ac} accounts, {gr} groups")
        elif args.action == "once":
            run_cycle(cfg, store)
            print((Path(args.state_dir) / "status.json").read_text(encoding="utf-8"))
        else:
            LOG.info("Linux agent started: %s", cfg["device_id"])
            while True:
                run_cycle(cfg, store)
                time.sleep(5)
    except KeyboardInterrupt:
        LOG.info("Agent stopped")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, HTTPError, URLError, RuntimeError) as exc:
        LOG.error("Agent error: %s", exc)
        sys.exit(1)
