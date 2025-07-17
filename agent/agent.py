#!/usr/bin/env python3
# agent.py

"""
Cloud Vitals Agent

Collect system metrics at each interval, write seach sample as JSON
'/tmp/metrics_fifo', serve the latest metrics at '/metrics', and
accept start/stop commands at '/stress'.
"""

import os
import sys
import time
import json
import threading
import subprocess
import psutil
from flask import Flask, jsonify, request, abort


FIFO_PATH = '/tmp/metrics_fifo'
COLLECT_INTERVAL = 1    # seconds
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

# Track running stress-ng processes by class
stress_procs = {}
stress_lock = threading.Lock()

def init_fifo():
    """Create the named pipe if missing."""
    if not os.path.exists(FIFO_PATH):
        _mkfifo(FIFO_PATH)

def collect_metrics():
    """Sample metrics, update state, and write to pipe each interval."""
    global latest_metrics
    prev_net = psutil.net_io_counters()

    while True:
        cpu_pct = psutil.cpu_percent(interval=None)

        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        du = psutil.disk_usage('/')

        net = psutil.net_io_counters()
        sent = net.bytes_sent - prev_net.bytes_sent
        recv = net.bytes_recv - prev_net.bytes_recv
        net_bps = (sent + recv) / COLLECT_INTERVAL
        prev_net = net

        sample = {
            'timestamp': time.time(),
            'cpu_percent': cpu_pct,

            'memory_total': vm.total,
            'memory_used': vm.used,
            'memory_free': vm.free,
            'memory_percent': vm.percent,

            'swap_total': swap.total,
            'swap_used': swap.used,
            'swap_free': swap.free,
            'swap_percent': swap.percent,

            'disk_total': du.total,
            'disk_used': du.used,
            'disk_free': du.free,
            'disk_percent': du.percent,

            'network_average_bytes_per_sec': net_bps
        }

        # Update in-memory sample
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

def run_stress(stress_class, duration):
    """Launch cloud_vitals_stress.sh for class and duration."""
    script = os.path.join(os.path.dirname(__file__), 'cloud_vitals_stress.sh')
    if not (os.path.isfile(script) and os.access(script, os.X_OK)):
        return False

    cmd = [script, stress_class, str(duration)]
    with stress_lock:
        old = stress_procs.get(stress_class)
        if old and old.poll() is None:
            return False  # already running
        try:
            proc = subprocess.Popen(cmd)
            stress_procs[stress_class] = proc
            return True
        except Exception:
            return False

def abort_stress(stress_class):
    """Stop running a stress-ng job by class."""
    with stress_lock:
        proc = stress_procs.get(stress_class)
        if proc and proc.poll() is None:
            proc.terminate()
            stress_procs.pop(stress_class, None)
            return True
    return False

app = Flask(__name__)

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Return the latest metrics as JSON."""
    with metrics_lock:
        return jsonify(latest_metrics)

@app.route('/stress', methods=['POST'])
def stress_api():
    """Start a stress test. JSON Body: { "class": str, "duration": int }."""
    data = request.get_json() or {}
    cls = data.get('class')
    dur = data.get('duration')
    if not isinstance(cls, str) or not isinstance(dur, (int, float)):
        abort(400, 'Invalid payload')
    if not run_stress(cls, dur):
        abort(400, f'Failed to start stress for "{cls}"')
    return jsonify({'status': 'started', 'class': cls, 'duration': dur})

@app.route('/stress/<cls>', methods=['DELETE'])
def stress_abort_api(cls):
    """Abort a running stress test for the given class."""
    if not abort_stress(cls):
        abort(400, f'No running stress test for "{cls}"')
    return jsonify({'status': 'stopped', 'class': cls})

if __name__ == '__main__':
    init_fifo()

    # Start the collector thread
    threading.Thread(target=collect_metrics, daemon=True).start()

    # Serve API
    app.run(host=HOST, port=PORT)
