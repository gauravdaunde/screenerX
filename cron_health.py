from alerts import AlertBot
import config
import sys
import datetime

class HealthMonitor:
    def __init__(self):
        # Use the Health Bot Token
        self.bot = AlertBot(token=config.TELEGRAM_HEALTH_BOT_TOKEN)
        self.start_time = None
        
    def send_start_alert(self, job_name):
        self.start_time = datetime.datetime.now()
        msg = f"🟢 <b>JOB STARTED: {job_name}</b>\n\n🕒 Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}"
        self.bot.send_message(msg)
        
    def send_success_alert(self, job_name, details=""):
        end_time = datetime.datetime.now()
        duration = end_time - self.start_time if self.start_time else "N/A"
        msg = f"✅ <b>JOB SUCCESS: {job_name}</b>\n\n{details}\n\n🕒 End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n⏱️ Duration: {duration}"
        self.bot.send_message(msg)

    def send_failure_alert(self, job_name, error):
        end_time = datetime.datetime.now()
        duration = end_time - self.start_time if self.start_time else "N/A"
        msg = f"🔴 <b>JOB FAILED: {job_name}</b>\n\nError: {str(error)}\n\n🕒 End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n⏱️ Duration: {duration}"
        self.bot.send_message(msg)

if __name__ == "__main__":
    # CLI usage: python cron_health.py "Daily Scan" "success" "Found 5 stocks"
    if len(sys.argv) > 2:
        monitor = HealthMonitor()
        job = sys.argv[1]
        status = sys.argv[2]
        message = sys.argv[3] if len(sys.argv) > 3 else ""
        
        if status.lower() == "start":
            monitor.send_start_alert(job)
        elif status.lower() == "success":
            monitor.send_success_alert(job, message)
        else:
            monitor.send_failure_alert(job, message)
