#!/usr/bin/env bash
# cloud_vitals_agent_check.sh
# Note: Make sure this is is executable with chmod +x

SERVICE=cloud_vitals_agent

if ! systemctl is-active --quiet "$SERVICE"; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') $SERVICE is down, restarting" \
    >> /var/log/cloud-vitals-agent-check.log
  systemctl restart "$SERVICE"
fi
