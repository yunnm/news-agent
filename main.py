import schedule
import time

schedule.every().day.at("07:00").do(daily_news_job)

while True:
    schedule.run_pending()
    time.sleep(60)