# Cloud Vitals

A custom remote-monitoring solution for Linux servers.
It uses a Python agent on each VM and a central dashboard.

## Repository Layout
```
├── .gitignore
├── LICENSE
├── README.md
├── agent/
│   ├── agent_venv/
│   ├── agent.py
│   ├── requirements.txt
│   └── cloud-vitals-agent.service
├── dashboard/
│   ├── dash_venv/
│   ├── dashboard.py
│   └── requirements.txt
```

## Prerequisites
- Ubuntu 24.04 LTS 
- Python 3.12.3
- A system user `useragent` on each VM
- Port 5000 open between the dashboard and agents

## Firewall
You need to forward port 5000 so your dashboard can pull data from the agent.
On the VM, open port 5000/tcp:
```bash
# If you use UFW:
sudo ufw allow 5000/tcp

# If you use IPTables:
sudo iptables -A INPUT -p tcp --dport 5000 -j ACCEPT
```

## Agent Install
1. SSH into VM
2. Install venv support: `sudo apt update && sudo apt install -y python3-venv`
3. Copy your `agent/` folder to `/opt/cloudvitals/agent`
4. Create the service user: `sudo useradd -r -s /usr/sbin/nologin agentuser`
5. Switch to `agentuser` and set up the virtualenv:
   ```bash
   sudo -u agentuser bash
   cd /opt/cloud-vitals/agent
   python3 -m venv agent_venv
   source agent_venv/bin/activate
   pip install -r requirements.txt
   exit
   ```
6. Deploy and start the service:
   ```
   sudo cp agent/cloud-vitals-agent.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable cloud-vitals-agent
   sudo systemctl start cloud-vitals-agent
   ```

### Dashboard Install
*(WIP)*
