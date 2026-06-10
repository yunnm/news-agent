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

# 加载环境变量
load_dotenv()

# DeepSeek API
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# 网易邮箱 SMTP 配置
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.163.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO")


def _retry(func, name, max_retries=2):
    """带指数退避的重试封装"""
    for attempt in range(max_retries + 1):
        try:
            result = func()
            if result is not None:
                return result
            raise ValueError("返回为空")
        except Exception as e:
            if attempt == max_retries:
                raise
            wait = (attempt + 1) * 2
            print(f"[retry] {name} 第{attempt+1}次失败, {wait}s后重试: {e}")
            time.sleep(wait)


# 获取科技新闻
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
            print(f"[warn] RSS获取失败 {rss_url}: {e}")
            continue

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


# ── 东方财富行情 API ──
EM_API = "https://push2.eastmoney.com/api/qt/ulist.np/get"
EM_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://quote.eastmoney.com/",
}

# 指数映射: 显示名 -> 东方财富 secid
EM_INDICES = {
    "道琼斯":   "100.DJIA",
    "纳斯达克": "100.NDX",
    "标普500":  "100.SPX",
    "日经225":  "100.N225",
    "恒生指数": "100.HSI",
    "上证指数": "1.000001",
}

# 商品映射: 显示名 -> secid (COMEX via 东方财富)
EM_COMMODITIES = {
    "黄金ETF": "113.AUX",   # COMEX黄金
    "原油ETF": "113.CL",    # WTI原油
}


def _em_fetch(secids_map):
    """
    通过东方财富 API 批量拉取行情。
    返回 {name: "📈/📉 name: +x.xx%"} 字典。
    """
    codes = list(secids_map.values())
    params = {
        "fltt": "2",
        "fields": "f2,f3,f12,f14",
        "secids": ",".join(codes),
    }
    resp = requests.get(EM_API, params=params, headers=EM_HEADERS, timeout=10)
    data = resp.json()

    if not data.get("data") or not data["data"].get("diff"):
        raise ValueError("东方财富返回空数据")

    # 建立 code -> {name, price, pct} 的索引
    items = {}
    for row in data["data"]["diff"]:
        items[row["f12"]] = {
            "price": row.get("f2"),
            "pct": row.get("f3"),
            "name": row.get("f14", ""),
        }

    result = {}
    reverse_map = {v: k for k, v in secids_map.items()}
    # 东方财富返回的 f12 是短码(去掉市场前缀)，需要匹配
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


# 获取金融市场数据
def get_market_data():
    """
    获取全球金融市场行情。
    主数据源: 东方财富 (国内可达，JSON格式，稳定可靠)
    备用: yfinance (兜底)
    """

    result = []

    # ── 六大指数: 东方财富一次请求 ──
    try:
        idx_data = _retry(lambda: _em_fetch(EM_INDICES), "全球指数(东方财富)")
        for name in EM_INDICES:
            result.append(idx_data.get(name) or f"{name}: 无数据")
    except Exception as e:
        print(f"[error] 东方财富指数获取失败: {e}")
        # 全部失败时用 yfinance 逐个兜底
        import yfinance as yf
        yf_map = {
            "道琼斯": "^DJI", "纳斯达克": "^IXIC", "标普500": "^GSPC",
            "日经225": "^N225", "恒生指数": "^HSI", "上证指数": "000001.SS",
        }
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

    # ── 黄金 & 原油: 东方财富 ──
    try:
        cm_data = _retry(lambda: _em_fetch(EM_COMMODITIES), "商品(东方财富)")
        for name in EM_COMMODITIES:
            result.append(cm_data.get(name) or f"{name}: 无数据")
    except Exception as e:
        print(f"[error] 东方财富商品获取失败: {e}")
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


def markdown_to_html(md_text):
    """将基本 Markdown 转为 HTML，适配邮件客户端。"""
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


# 网易邮箱发送
def send_email(markdown_body):
    """通过网易 SMTP 发送邮件。"""
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


# 主任务
def daily_news_job():

    print("开始获取金融数据...")
    market_data = get_market_data()
    print(market_data)

    print("开始获取新闻...")
    news = get_news()

    full_content = f"""
# 全球市场

{market_data}

# 科技新闻

{news}
"""

    print("开始AI总结...")
    summary = summarize_news(full_content)
    print(summary)

    print("开始发送邮件...")
    send_email(summary)
    print("今日晨报推送完成")


if __name__ == "__main__":
    daily_news_job()
