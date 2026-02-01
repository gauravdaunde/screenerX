# Deploying Screener to Oracle Cloud Infrastructure (OCI)

This guide provides a comprehensive analysis and step-by-step instructions for deploying your trading screener and automated trading bot to Oracle Cloud.

## Analysis & Recommendation

Your project consists of three components:
1.  **Daily Scanner (`main.py`)**: Scheduled task.
2.  **Real-Time Alerts (`realtime_alerts.py`)**: Background service.
3.  **API (`api.py`)**: Web server for manual controls and status.

### Recommended Architecture: **OCI Compute Instance (Always Free Tier)**
We recommend using an **always-free Compute Instance (VM)**.

*   **Primary Choice**: **Ampere (ARM) VM.Standard.A1.Flex** (4 OCPUs, 24GB RAM).
    *   *Best performance, but often out of stock.*
*   **Backup Choice**: **AMD VM.Standard.E2.1.Micro** (1 OCPU, 1GB RAM).
    *   *Lower performance, but usually available. Requires Swap memory setup.*

---

## Deployment Guide

### Step 1: Create the Compute Instance
1.  Log in to your Oracle Cloud Console.
2.  Go to **Compute** -> **Instances** -> **Create Instance**.
3.  **Placement**: 
    *   Try different **Availability Domains** (AD-1, AD-2, AD-3) if the default one is full.
4.  **Image & Shape**:
    *   **Image**: Oracle Linux 8 or 9 (or Ubuntu 22.04).
    *   **Shape (Option A - Preferred)**: **Ampere (ARM) VM.Standard.A1.Flex**.
    *   **Shape (Option B - Backup)**: **AMD VM.Standard.E2.1.Micro**.
        *   *Note: If you receive an "Out of Capacity" error for A1 Flex, select this AMD shape instead.*
5.  **Networking (CRITICAL STEP)**: 
    *   If creating a new VCN, ensure **"Create new VCN"** and **"Create new public subnet"** are selected.
    *   **IMPORTANT**: Scroll down to "Public IPv4 address" and select **"Assign a public IPv4 address"**. 
    *   *If you do not check this, you will not be able to connect to your server.*
6.  **SSH Keys**: "**Save Private Key**" (IMPORTANT: Do not lose this!).
7.  Click **Create**. Wait for it to turn "Running".

### Step 2: Connect to the Server
Look for **"Public IP"** on the instance details page.

Open your terminal and SSH into the server using the key you saved.

```bash
chmod 400 path/to/key.key
ssh -i path/to/key.key opc@<PUBLIC_IP_ADDRESS>
```

### Step 3: Configure the Environment
**IMPORTANT**: If you are using the **AMD Micro** instance (1GB RAM), you **MUST** create a swap file first, or your apps will crash.

#### 3a. Create Swap File (Only for AMD Micro Instance)
```bash
# Allocate 4GB swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

#### 3b. Install Software
Run these commands on the server to install Python and Git:

```bash
# Update system
sudo dnf update -y

# Install Python 3.9 (or newer) and Git
sudo dnf install -y python39 git

# Verify installation
python3.9 --version
```

### Step 4: Deploy the Code
1.  **Clone the Repository**:
    ```bash
    git clone <YOUR_GITHUB_REPO_URL> screener
    cd screener
    ```

2.  **Set up Virtual Environment**:
    ```bash
    python3.9 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    ```

3.  **Configure Secrets (`.env`)**:
    Create the `.env` file manually on the server.
    ```bash
    nano .env
    ```
    *Add your API Keys here:*
    ```env
    API_KEY=my_secret_password_123
    TELEGRAM_BOT_TOKEN=...
    TELEGRAM_HEALTH_BOT_TOKEN=... (Create a 2nd bot for system alerts)
    TELEGRAM_CHAT_ID=...
    ```
    *Save and exit.*
    
4.  **Initialize Database (Production Mode)**:
    This sets up SQLite WAL (Write-Ahead-Log) mode for better concurrency.
    ```bash
    python3 trade_db.py
    ```

---

## Option A: Run Daily Scanner (Cron Job)
Use this for the daily scheduled scan.

1.  **Open Crontab**:
    ```bash
    crontab -e
    ```

2.  **Add Schedule**:
    Add this line to run strictly at 3:45 PM IST (which is **10:15 UTC**).
    
    ```bash
    # Run daily scanner at 10:15 UTC (15:45 IST) Mon-Fri
    15 10 * * 1-5 cd /home/opc/screener && /home/opc/screener/venv/bin/python main.py >> scanner.log 2>&1
    
    # [NEW] Run Trade Monitor every 15 minutes (Mon-Fri 9:15-15:30 IST)
    # UTC: 03:45 to 10:00
    */15 3-10 * * 1-5 cd /home/opc/screener && /home/opc/screener/venv/bin/python trade_manager.py >> trade_monitor.log 2>&1
    ```

---

## Option B: Run Real-Time Alerts (Systemd Service)
Use this for the continuous background monitoring.

1.  **Create Service File**:
    ```bash
    sudo nano /etc/systemd/system/screener-realtime.service
    ```

2.  **Configuration**:
    ```ini
    [Unit]
    Description=Screener Real-Time Alerts
    After=network.target

    [Service]
    User=opc
    WorkingDirectory=/home/opc/screenerX
    ExecStart=/home/opc/screenerX/venv/bin/python realtime_alerts.py
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target
    ```
    *(Note: Ensure path is `/home/opc/screenerX` if that's your folder name)*

3.  **Start Service**:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable screener-realtime
    sudo systemctl start screener-realtime
    ```

---

## Option C: Run FastAPI Server (Systemd Service)
Use this to expose the API.

1.  **Open Local Firewall Port (8000)**:
    Required to access the API from the internet.
    ```bash
    # Open port 8000 on the server itself
    sudo firewall-cmd --permanent --add-port=8000/tcp
    sudo firewall-cmd --reload
    ```
    
2.  **Open Oracle Cloud "Ingress Rule" (CRITICAL)**:
    * Even if the server firewall is open, Oracle blocks ports by default.
    *   Go to **OCI Console** -> **Instances** -> Click your instance.
    *   Click on the **Subnet** (e.g., `subnet-2023...`).
    *   Click on the **Security List** (e.g., `Default Security List for...`).
    *   Click **Add Ingress Rules**.
    *   **Source CIDR**: `0.0.0.0/0`
    *   **IP Protocol**: `TCP`
    *   **Destination Port Range**: `8000`
    *   Click **Add Ingress Rules**.

3.  **Create Service File**:
    ```bash
    sudo nano /etc/systemd/system/screener-api.service
    ```

4.  **Configuration**:
    *(We use 'python -m uvicorn' instead of just 'uvicorn' to avoid permission issues)*
    ```ini
    [Unit]
    Description=Screener API
    After=network.target

    [Service]
    User=opc
    WorkingDirectory=/home/opc/screenerX
    ExecStart=/home/opc/screenerX/venv/bin/python -m uvicorn api:app --host 0.0.0.0 --port 8000
    Restart=always
    RestartSec=10

    [Install]
    WantedBy=multi-user.target
    ```

5.  **Start Service**:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable screener-api
    sudo systemctl start screener-api
    ```

6.  **Access**:
    *   **Dashboard**: `http://<YOUR_IP>:8000/portfolio?token=YOUR_API_KEY`
    *   **API Docs**: `http://<YOUR_IP>:8000/docs` (Use 'Authorize' button)

---

## Troubleshooting

### "Permission denied" on EXEC
1.  **Grant Execution Permissions**:
    ```bash
    sudo chown -R opc:opc /home/opc/screenerX
    chmod -R 755 /home/opc/screenerX
    ```
2.  **Fix SELinux Context (CRITICAL FIX)**:
    ```bash
    sudo chcon -R -t bin_t /home/opc/screenerX/venv/bin/
    ```
3.  **Restart Service**:
    ```bash
    sudo systemctl restart screener-api
    ```

### "DatabaseError: no such table: trades"
1.  **Run Initialization**:
    ```bash
    cd ~/screenerX
    source venv/bin/activate
    python3 trade_db.py
    ```

### "Site Can't Be Reached" (Timeout)
1.  **Check OCI Security List**: Add Ingress Rule for Port 8000 (0.0.0.0/0).
