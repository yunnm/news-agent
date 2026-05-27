import os
import requests
import feedparser
import yfinance as yf

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


# 获取科技新闻
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


# 获取金融市场数据
def get_market_data():

    markets = {
        "纳斯达克": "^IXIC",
        "标普500": "^GSPC",
        "道琼斯": "^DJI",
        "日经225": "^N225",
        "恒生指数": "^HSI",
        "上证指数": "000001.SS",
        "黄金ETF": "GLD",
        "原油ETF": "USO",
    }

    result = []

    for name, ticker in markets.items():

        try:

            data = yf.Ticker(ticker)

            hist = data.history(period="2d")

            if len(hist) >= 2:

                prev_close = hist["Close"].iloc[-2]
                latest_close = hist["Close"].iloc[-1]

                change = (
                    (latest_close - prev_close)
                    / prev_close
                ) * 100

                emoji = "📈"

                if change < 0:
                    emoji = "📉"

                result.append(
                    f"{emoji} {name}: {change:.2f}%"
                )

        except Exception as e:

            result.append(f"{name}: 获取失败")

    return "\n".join(result)


# DeepSeek AI总结
def summarize_news(news_text):

    prompt = f"""
你是一位专业金融与科技晨报编辑。

请根据以下内容生成：

# 今日全球晨报

要求：

1. 用中文输出
2. 使用Markdown格式
3. 内容包括：

- 全球大盘表现
- 热门板块分析
- AI新闻
- 科技新闻
- 国际动态

4. 简单分析涨跌原因
5. 不超过800字
6. 最后增加：
   今日一句话总结

内容：
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

    print("开始获取金融数据...")

    market_data = get_market_data()

    print(market_data)

    print("开始获取新闻...")

    news = get_news()

    # 合并数据
    full_content = f"""
# 全球市场

{market_data}

# 科技新闻

{news}
"""

    print("开始AI总结...")

    summary = summarize_news(full_content)

    print(summary)

    print("开始发送Telegram...")

    send_telegram(summary)

    print("今日晨报推送完成")


# 程序入口
if __name__ == "__main__":
    daily_news_job()