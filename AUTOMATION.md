# 🤖 Automating the Daily Swing Scanner

To run the swing scanner automatically every day at market close (e.g., 3:45 PM IST), follow these steps.

## 1. Locate Python path
Run this in your terminal to find your python path:
```bash
which python3
```
*Example: `/usr/bin/python3` or `/Users/gaurav/Documents/code/personal/screener/venv/bin/python3`*

## 2. Locate Script path
Run this:
```bash
pwd
```
*Example: `/Users/gaurav/Documents/code/personal/screener`*

## 3. Edit Crontab
Open the crontab editor:
```bash
crontab -e
```

## 4. Add the Schedule
Add the following line to run every weekday (Mon-Fri) at 3:45 PM IST (10:15 UTC):

```bash
# Run swing scanner Mon-Fri at 15:45 IST
45 15 * * 1-5 cd /Users/gaurav/Documents/code/personal/screener && ./venv/bin/python3 main.py >> scanner.log 2>&1
```

## 5. Verify
List your cron jobs to confirm:
```bash
crontab -l
```

## 📜 Logs
Output will be saved to `scanner.log` in the project directory.
You can check it anytime:
```bash
tail -f scanner.log
```
