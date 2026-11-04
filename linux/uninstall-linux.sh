#!/usr/bin/env bash
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
    echo "Run: sudo ./uninstall-linux.sh" >&2
    exit 1
fi
systemctl disable --now accessreview-agent.service 2>/dev/null || true
rm -f /etc/systemd/system/accessreview-agent.service
rm -f /usr/share/applications/accessreview-agent.desktop
systemctl daemon-reload
rm -rf /opt/accessreview-agent
printf 'Removed service and code. Configuration and queue retained at:\n'
printf '  /etc/accessreview-agent/\n  /var/lib/accessreview-agent/\n'
printf 'To permanently delete these too, review and remove them manually.\n'
