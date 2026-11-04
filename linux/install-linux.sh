#!/usr/bin/env bash
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
    echo "Please run: sudo ./install-linux.sh" >&2
    exit 1
fi
if ! command -v journalctl >/dev/null || ! command -v systemctl >/dev/null; then
    echo "This installer requires Ubuntu/Debian with systemd-journald." >&2
    exit 1
fi
if ! command -v python3 >/dev/null; then
    echo "Install Python 3 first: sudo apt update && sudo apt install python3" >&2
    exit 1
fi
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install -d -m 0755 /opt/accessreview-agent
install -m 0755 "$HERE/agent.py" /opt/accessreview-agent/agent.py
install -m 0755 "$HERE/configure.py" /opt/accessreview-agent/configure.py
install -m 0755 "$HERE/desktop.py" /opt/accessreview-agent/desktop.py
install -m 0644 "$HERE/README.md" /opt/accessreview-agent/README.md
install -d -m 0700 /etc/accessreview-agent
install -d -m 0700 /var/lib/accessreview-agent
install -m 0644 "$HERE/accessreview-agent.service" /etc/systemd/system/accessreview-agent.service
install -m 0644 "$HERE/accessreview-agent.desktop" /usr/share/applications/accessreview-agent.desktop
systemctl daemon-reload
# Existing config is retained on reinstall; only prompt for initial setup.
if [[ ! -s /etc/accessreview-agent/config.json ]]; then
    echo "\nFirst-time setup. Use a unique token for this Linux device from Coolify."
    python3 /opt/accessreview-agent/configure.py
fi
systemctl enable --now accessreview-agent.service
systemctl restart accessreview-agent.service
printf '\nInstalled. Device status:\n'
systemctl --no-pager --full status accessreview-agent.service | head -n 14 || true
printf '\nFollow live agent output: sudo journalctl -u accessreview-agent -f\n'
printf 'View local agent status: sudo python3 /opt/accessreview-agent/agent.py status\n'
printf 'To change settings: sudo python3 /opt/accessreview-agent/configure.py\n'
