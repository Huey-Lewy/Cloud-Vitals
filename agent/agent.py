#!/usr/bin/env python3
# agent.py

"""
Cloud Vitals Agent

Collect CPU, memory, swap, disk, and network metrics at each interval,
write each sample as JSON to '/tmp/metrics_fifo', and serve the latest
metrics at '/metrics' via Flask on the configured host and port.
- Default Temp Folder: '/tmp/metrics_fifo'
- Default Interval (seconds): 1
- Default Host: 0.0.0.0
- Default Port: 5000
"""

import os
import sys
import time
import json
import threading
import psutil
from flask import Flask, jsonify

FIFO_PATH = '/tmp/metrics_fifo'
COLLECT_INTERVAL = 1  # seconds
HOST = '0.0.0.0'
PORT = 5000

# Alias POSIX calls so Pylance sees them
if sys.platform != "win32" and hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"):
    _mkfifo = os.mkfifo
    _O_NONBLOCK = os.O_NONBLOCK
else:
    def _mkfifo(path, mode=0o666):
        raise RuntimeError("mkfifo not supported on this platform")
    _O_NONBLOCK = 0

# Holds the latest sample
latest_metrics = {}
metrics_lock = threading.Lock()

def init_fifo():
    """Create the named pipe if it's missing."""
    if not os.path.exists(FIFO_PATH):
        _mkfifo(FIFO_PATH)

def collect_metrics():
    """Sample metrics, update state, and write to pipe each interval."""
    global latest_metrics
    prev_net = psutil.net_io_counters()

    while True:
        cpu_pct = psutil.cpu_percent(interval=None)
        mem_pct = psutil.virtual_memory().percent
        swap_pct = psutil.swap_memory().percent
        disk_pct = psutil.disk_usage('/').percent

        net = psutil.net_io_counters()
        sent = net.bytes_sent - prev_net.bytes_sent
        recv = net.bytes_recv - prev_net.bytes_recv
        net_bps = (sent + recv) / COLLECT_INTERVAL
        prev_net = net

        sample = {
            'timestamp': time.time(),
            'cpu_percent': cpu_pct,
            'memory_percent': mem_pct,
            'swap_percent': swap_pct,
            'disk_percent': disk_pct,
            'network_average_bytes_per_sec': net_bps
        }

        # Update in-memory sample\
        with metrics_lock:
            latest_metrics = sample

        # Write JSON line if a reader si on the pipe
        try:
            fd = os.open(FIFO_PATH, os.O_WRONLY | _O_NONBLOCK)
            with os.fdopen(fd, 'w') as fifo:
                fifo.write(json.dumps(sample) + '\n')
        except OSError:
            pass # no reader on pipe

        time.sleep(COLLECT_INTERVAL)

app = Flask(__name__)

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Serve the latest metrics as JSON."""
    with metrics_lock:
        return jsonify(latest_metrics)

if __name__ == '__main__':
    init_fifo()

    # Start the collector thread
    threading.Thread(target=collect_metrics, daemon=True).start()

    # Serve API
    app.run(host=HOST, port=PORT)
