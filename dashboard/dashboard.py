#!/usr/bin/env python3
# dashboard.py
"""
Cloud Vitals Dashboard

This script runs on your local machine (or a separate VM).
Periodically checks the Cloud Vital Agents' endpoints using requests,
aggregates the returned data, and renders the resulting data visually.
"""

import os
import sys
import requests
import threading
import subprocess
import tkinter as tk
import tkinter.ttk as ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

## -- Configuration ------------------------------------------
POLL_INTERVAL = 1000  # ms between polls
HISTORY_LENGTH = 60  # points to keep in each chart
CON_TIMEOUT = 5  # seconds until connection timeout
STRESS_DURATION = 20  # seconds per test
STRESS_CLASSES = ["cpu", "swap", "filesystem", "io", "net"]

# Warning Alerts
THRESHOLD_WINDOW = 10  # seconds back to look when checking thresholds
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALERT_SOUND = os.path.join(SCRIPT_DIR, "WarningAlert.wav")

# These will be set when the user click "Connect" to the agent
AGENT_URL = ""
STRESS_URL = ""
connected = False
polling_job = None

## -- Buffers for historical data ----------------------------
cpu_data = [0] * HISTORY_LENGTH
mem_data = [0] * HISTORY_LENGTH
swap_data = [0] * HISTORY_LENGTH
disk_data = [0] * HISTORY_LENGTH
net_data = [0] * HISTORY_LENGTH
diskR_data = [0] * HISTORY_LENGTH
diskW_data = [0] * HISTORY_LENGTH


## -- Helpers ------------------------------------------------
def format_bytes(num_bytes: float) -> str:
    """Turn a raw byte count into MB, GB, or TB with two decimal places."""
    units = [(1 << 40, "TB"), (1 << 30, "GB"), (1 << 20, "MB")]
    for factor, suffix in units:
        if num_bytes >= factor:
            return f"{num_bytes / factor:.2f} {suffix}"
    return f"{num_bytes / (1 << 20):.2f} MB"

def add_placeholder(entry, placeholder):
    entry.insert(0, placeholder)
    entry.config(fg="grey")

    def on_focus_in(event):
        if entry.get() == placeholder:
            entry.delete(0, "end")
            entry.config(fg="black")

    def on_focus_out(event):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg="grey")

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)


def make_button_row(parent, classes):
    row = tk.Frame(parent)
    row.pack(fill="x", pady=2)
    for cls in classes:
        btn = tk.Button(row, text=f"Start {cls.upper()}", command=make_toggle(cls), font=("Arial", 10, "bold"), width=max_text_len)
        default_bg[cls] = btn.cget("background")
        btn.pack(side="left", expand=True, fill="x", padx=5)
        buttons[cls] = btn


def play_alert():
    """Cross-platform WAV playback."""
    try:
        if sys.platform == "win32":  # Windows
            import winsound

            winsound.PlaySound(ALERT_SOUND, winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sys.platform == "darwin":  # macOS
            subprocess.Popen(["afplay", ALERT_SOUND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform.startswith("linux"):  # Linux
            subprocess.Popen(["aplay", ALERT_SOUND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            print(f"Cannot play sound on platform {sys.platform}")
    except Exception as e:
        print("Failed to play alert:", e)


def make_graph(frame, title):
    # Create figure, axes, and empty line
    fig, ax = plt.subplots(figsize=(5, 3), constrained_layout=True)
    (line,) = ax.plot(range(HISTORY_LENGTH), [0] * HISTORY_LENGTH)

    # Titles and Labels
    ax.set_xlabel("Seconds ago")
    ax.set_ylabel(title)

    # Major x-axis ticks
    ticks = list(range(0, HISTORY_LENGTH, 10)) + [HISTORY_LENGTH - 1]
    labels = [f"{HISTORY_LENGTH - t}s" for t in ticks[:-1]] + ["0s"]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)

    # Grids
    ax.grid(which="major", linestyle="--", linewidth=0.5)
    ax.grid(which="minor", linestyle=":", linewidth=0.3)

    # If it is a percent chart, clamp and format ticks
    if title.endswith("%"):
        ax.set_ylim(0, 100)
        yticks = [0, 20, 40, 60, 80, 100]
        ax.set_yticks(yticks)
        ax.set_yticklabels([f"{y}%" for y in yticks])

    # Embed in Tk
    canvas = FigureCanvasTkAgg(fig, master=frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side="left", anchor="w")

    return line, fig


## -- Networking / Polling -----------------------------------
def fetch_and_update():
    global polling_job
    if not connected:
        return

    def worker():
        try:
            resp = requests.get(AGENT_URL, timeout=CON_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print("Fetch error:", e)
            data = None

        # Schedule update_ui(data) on main thread
        window.after(0, update_ui, data)

    # Start the background fetch
    threading.Thread(target=worker, daemon=True).start()


def update_ui(data):
    global polling_job
    if data:
        # Shift in new samples, drop oldest
        cpu_data.append(data.get("cpu_percent", 0))
        cpu_data.pop(0)
        mem_data.append(data.get("memory_percent", 0))
        mem_data.pop(0)
        swap_data.append(data.get("swap_percent", 0))
        swap_data.pop(0)
        disk_data.append(data.get("disk_percent", 0))
        disk_data.pop(0)

        # Convert from bytes/sec to MB/sec:
        net_data.append(data.get("network_bytes_per_sec", 0) / (1024**2))
        net_data.pop(0)
        diskW_data.append(data.get("disk_write_bytes_per_sec", 0) / (1024**2))
        diskW_data.pop(0)
        diskR_data.append(data.get("disk_read_bytes_per_sec", 0) / (1024**2))
        diskR_data.pop(0)

        # Update lines
        cpu_line.set_ydata(cpu_data)
        mem_line.set_ydata(mem_data)
        swap_line.set_ydata(swap_data)
        disk_line.set_ydata(disk_data)
        net_line.set_ydata(net_data)
        diskW_line.set_ydata(diskW_data)
        diskR_line.set_ydata(diskR_data)

        # Autoscale the MB/s charts
        for fig in (net_fig, diskW_fig, diskR_fig):
            ax = fig.axes[0]
            ax.relim()
            ax.autoscale_view()

        # Redraw each figure
        for fig in (cpu_fig, mem_fig, swap_fig, disk_fig, net_fig, diskW_fig, diskR_fig):
            fig.canvas.draw()

        # Update detail_vars and table rows
        for label, total_key, used_key, free_key in detail_specs:
            detail_vars[total_key].set(format_bytes(data.get(total_key, 0)))
            detail_vars[used_key].set(format_bytes(data.get(used_key, 0)))
            detail_vars[free_key].set(format_bytes(data.get(free_key, 0)))
            table.item(label, values=(label, detail_vars[total_key].get(), detail_vars[used_key].get(), detail_vars[free_key].get()))
        for idx, item in enumerate(table.get_children()):
            label, total_key, used_key, free_key = detail_specs[idx]
            table.item(item, values=(label, detail_vars[total_key].get(), detail_vars[used_key].get(), detail_vars[free_key].get()))

        # Threshold Checks (CPU, Memory, Swap)
        if len(cpu_data) >= THRESHOLD_WINDOW:
            recent_cpu = max(cpu_data[-THRESHOLD_WINDOW:])
            recent_mem = max(mem_data[-THRESHOLD_WINDOW:])
            recent_swap = max(swap_data[-THRESHOLD_WINDOW:])

            # CPU Warning
            if cpu_thresh_var.get() and recent_cpu > cpu_thresh_var.get():
                frames["cpu"].config(fg="red", text="CPU Usage % (WARNING)")
            else:
                frames["cpu"].config(fg="black", text="CPU Usage %")

            # Memory Warning
            if mem_thresh_var.get() and recent_mem > mem_thresh_var.get():
                frames["mem"].config(fg="red", text="Memory Usage % (WARNING)")
            else:
                frames["mem"].config(fg="black", text="Memory Usage %")

            # Swap Warning
            if swap_thresh_var.get() and recent_swap > swap_thresh_var.get():
                frames["swap"].config(fg="red", text="Swap Usage % (WARNING)")
            else:
                frames["swap"].config(fg="black", text="Swap Usage %")

            # Play sound if any threshold is exceeded
            if (
                (cpu_thresh_var.get() and recent_cpu > cpu_thresh_var.get())
                or (mem_thresh_var.get() and recent_mem > mem_thresh_var.get())
                or (swap_thresh_var.get() and recent_swap > swap_thresh_var.get())
            ):
                play_alert()

        # Update status
        status_label.config(text="Connected!", fg="green")
    else:
        status_label.config(text="Error: could not fetch data", fg="orange")

    # Schedule next fetch
    if connected:
        polling_job = window.after(POLL_INTERVAL, fetch_and_update)


## -- Connect / Disconnect -----------------------------------
def toggle_connection():
    global connected, AGENT_URL, STRESS_URL
    if not connected:
        ip = ip_entry.get().strip()
        port = port_entry.get().strip()
        AGENT_URL = f"http://{ip}:{port}/metrics"
        STRESS_URL = AGENT_URL.replace("/metrics", "/stress")

        connect_btn.config(text="Disconnect")
        status_label.config(text="Connecting...", fg="orange")

        connected = True
        fetch_and_update()
    else:
        connect_btn.config(text="Connect")
        connected = False
        if polling_job:
            window.after_cancel(polling_job)
        status_label.config(text="Disconnected!", fg="red")


## -- Build UI -----------------------------------------------
window = tk.Tk()
window.protocol("WM_DELETE_WINDOW", lambda: (window.quit(), sys.exit(0)))
window.title("Cloud Vitals Dashboard")
window.geometry("1800x800")
window.resizable(False, False)

# Container for all 3 rows by 4 columns
container = tk.Frame(window, padx=10, pady=10)
container.pack(fill="both", expand=True)

# Equal weight columns and rows
for col in range(4):
    container.grid_columnconfigure(col, weight=1, uniform="col")
container.grid_rowconfigure(0, weight=0, minsize=80)
container.grid_rowconfigure(1, weight=1, uniform="row")
container.grid_rowconfigure(2, weight=1, uniform="row")

# Definitions for each cell: (row, col, key, text, width, height)
cells = [
    # Row 0
    (0, 0, "title", None, 350, 80),
    (0, 1, "stress", "Stress Tests", 350, 80),
    (0, 2, "warning", "Warning Alerts", 350, 80),
    (0, 3, "details", "Details", 350, 80),
    # Row 1
    (1, 0, "conn", "Agent Connection", 350, 250),
    (1, 1, "cpu", "CPU Usage %", 350, 250),
    (1, 2, "mem", "Memory Usage %", 350, 250),
    (1, 3, "swap", "Swap Usage %", 350, 250),
    # Row 2
    (2, 0, "net", "Networking MB/s", 350, 250),
    (2, 1, "disk", "Disk Usage %", 350, 250),
    (2, 2, "diskR", "Disk Reads MB/s", 350, 250),
    (2, 3, "diskW", "Disk Writes MB/s", 350, 250),
]

frames = {}
for row, col, key, text, w, h in cells:
    if key == "title":
        # plain Frame for the title block
        frm = tk.Frame(container, width=w, height=h)
    else:
        frm = tk.LabelFrame(container, text=text, font=("Arial", 12, "bold"), padx=10, pady=10, width=w, height=h)
    frm.grid(row=row, column=col, padx=10, pady=5, sticky="nsew")
    frm.grid_propagate(True)
    frames[key] = frm

# --- Row 0: Title | Stress Tests | Warning | Details --------

# Title block
tk.Label(frames["title"], text="", height=4).pack()
tk.Label(frames["title"], text="Cloud Vitals Dashboard", font=("Arial", 16, "bold")).pack()

tk.Label(frames["title"], text="Dashboard GUI for Cloud Vital Agents", font=("Arial", 12, "italic")).pack()

# Stress test description & buttons
tk.Label(frames["stress"], text=f"Run stress tests against the agent for {STRESS_DURATION} seconds each.",
         font=("Arial", 10, "italic")).pack(anchor="w", pady=(0, 20))

# Compute max width in characters so buttons don't resize
max_text_len = max(len(f"Start {cls.upper()}") for cls in STRESS_CLASSES)

# State holders for button toggles
stress_running = {cls: False for cls in STRESS_CLASSES}
stop_job, buttons, default_bg = {}, {}, {}


def make_toggle(cls):

    def auto_stop():
        # Only run if still marked as running
        if stress_running[cls]:
            stress_running[cls] = False
            buttons[cls].config(text=f"Start {cls.upper()}", bg=default_bg[cls])
        stop_job.pop(cls, None)

    def toggle():
        if not stress_running[cls]:
            #Start the stress test
            try:
                requests.post(f"{STRESS_URL}", json={"class": cls, "duration": STRESS_DURATION}, timeout=CON_TIMEOUT).raise_for_status()
            except Exception as e:
                print(f"Stress {cls} error:", e)
                return
            stress_running[cls] = True
            buttons[cls].config(text=f"Stop {cls.upper()}", bg="red")

            # Schedule auto-stop after STRESS_DURATION
            stop_job[cls] = window.after(STRESS_DURATION * 1000, auto_stop)

        else:
            # Manual stop: cancel backend and UI
            try:
                requests.delete(f"{STRESS_URL}/{cls}", timeout=CON_TIMEOUT).raise_for_status()
            except Exception as e:
                print(f"Stress {cls} stop error:", e)
            stress_running[cls] = False
            buttons[cls].config(text=f"Start {cls.upper()}", bg=default_bg[cls])

            # Cancel the pending auto-stop callback
            if cls in stop_job:
                window.after_cancel(stop_job[cls])
                stop_job.pop(cls, None)

    return toggle


# Row 1: CPU & Swap
make_button_row(frames["stress"], ["cpu", "swap"])

# Row 2: FILESYSTEM (centered)
btn_fs = tk.Button(frames["stress"], text="Start FILESYSTEM", command=make_toggle("filesystem"),
                   font=("Arial", 10, "bold"), width=max_text_len)
default_bg["filesystem"] = btn_fs.cget("background")
btn_fs.pack(pady=5)
buttons["filesystem"] = btn_fs

# Row 3: IO & NET
make_button_row(frames["stress"], ["io", "net"])

# Warning Alerts
frames["warning"].grid_columnconfigure(0, weight=0)
frames["warning"].grid_columnconfigure(1, weight=1)

# Threshold variables
cpu_thresh_var = tk.IntVar(value=85)
mem_thresh_var = tk.IntVar(value=90)
swap_thresh_var = tk.IntVar(value=40)

# Description & threshold config
tk.Label(frames["warning"], text=f"Alerts threshold exceeds threshold in past {THRESHOLD_WINDOW} seconds.",
         font=("Arial", 10, "italic")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

thresholds = [("CPU Threshold (%)", cpu_thresh_var), ("Memory Threshold (%)", mem_thresh_var), ("Swap Threshold (%)", swap_thresh_var)]

# Create labeled horizontal sliders for each threshold
for i, (label, var) in enumerate(thresholds, start=1):
    tk.Label(frames["warning"], text=label, font=("Arial", 10, "bold")).grid(row=i, column=0, sticky="w", padx=(0, 5), pady=(5 if i > 1 else 0, 0))
    tk.Scale(frames["warning"], from_=0, to=100, orient="horizontal", variable=var).grid(row=i, column=1, sticky="ew", pady=(5 if i > 1 else 0, 0))

# Details grid
detail_specs = [("Memory", "memory_total", "memory_used", "memory_free"),
                ("Swap", "swap_total", "swap_used", "swap_free"),
                ("Disk", "disk_total", "disk_used", "disk_free")]
detail_vars = {key: tk.StringVar(value="0") for _, *keys in detail_specs for key in keys}

cols = ("Type", "Total", "Used", "Free")
table = ttk.Treeview(frames["details"], columns=cols, show="headings", height=len(detail_specs))
for col in cols:
    table.heading(col, text=col)
    table.column(col, anchor="e" if col != "Type" else "w", width=100, stretch=True)
table.pack(fill="both", expand=True)

for spec in detail_specs:
    label, *keys = spec
    table.insert("", "end", iid=label, values=(label, *(detail_vars[k].get() for k in keys)))

# --- Row 1: Connection | CPU % | Mem % | Swap % -------------
cpu_line, cpu_fig = make_graph(frames["cpu"], "CPU Usage %")
mem_line, mem_fig = make_graph(frames["mem"], "Memory Usage %")
swap_line, swap_fig = make_graph(frames["swap"], "Swap Usage %")

# Connection controls
conn = frames["conn"]
conn.grid_columnconfigure(0, weight=1)
conn.grid_columnconfigure(1, weight=0)
conn.grid_rowconfigure(0, minsize=40)

# Agent Status Row
tk.Label(conn, text="Agent Status:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 2))
connect_btn = tk.Button(conn, text="Connect", command=toggle_connection, width=12, font=("Arial", 10, "bold"))
connect_btn.grid(row=0, column=1, sticky="e", padx=(5, 0), pady=(0, 2))

# Connection Status Display
status_label = tk.Label(conn, text="Disconnected!", bg="black", fg="red", font=("Arial", 10, "bold"), anchor="w", justify="left", height=1)
status_label.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 5), ipady=5)

# IP Input
tk.Label(conn, text="Agent IP Address:", font=("Arial", 10, "bold")).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 10))
ip_entry = tk.Entry(conn)
ip_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 5), ipady=5)
add_placeholder(ip_entry, "Put the IP of your Agent here (e.g. 127.0.0.1)")

# Port Input
tk.Label(conn, text="Agent Port:", font=("Arial", 10, "bold")).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 2))
port_entry = tk.Entry(conn)
port_entry.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 5), ipady=5)
add_placeholder(port_entry, "Put the Port of your Agent here (e.g. 5000)")

# --- Row 3: Networking | Disk % | Disk R | Disk W -----------
net_line, net_fig = make_graph(frames["net"], "Networking MB/s")
disk_line, disk_fig = make_graph(frames["disk"], "Disk Usage %")
diskR_line, diskR_fig = make_graph(frames["diskR"], "Disk Reads MB/s")
diskW_line, diskW_fig = make_graph(frames["diskW"], "Disk Writes MB/s")

# Run the Dashboard
window.mainloop()
