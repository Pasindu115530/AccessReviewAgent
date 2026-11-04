#!/usr/bin/env python3
"""Interactive root-only configuration helper. Does not print the token."""
import getpass
import json
import os
from pathlib import Path
import sys
from agent import DEFAULT_CONFIG, validate_config


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run as root: sudo python3 /opt/accessreview-agent/configure.py")
    path = Path(DEFAULT_CONFIG)
    old = {}
    if path.exists():
        try:
            old = json.loads(path.read_text())
        except ValueError:
            pass
    print("AccessReviewAgent Linux setup — per-device credentials")
    print("Provide the same HTTPS API origin used by your Windows agents.")
    server = input(f"Server URL [{old.get('server_url', 'https://logs.example.com')}]: ").strip()
    server = server or old.get("server_url", "https://logs.example.com")
    device = input(f"Device ID [{old.get('device_id', 'LINUX-01')}]: ").strip()
    device = device or old.get("device_id", "LINUX-01")
    token = getpass.getpass("Agent token [Enter to keep existing]: ").strip()
    if not token:
        token = old.get("agent_token", "")
    cfg = validate_config({"server_url": server, "device_id": device, "agent_token": token})
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    old_umask = os.umask(0o077)
    try:
        with tmp.open("w", encoding="utf-8") as out:
            json.dump(cfg, out, indent=2)
            out.write("\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        os.umask(old_umask)
    print(f"Saved {path} (root only). Device: {device}")
    print("To apply changes: sudo systemctl restart accessreview-agent")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as err:
        print("Configuration error:", err, file=sys.stderr)
        sys.exit(1)
