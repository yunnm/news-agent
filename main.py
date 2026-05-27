import os
import requests
import feedparser

from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()

# DeepSeek API
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# Telegram 配置
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# 获取新闻
def get_news():

    rss_sources = [
        "https://feeds.feedburner.com/TechCrunch/",
        "https://hnrss.org/frontpage",
    ]

    all_news = []

    for rss_url in rss_sources:

        feed = feedparser.parse(rss_url)

        for entry in feed.entries[:5]:

            title = entry.title

            summary = ""

            if "summary" in entry:
                summary = entry.summary

            news_text = f"""
标题:
{title}

内容:
{summary}
"""

            all_news.append(news_text)

    return "\n\n".join(all_news)


# DeepSeek AI总结
def summarize_news(news_text):

    prompt = f"""
你是一位专业科技新闻编辑。

请总结以下新闻：

要求：

1. 用中文输出
2. 提炼最重要内容
3. 分类：
   - AI
   - 科技
   - 国际动态
4. 用Markdown格式
5. 不超过500字
6. 最后增加：
   今日一句话总结

新闻内容：
{news_text}
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7
    )

    return response.choices[0].message.content


# Telegram发送
def send_telegram(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    response = requests.post(url, data=data)

    print("Telegram状态:", response.status_code)


# 主任务
def daily_news_job():

    print("开始获取新闻...")

    news = get_news()

    print("开始AI总结...")

    summary = summarize_news(news)

    print(summary)

    print("开始发送Telegram...")

    send_telegram(summary)

    print("今日新闻推送完成")


# 程序入口
if __name__ == "__main__":
    daily_news_job()