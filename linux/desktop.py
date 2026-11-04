#!/usr/bin/env python3
"""Optional read-only Ubuntu desktop status window (requires python3-tk)."""
import json
from pathlib import Path
import subprocess
try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    raise SystemExit("Optional GUI needs tkinter: sudo apt install python3-tk")

STATE = Path("/run/accessreview-agent/status.json")
root = tk.Tk()
root.title("AccessReviewAgent | Linux")
root.geometry("510x420")
root.configure(bg="#121a28")
root.resizable(False, False)
font = ("DejaVu Sans", 11)
large = ("DejaVu Sans", 21, "bold")
label = tk.Label(root, text="🛡  AccessReviewAgent", fg="#f0f4fa", bg="#121a28", font=large)
label.pack(pady=(22, 8))
tk.Label(root, text="Linux Audit Collector • Read-only status", fg="#a7b5c8", bg="#121a28", font=font).pack()
status_var = tk.StringVar(value="Checking service...")
info_var = tk.StringVar(value="")
tk.Label(root, textvariable=status_var, fg="#75d9a4", bg="#121a28", font=("DejaVu Sans", 15, "bold")).pack(pady=(22, 14))
tk.Label(root, textvariable=info_var, fg="#d6e0ed", bg="#121a28", font=font,
         justify="left", wraplength=460).pack(padx=26, anchor="w")


def refresh():
    service = subprocess.run(["systemctl", "is-active", "accessreview-agent.service"],
                             capture_output=True, text=True, timeout=10)
    status_var.set("●  Running" if service.stdout.strip() == "active" else "●  Service stopped")
    if not STATE.exists():
        info_var.set("No status report yet. Start the agent service first.")
        return
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        info_var.set("Device: " + str(data.get("device_id", "-")) + "\n\n"
                     "Computer: " + str(data.get("hostname", "-")) + "\n\n"
                     "Pending events: " + str(data.get("pending_events", "-")) + "\n\n"
                     "Last successful API sync: " + str(data.get("last_successful_sync_utc", "-")) + "\n\n"
                     "Last account snapshot: " + str(data.get("last_snapshot_utc", "-")) + "\n\n"
                     "Error: " + str(data.get("error") or "None"))
    except (ValueError, OSError) as exc:
        info_var.set("Could not read status: " + str(exc))


tk.Button(root, text="Refresh", command=refresh, font=font, bg="#3177d3", fg="white",
          padx=24, pady=7).pack(pady=(20, 10))
tk.Label(root, text="Setup: sudo python3 /opt/accessreview-agent/configure.py",
         fg="#8da0ba", bg="#121a28", font=("DejaVu Sans", 9)).pack()
refresh()
root.mainloop()
