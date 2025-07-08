# agent.py

"""
Cloud Vitals Agent

This script runs on each monitored Ubuntu server.
Collects key system performance metrics (CPU, memory, disk, network, etc.) and
exposes them as JSON via a endpoint. Designed to be run as a systemd service so
that it automatically starts on boot and restarts on failure.
"""
