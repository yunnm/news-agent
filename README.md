# 每日全球晨报

每天自动抓取全球金融市场行情和科技新闻，通过 DeepSeek AI 汇总成中文晨报，以邮件推送。

## 功能

- **全球行情**：道琼斯、纳斯达克、标普 500、日经 225、恒生指数、上证指数、黄金、原油 — 8 项标的
- **科技新闻**：Hacker News + 36kr RSS 聚合
- **AI 总结**：DeepSeek 大模型生成结构化中文晨报（大盘表现、板块分析、AI/科技新闻、国际动态）
- **邮件推送**：HTML + 纯文本双格式，适配各种邮件客户端

## 架构

```
东方财富 API (push2.eastmoney.com)  →  行情数据
Hacker News / 36kr RSS              →  科技新闻
         ↓
   DeepSeek AI 汇总
         ↓
   网易邮箱 SMTP 推送
```

数据源选用东方财富（国内零延迟，稳定可靠），后端部署在阿里云函数计算（按需执行，近乎免费）。

## 项目结构

```
.
├── main.py              # 核心业务逻辑
├── index.py             # 阿里云 FC handler
├── s.yaml               # Serverless Devs 部署配置
├── requirements.txt     # Python 依赖
├── .env.example         # 环境变量模板
├── .fcignore            # FC 部署忽略规则
└── DEPLOY.md            # 部署指南
```

## 快速开始

### 1. 准备环境变量

```bash
cp .env.example .env
```

填写 `.env`：

```env
DEEPSEEK_API_KEY=sk-xxxxxxxx          # DeepSeek API Key
EMAIL_ADDRESS=your_email@163.com      # 网易邮箱
EMAIL_PASSWORD=your_smtp_auth_code    # SMTP 授权码（非登录密码）
EMAIL_HOST=smtp.163.com
EMAIL_PORT=465
EMAIL_TO=recipient@example.com        # 收件人
```

### 2. 本地运行

```bash
pip install -r requirements.txt
python main.py
```

### 3. 部署到阿里云 FC

详见 [DEPLOY.md](DEPLOY.md)。

```bash
npm install -g @serverless-devs/s
s config add
s deploy
```

部署后每天北京时间 8:00 自动执行。可在 FC 控制台点击「测试函数」手动触发。

## 成本

- 阿里云 FC：每月约 ¥0.01（在免费额度内）
- DeepSeek API：每次约 ¥0.01-0.03

## License

MIT
