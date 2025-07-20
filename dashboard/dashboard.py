# dashboard.py

"""
Cloud Vitals Dashboard

This script runs on your local machine (or a separate VM).
Periodically checks the Cloud Vital Agents' endpoints using requests,
aggregates the returned data, and renders the resulting data visually.
"""

import sys
import requests
import tkinter as tk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Agent endpoint and polling settings
AGENT_URL       = "http://addr:5000/metrics"
POLL_INTERVAL   = 1000   # ms between polls
HISTORY_LENGTH  = 60     # points to keep in each chart

# Stress control settings
STRESS_URL      = AGENT_URL.replace('/metrics', '/stress')
STRESS_DURATION = 20    # per test
STRESS_CLASSES  = ["cpu","filesystem", "swap", "net", "io"]
#STRESS_CLASSES  = ["cpu", "io", "filesystem"]

# Buffers for historical data
cpu_data    = [0] * HISTORY_LENGTH
mem_data    = [0] * HISTORY_LENGTH
swap_data   = [0] * HISTORY_LENGTH
disk_data   = [0] * HISTORY_LENGTH
net_data    = [0] * HISTORY_LENGTH
diskR_data  = [0] * HISTORY_LENGTH
diskW_data  = [0] * HISTORY_LENGTH

def make_graph(frame, title):
    fig     = plt.figure(figsize=(3,2))
    ax      = fig.add_subplot(1,1,1)
    line,   = ax.plot(range(HISTORY_LENGTH), [0] * HISTORY_LENGTH)
    ax.set_title(title)
    fig.tight_layout()

    # If this is a percent chart, fix y-axis to 0-100
    if title.endswith("%"):
        ax.set_ylim(0, 100)

    canvas = FigureCanvasTkAgg(fig, master=frame)
    canvas.draw()
    canvas.get_tk_widget().pack()
    return line, fig

def fetch_and_update():
    try:
        data = requests.get(AGENT_URL, timeout=2).json()
    except Exception:
        # Skip this cycle on error
        window.after(POLL_INTERVAL, fetch_and_update)
        return

    # Shift in new samples, drop oldest
    cpu_data.append(data.get("cpu_percent", 0));    cpu_data.pop(0)
    mem_data.append(data.get("memory_percent", 0)); mem_data.pop(0)
    swap_data.append(data.get("swap_percent", 0));  swap_data.pop(0)
    disk_data.append(data.get("disk_percent", 0));  disk_data.pop(0)
    net_data.append(data.get("network_average_bytes_per_sec", 0));  net_data.pop(0)
    diskR_data.append(data.get("disk_read", 0));    diskR_data.pop(0)
    diskW_data.append(data.get("disk_write", 0));   diskW_data.pop(0)

    # Update lines
    cpu_line.set_ydata(cpu_data)
    mem_line.set_ydata(mem_data)
    swap_line.set_ydata(swap_data)
    disk_line.set_ydata(disk_data)
    net_line.set_ydata(net_data)
    diskR_line.set_ydata(diskR_data)
    diskW_line.set_ydata(diskW_data)

    # Autoscale the network axis to fit the newest data
    net_ax = net_fig.axes[0]
    net_ax.relim()
    net_ax.autoscale_view()

    diskR_ax = diskR_fig.axes[0]
    diskR_ax.relim()
    diskR_ax.autoscale_view()

    diskW_ax = diskW_fig.axes[0]
    diskW_ax.relim()
    diskW_ax.autoscale_view()

    # Redraw each figure
    cpu_fig.canvas.draw()
    mem_fig.canvas.draw()
    swap_fig.canvas.draw()
    disk_fig.canvas.draw()
    net_fig.canvas.draw()
    diskR_fig.canvas.draw()
    diskW_fig.canvas.draw()

    # Update detail labels
    for key, title in detail_specs:
        detail_vars[key].set(f"{title}: {data.get(key, 0)}")

    window.after(POLL_INTERVAL, fetch_and_update)

# Build UI
window = tk.Tk()
def on_closing():
    # Stop the mainloop and exit the script
    window.quit()   # Breaks out of the main loop
    sys.exit(0)     # Terminates the process
window.protocol("WM_DELETE_WINDOW", on_closing)
window.title("Cloud Vitals Dashboard")
window.geometry("2000x400")

tk.Label(window, text="Cloud Vitals Dashboard", font=("Arial",16)).pack(pady=10)

# Map of metric key -> (label text, StringVar)
detail_vars = {}
detail_specs = [
    ("memory_total", "Mem Total"),
    ("memory_used",  "Mem Used"),
    ("memory_free",  "Mem Free"),
    ("swap_total",   "Swap Total"),
    ("swap_used",    "Swap Used"),
    ("swap_free",    "Swap Free"),
    ("disk_total",   "Disk Total"),
    ("disk_used",    "Disk Used"),
    ("disk_free",    "Disk Free"),
]

detail_vars = {}

# Build the label row
details_frame = tk.LabelFrame(window, text="Details", padx=5, pady=5)
details_frame.pack(side="top", fill="x", padx=10, pady=5)

for idx, (key, title) in enumerate(detail_specs):
    var = tk.StringVar(value=f"{title}: 0")
    detail_vars[key] = var
    lbl = tk.Label(details_frame, textvariable=var, width=15, anchor="w")
    lbl.grid(row=0, column=idx, padx=2)

# Stress Toggle Buttons
stress_running  = {cls: False for cls in STRESS_CLASSES}
default_bg      = {}
buttons         = {}
def make_toggle(cls):
    def toggle():
        if not stress_running[cls]:
            # Start Stress
            try:
                r = requests.post(STRESS_URL, json={ "class": cls, "duration": STRESS_DURATION }, timeout=2)
                r.raise_for_status()
            except Exception as e:
                print(f"Failed to start {cls} stress: ", e)
            stress_running[cls] = True
            buttons[cls].config(text=f"Stop {cls.upper()}", bg="red")
        else:
            # Stop Stress
            try:
                r = requests.delete(f"{STRESS_URL}/{cls}", timeout=2)
                r.raise_for_status()
            except Exception as e:
                print(f"Failed to stop {cls} stress: ", e)
            stress_running[cls] = False
            buttons[cls].config(text=f"Start {cls.upper()}", bg=default_bg[cls])
    return toggle

ctrl_frame = tk.Frame(window, pady=10)
ctrl_frame.pack()

for cls in STRESS_CLASSES:
    btn = tk.Button(ctrl_frame, text=f"Start {cls.upper()}", command=make_toggle(cls))
    default_bg[cls] = btn.cget("background")
    btn.pack(side="left", padx=5)
    buttons[cls] = btn

# Create frames and graphs
frames = {}
for key, title in [
    ("cpu",  "CPU %"),
    ("mem",  "Mem %"),
    ("swap", "Swap %"),
    ("disk", "Disk %"),
    ("net",  "Net B/s"),
    ("diskW", "Disk W/s"),
    ("diskR", "Disk R/s"),
]:
    f = tk.LabelFrame(window, text=title, padx=5, pady=5)
    f.pack(side="left", padx=10, pady=10)
    frames[key] = f

# Initialize each graph and keep references
cpu_line, cpu_fig   = make_graph(frames["cpu"],  "CPU %")
mem_line, mem_fig   = make_graph(frames["mem"],  "Mem %")
swap_line, swap_fig = make_graph(frames["swap"], "Swap %")
disk_line, disk_fig = make_graph(frames["disk"], "Disk %")
net_line, net_fig   = make_graph(frames["net"],  "Net B/s")
diskR_line, diskR_fig = make_graph(frames["diskR"], "Disk R/s")
diskW_line, diskW_fig = make_graph(frames["diskW"], "Disk W/s")

# Add detail labels to respective frames
for key, title in [("memory_total", "Mem Total"), ("memory_used", "Mem Used"), ("memory_free", "Mem Free")]:
    var = tk.StringVar(value=f"{title}: 0")
    detail_vars[key] = var
    tk.Label(frames["mem"], textvariable=var, width=15, anchor="w").pack()

for key, title in [("swap_total", "Swap Total"), ("swap_used", "Swap Used"), ("swap_free", "Swap Free")]:
    var = tk.StringVar(value=f"{title}: 0")
    detail_vars[key] = var
    tk.Label(frames["swap"], textvariable=var, width=15, anchor="w").pack()

# Add disk detail labels to all disk frames
for frame_key in ["disk", "diskR", "diskW"]:
    for key, title in [("disk_total", "Disk Total"), ("disk_used", "Disk Used"), ("disk_free", "Disk Free")]:
        var = tk.StringVar(value=f"{title}: 0")
        detail_vars[key] = var
        tk.Label(frames[frame_key], textvariable=var, width=15, anchor="w").pack()

# Start polling loop
window.after(POLL_INTERVAL, fetch_and_update)
window.mainloop()
