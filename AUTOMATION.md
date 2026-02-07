# 🤖 Automating the Scanners

## 1. Daily Swing Scanner (Market Close)
To run the swing scanner automatically every day at market close (e.g., 3:45 PM IST):

```bash
# Run swing scanner Mon-Fri at 15:45 IST
45 15 * * 1-5 cd /Users/gaurav/Documents/code/personal/screener && ./venv/bin/python3 legacy/daily_swing_scan.py >> scanner.log 2>&1
```

## 2. Intraday Scalping Scanner (Market Hours)
To run the **Nifty Scalper** every 5 minutes during market hours (9:15 AM - 3:30 PM approx):

```bash
# Run Nifty Scalper every 5 mins (Mon-Fri, 09:00-15:00 hours)
*/5 9-15 * * 1-5 cd /Users/gaurav/Documents/code/personal/screener && ./venv/bin/python3 options_strategies/nifty_scalper.py >> scalper.log 2>&1
```

## 3. How to Setup
1. Open crontab:
   ```bash
   crontab -e
   ```
2. Paste the lines above.
3. Save and exit (`:wq` in vim).

## 4. Verify
List your cron jobs:
```bash
crontab -l
```

## 📜 Logs
- Swing Scanner: `scanner.log`
- Scalper: `scalper.log`

Check logs:
```bash
tail -f scalper.log
```
