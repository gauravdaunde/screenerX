# Deploy to OCI (Always Free Tier)

## Prerequisites
1. **GitHub Repository**: Push your code to a private GH repo.
2. **Oracle Cloud Account**: Sign up for the Always Free tier.
3. **SSH Key**: Generate an SSH key pair (`ssh-keygen -t rsa -b 4096 -C "your_email@example.com"`).

---

## 1. Create VM Instance
1. Go to **Compute -> Instances -> Create Instance**.
2. **Image**: Canonical Ubuntu 22.04 or 24.04 (Minimal).
3. **Shape**: VM.Standard.A1.Flex (Ampere ARM) - Select 4 OCPUs, 24GB RAM (It's Free!).
4. **Networking**: Create new VCN with public subnet.
5. **SSH Keys**: Upload your PUBLIC key (`id_rsa.pub`).
6. Click **Create**. Copy the Public IP.

---

## 2. Server Setup (Run via SSH)
Connect: `ssh -i /path/to/private_key ubuntu@YOUR_PUBLIC_IP`

```bash
# Update System
sudo apt update && sudo apt upgrade -y

# Install Python 3.10+, Pip, Venv, Git
sudo apt install python3-pip python3-venv git -y

# Setup Firewall (Allow 8000 for API, 22 is open by default)
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save

# Clone Repo
git clone https://github.com/YOUR_USERNAME/screenerX.git
cd screenerX
```

---

## 3. Environment Setup
```bash
# Create Virtual Env
python3 -m venv venv
source venv/bin/activate

# Install Dependencies
pip install -r requirements.txt

# Create .env file
nano .env
# Paste your keys (Check .env.example)
```

---

## 4. Run Application (Background)

### Option A: Simple Crontab (For Scheduled Scanning)
Use this if you only need the scanner to run periodically.

```bash
crontab -e
```

Add these lines:
```bash
# Run Swing Scanner every 4 hours (Weekdays)
0 */4 * * 1-5 cd /home/opc/screenerX && /home/opc/screenerX/venv/bin/python main.py --scan >> /home/opc/screenerX/cron.log 2>&1

# [NEW] Run Trade Monitor every 2 minutes (Mon-Fri 9:15-15:30 IST)
# UTC: 03:45 to 10:00
*/2 3-10 * * 1-5 cd /home/opc/screenerX && /home/opc/screenerX/venv/bin/python trade_manager.py >> /home/opc/screenerX/trade_monitor.log 2>&1

# [NEW] Run Options Strategy Scanner Every 30 Mins (9:15 AM - 3:30 PM IST)
# UTC: 03:45 to 10:00
*/30 3-10 * * 1-5 cd /home/opc/screenerX && /home/opc/screenerX/venv/bin/python options_strategies/live_scanner.py >> /home/opc/screenerX/options_scanner.log 2>&1
```

---

## Option C: Run FastAPI Server (Systemd Service)
Use this to expose the API and monitoring dashboard.

1. Create Service File:
   `sudo nano /etc/systemd/system/screener.service`

2. Paste Content (Adjust paths):
   ```ini
   [Unit]
   Description=ScreenerX API
   After=network.target

   [Service]
   User=ubuntu
   WorkingDirectory=/home/ubuntu/screenerX
   ExecStart=/home/ubuntu/screenerX/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. Start Service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start screener
   sudo systemctl enable screener
   ```

4. Check Status:
   `sudo systemctl status screener`
