import json
import os
import re
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import feedparser
import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.163.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")


def _retry(func, name, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            result = func()
            if result is not None:
                return result
            raise ValueError("empty")
        except Exception as e:
            if attempt == max_retries:
                raise
            wait = (attempt + 1) * 2
            print(f"[retry] {name} #{attempt+1} fail, {wait}s: {e}")
            time.sleep(wait)


def get_news():
    rss_sources = [
        "https://hnrss.org/frontpage",
        "https://www.36kr.com/feed",
    ]
    all_news = []
    for rss_url in rss_sources:
        try:
            resp = requests.get(rss_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            resp.encoding = "utf-8"
            feed = feedparser.parse(resp.text)
        except Exception as e:
            print(f"[warn] RSS fail {rss_url}: {e}")
            continue
        for entry in feed.entries[:5]:
            title = entry.title
            summary = entry.get("summary", "")
            news_text = f"标题:\n{title}\n\n内容:\n{summary}"
            all_news.append(news_text)
    return "\n\n".join(all_news)


EM_API = "https://push2.eastmoney.com/api/qt/ulist.np/get"
EM_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}

EM_INDICES = {
    "道琼斯": "100.DJIA", "纳斯达克": "100.NDX", "标普500": "100.SPX",
    "日经225": "100.N225", "恒生指数": "100.HSI", "上证指数": "1.000001",
}
EM_COMMODITIES = {"黄金ETF": "113.AUX", "原油ETF": "113.CL"}


def _em_fetch(secids_map):
    codes = list(secids_map.values())
    params = {"fltt": "2", "fields": "f2,f3,f12,f14", "secids": ",".join(codes)}
    resp = requests.get(EM_API, params=params, headers=EM_HEADERS, timeout=10)
    data = resp.json()
    if not data.get("data") or not data["data"].get("diff"):
        raise ValueError("empty response")
    items = {}
    for row in data["data"]["diff"]:
        items[row["f12"]] = {"price": row.get("f2"), "pct": row.get("f3"), "name": row.get("f14", "")}
    result = {}
    short_map = {v.split(".")[-1]: k for k, v in secids_map.items()}
    for code, display_name in short_map.items():
        it = items.get(code)
        if it is None or it["pct"] is None:
            result[display_name] = None
            continue
        pct = float(it["pct"])
        emoji = "📈" if pct >= 0 else "📉"
        result[display_name] = f"{emoji} {display_name}: {pct:+.2f}%"
    return result


def get_market_data():
    result = []
    try:
        idx_data = _retry(lambda: _em_fetch(EM_INDICES), "indices")
        for name in EM_INDICES:
            result.append(idx_data.get(name) or f"{name}: 无数据")
    except Exception as e:
        print(f"[error] indices: {e}")
        import yfinance as yf
        yf_map = {"道琼斯": "^DJI", "纳斯达克": "^IXIC", "标普500": "^GSPC", "日经225": "^N225", "恒生指数": "^HSI", "上证指数": "000001.SS"}
        for name, ticker in yf_map.items():
            try:
                data = yf.Ticker(ticker)
                hist = data.history(period="2d")
                if len(hist) >= 2:
                    pct = (hist["Close"].iloc[-1] / hist["Close"].iloc[-2] - 1) * 100
                    emoji = "📈" if pct >= 0 else "📉"
                    result.append(f"{emoji} {name}: {pct:+.2f}%")
                else:
                    result.append(f"{name}: 数据不足")
            except Exception:
                result.append(f"{name}: 获取失败")
    try:
        cm_data = _retry(lambda: _em_fetch(EM_COMMODITIES), "commodities")
        for name in EM_COMMODITIES:
            result.append(cm_data.get(name) or f"{name}: 无数据")
    except Exception as e:
        print(f"[error] commodities: {e}")
        import yfinance as yf
        for name, ticker in [("黄金ETF", "GLD"), ("原油ETF", "USO")]:
            try:
                data = yf.Ticker(ticker)
                hist = data.history(period="2d")
                if len(hist) >= 2:
                    pct = (hist["Close"].iloc[-1] / hist["Close"].iloc[-2] - 1) * 100
                    emoji = "📈" if pct >= 0 else "📉"
                    result.append(f"{emoji} {name}: {pct:+.2f}%")
                else:
                    result.append(f"{name}: 数据不足")
            except Exception:
                result.append(f"{name}: 获取失败")
    return "\n".join(result)


def summarize_news(news_text):
    prompt = f"""你是一位专业金融与科技晨报编辑。请根据以下内容生成：# 今日全球晨报
要求：1. 用中文输出 2. 使用Markdown格式 3. 内容包括：全球大盘表现、热门板块分析、AI新闻、科技新闻、国际动态 4. 简单分析涨跌原因 5. 不超过800字 6. 最后增加：今日一句话总结
内容：{news_text}"""
    response = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": prompt}], temperature=0.7)
    return response.choices[0].message.content


def markdown_to_html(md_text):
    html = md_text
    paragraphs = html.split("\n\n")
    result = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith("# "):
            result.append(f"<h2>{p[2:]}</h2>")
        elif p.startswith("## "):
            result.append(f"<h3>{p[4:]}</h3>")
        elif p.startswith("### "):
            result.append(f"<h4>{p[5:]}</h4>")
        elif p.startswith("- "):
            items = [f"<li>{line[2:]}</li>" for line in p.split("\n") if line.startswith("- ")]
            result.append(f"<ul>{''.join(items)}</ul>")
        else:
            result.append(f"<p>{p}</p>")
    html = "\n".join(result)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"(?<!\n)\n(?!\n)", "<br>\n", html)
    return html


def send_email(markdown_body):
    today = datetime.now().strftime("%Y年%m月%d日")
    subject = f"每日全球晨报 - {today}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(markdown_body, "plain", "utf-8"))
    html_body = markdown_to_html(markdown_body)
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
    print(f"邮件已发送至 {EMAIL_TO}")


def daily_news_job():
    print("开始获取金融数据...")
    market_data = get_market_data()
    print(market_data)
    print("开始获取新闻...")
    news = get_news()
    full_content = f"# 全球市场\n\n{market_data}\n\n# 科技新闻\n\n{news}"
    print("开始AI总结...")
    summary = summarize_news(full_content)
    print(summary)
    print("开始发送邮件...")
    send_email(summary)
    print("今日晨报推送完成")


if __name__ == "__main__":
    daily_news_job()
