# 从 Railway 迁移到阿里云函数计算 — 部署指南

本项目的定时任务已从 Railway Worker 迁移到阿里云函数计算（FC 3.0），
推送方式也由 Telegram 改为网易邮箱 SMTP。

## 为什么选函数计算

| 维度 | Railway | 阿里云 FC |
|------|---------|-----------|
| 运行模式 | Worker 持续运行 | 定时触发，按需执行 |
| 计费 | 按资源时长 | 按调用次数+执行时长，更省 |
| 安全隔离 | 共享环境 | VPC 隔离，RAM 权限控制 |
| 国内访问 | 不稳定 | 国内节点，低延迟 |
| 合规 | 海外托管 | 国内合规，数据不出境 |

## 前置条件

1. 阿里云账号并实名认证：[注册](https://www.aliyun.com)
2. 开通函数计算 FC 服务：[开通 FC](https://fcnext.console.aliyun.com)
3. 安装 Node.js（用于 Serverless Devs CLI）

## 网易邮箱 SMTP 准备

在部署前，需要先在网易邮箱开启 SMTP 并获取授权码：

1. 登录 [网易邮箱](https://mail.163.com)（也支持 126.com / yeah.net）
2. 进入 **设置 → POP3/SMTP/IMAP**
3. 开启 **SMTP 服务**
4. 系统会生成一个 **授权码**（注意：这是授权码，不是你邮箱的登录密码）
5. 保存这个授权码，后面配置 `EMAIL_PASSWORD` 时会用到

## 部署步骤

### 1. 安装 Serverless Devs

```bash
npm install -g @serverless-devs/s
```

### 2. 配置阿里云凭证

```bash
s config add
```

按提示选择：
- **Cloud provider**: Alibaba Cloud (alibaba)
- **AccountName**: 任意名称（如 `default`）
- **AccountID**: 阿里云主账号 ID（在[控制台](https://account.console.aliyun.com)查看）
- **AccessKeyID / AccessKeySecret**: 在 [RAM 控制台](https://ram.console.aliyun.com/manage/ak) 创建

> **安全建议**：使用 RAM 子账号的 AccessKey，仅授予 FC 相关权限（AliyunFCFullAccess）。

### 3. 编辑 .env 文件

根据 `.env.example` 的模板，填写你的真实配置：

```env
DEEPSEEK_API_KEY=sk-xxxxxxxx
EMAIL_ADDRESS=your_email@163.com
EMAIL_PASSWORD=你的SMTP授权码
EMAIL_HOST=smtp.163.com
EMAIL_PORT=465
EMAIL_TO=收件人@example.com
```

### 4. 设置环境变量并部署

**PowerShell:**
```powershell
$env:DEEPSEEK_API_KEY="sk-xxxxxxxx"
$env:EMAIL_ADDRESS="your_email@163.com"
$env:EMAIL_PASSWORD="你的SMTP授权码"
$env:EMAIL_HOST="smtp.163.com"
$env:EMAIL_PORT="465"
$env:EMAIL_TO="收件人@example.com"
s deploy
```

### 5. 验证

- 在阿里云 FC 控制台找到 `daily-news-bot` 函数
- 点击「测试函数」手动触发一次
- 确认收件箱收到邮件

## 调整定时执行时间

编辑 `s.yaml` 中的 `cronExpression`，修改后重新 `s deploy`：

```yaml
cronExpression: "0 0 8 * * *"   # 每天 8:00
cronExpression: "0 30 8 * * *"  # 每天 8:30
cronExpression: "0 0 20 * * *"  # 每天 20:00
```

格式：`分 时 日 月 周 年`

## 换用其他网易域名

如果你用的是 126 邮箱或 Yeah 邮箱，修改 `.env` 中的 `EMAIL_HOST`：

| 邮箱 | SMTP 服务器 |
|------|------------|
| @163.com | smtp.163.com |
| @126.com | smtp.126.com |
| @yeah.net | smtp.yeah.net |

## 后续维护

- **更新代码**：修改代码后执行 `s deploy function`（仅更新函数，不重建触发器）
- **查看日志**：在 FC 控制台 → 函数详情 → 调用日志，或使用 `s logs`
- **监控告警**：在 FC 控制台配置错误率告警，阈值建议设为 1 次/24h
- **删除服务**：`s remove`（会删除函数和触发器，不可恢复）

## 成本预估

该脚本每天执行 1 次，每次约 30-60 秒，内存 512MB：

- 函数计算：约 ¥0.01/月（前 100 万次调用免费）
- 完全在免费额度内

## 文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | 核心业务逻辑（抓新闻 → AI 汇总 → 邮件推送） |
| `index.py` | FC handler 入口，包装 main.py 适配 FC 运行环境 |
| `s.yaml` | Serverless Devs 部署配置 |
| `.fcignore` | 部署时排除的文件 |
| `requirements.txt` | Python 依赖 |
