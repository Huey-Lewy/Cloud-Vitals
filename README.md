### ⚠️ **Under Active Development** ⚠️

This project is under active development and subject to change. APIs, configurations, and feature behavior may be updated or removed without notice.

# About Cloud Vitals

Cloud Vitals monitors Ubuntu servers with a lightweight Python agent and a central dashboard. The agent collects CPU, memory, disk, network, and swap metrics every second, writes JSON samples to a named pipe, and exposes REST endpoints to fetch data or trigger stress tests.

You'll manage the agent with a `systemd` unit and a `cron`-based health check. The dashboard polls each agent, displays live and historical charts, and alerts you when metrics cross over your specified thresholds.

## Repository Layout

```
├── .gitignore
├── LICENSE
├── README.md
├── agent/
│   ├── agent_venv/                    # Python virtual environment
│   ├── agent.py                       # Main agent code
│   ├── requirements.txt               # Flask, psutil, etc.
│   ├── cloud_vitals_agent.service     # systemd unit file
│   ├── cloud_vitals_stress.sh         # stress‑ng wrapper script
│   └── cloud_vitals_agent_check.sh    # health‑check script
└── dashboard/
    ├── dash_venv/         # Python virtual environment
    ├── dashboard.py       # GUI code
    └── requirements.txt   # Dashboard dependencies
```

## Prerequisites

Before you begin, make sure you have the following:
* **Ubuntu** 24.04 LTS
* **Python** 3.12.3
* A system user named `agentuser` on each VM
* Port **5000** open so the dashboard can talk to the agents

**Note:** These are the exact versions we used during development. Other Ubuntu LTS (or Debian‑based) releases and Python 3.12.x versions _might_ work but haven’t been verified.

## Firewall

The dashboard and agent each communicate over TCP port 5000. You need to open this port on your VM's operating-system firewall **and** Google Cloud VPC firewall settings. With both OS-level and VPC firewall rules in place, your dashboard will be abvle to reach agent on port 5000.

#### **1\. Operating-system firewall.**

```bash
# If you are using UFW then enter this:
sudo ufw allow 5000/tcp

# If you are using iptables then enter this:
sudo iptables -A INPUT -p tcp --dport 5000 -j ACCEPT
```
#### **2\. Google Cloud VPC Firewall** _(with GUI)_

Make sure you have a rule (for example, `allow-agent-5000`) with these settings:
* **Network**: `default`
* **Direction**: `Ingress`
* **Action**: `Allow`
* **Targets**: instances tagged `cloud-vitals-agent`
* **Source IPv4 ranges**: `0.0.0.0/0` _(or a narrower CIDR, if preferred)_
* **Protocols and ports**: `tcp:5000`

#### **3\. Google Cloud PVC Firewall** _(with CLI)_

* Create/update the `allow-agent-5000` rule with the `gcloud` CLI using this command:
   ```
   gcloud compute firewall‐rules create allow-agent-5000 \
      --network=default \
      --direction=INGRESS \
      --action=ALLOW \
      --rules=tcp:5000 \
      --source-ranges=0.0.0.0/0 \
      --target-tags=cloud-vitals-agent \
      --description="Allow the Cloud Vitals agent to share telemetry data."
   ```

## Agent Install

#### **1\. SSH into your VM.**

#### **2\. Install Python virtual-env support and stress-ng.**

   ```bash
   sudo apt update
   sudo apt install -y python3-venv stress-ng
   ```

#### **3\. Copy agent folder.**

   ```bash
   sudo mkdir -p /opt/cloud-vitals/agent
   sudo cp -r ~/cloud-vitals/agent/* /opt/cloud-vitals/agent/
   ```

#### **4\. Create the service user and set permissions.**

   ```bash
   sudo useradd -r -s /usr/sbin/nologin agentuser
   sudo chown -R agentuser:agentuser /opt/cloud-vitals/agent
   ```

#### **5\. Set up the Python environment and install dependencies.**

   ```bash
   sudo -u agentuser python3 -m venv /opt/cloud-vitals/agent/agent_venv
   sudo -u agentuser /opt/cloud-vitals/agent/agent_venv/bin/pip install -r /opt/cloud-vitals/agent/requirements.txt
   ```

#### **6\. Make the helper scripts executable.**

   ```bash
   sudo chmod +x /opt/cloud-vitals/agent/cloud_vitals_stress.sh /opt/cloud-vitals/agent/cloud_vitals_agent_check.sh
   ```

#### **7\. Install and start the systemd service.**

   ```bash
   sudo cp /opt/cloud-vitals/agent/cloud_vitals_agent.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable cloud_vitals_agent
   sudo systemctl start cloud_vitals_agent
   ```

#### **8\. Verify the agent**

   ```bash
   systemctl status cloud_vitals_agent # Shows if the agent is running
   journalctl -u cloud_vitals_agent -f # Tail its logs live
   ls -l /tmp/metrics_fifo             # Verify the named pipe exists
   curl http://localhost:5000/metrics  # Fetch JSON metrics from the agent
   ```
   
#### **9\. Set up health‑check cron job**

   * **Make sure the log file exists**:
     ```bash
     sudo touch /var/log/cloud-vitals-agent-check.log
     sudo chmod 644 /var/log/cloud-vitals-agent-check.log
     ```
   * **Edit root's crontab**:
     ```bash
     sudo crontab -e
     ```
   * **Add the following at the end of the crontab file**:
     ```cron
     */5 * * * * /opt/cloud-vitals/agent/cloud_vitals_agent_check.sh >> /var/log/cloud-vitals-agent-check.log 2>&1
     ```
   * **Verify**:
     ```bash
     sudo crontab -l
     tail -f /var/log/cloud-vitals-agent-check.log
     ```

## Dashboard Setup

#### **1. Make sure that you pip install the dashboard dependencies**
```
pip install requirements.txt
```
#### **2. Change IP address to the one you want to use**
```
AGENT_URL       = "http://IPADDRESS:5000/metrics"
```
#### **3. Run Agent on your VM**
* See agent install section
#### **4. Run dashboard.py on a separate VM or local machine to monitor vitals**
``` 
python dashboard.py
```

