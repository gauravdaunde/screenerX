# 🤖 Automating the Scanners (UTC Server Config)

Since your server runs on **UTC**, these commands are adjusted for **Indian Market Hours (IST)**:
- Market Open (IST 9:15 AM) = **UTC 03:45 AM**
- Market Close (IST 3:15 PM) = **UTC 09:45 AM**
- Swing Report (IST 3:45 PM) = **UTC 10:15 AM**

## 1. Daily Swing Scanner (Market Close)
To run the swing scanner automatically every day at IST market close:

```bash
# Run swing scanner Mon-Fri at 10:15 AM UTC (3:45 PM IST)
15 10 * * 1-5 cd /Users/gaurav/Documents/code/personal/screener && ./venv/bin/python3 legacy/daily_swing_scan.py >> scanner.log 2>&1
```

## 2. Intraday Scalping Scanner (Precise Market Hours)
To run the **Nifty Jackpot Scalper** (Dual 3.0RR Strategy) **EVERY 1 MINUTE** from 9:15 AM to 3:15 PM IST:

### Single Combined Crontab Line (UTC Optimized)
Paste this into `crontab -e`. It uses a shell check to enforce the exact **03:45 AM to 09:45 AM UTC** window:

```bash
* 3-9 * * 1-5 [ "$(date +\%H\%M)" -ge "0345" ] && [ "$(date +\%H\%M)" -le "0945" ] && cd /Users/gaurav/Documents/code/personal/screener && ./venv/bin/python3 options_strategies/new_nifty_scanner.py >> scalper_cron.log 2>&1
```

### Alternative: Continuous Live Scanner
Runs a continuous loop regardless of crontab.
```bash
nohup ./venv/bin/python3 options_strategies/nifty_scalper_live.py >> scalper.log 2>&1 &
```

## 3. How to Setup
1. Open crontab:
   ```bash
   crontab -e
   ```
2. Paste the **UTC Optimized** lines above.
3. Save and exit (`:wq` in vim).

## 4. Verify
List your cron jobs:
```bash
crontab -l
```

## 📜 Logs
- Swing Scanner: `scanner.log`
- Scalper (Cron): `scalper_cron.log`
- Scalper (Live): `scalper.log`
