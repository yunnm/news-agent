"""阿里云函数计算入口 - FC handler 包装器。

将原有 main.py 中的 daily_news_job 封装成 FC 标准 handler，
同时兼容本地直接运行。
"""

import json
import logging

from main import daily_news_job

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """阿里云 FC 3.0 标准 handler。

    event:  触发器传入的事件数据（timer 触发器通常为空或 {"triggerTime": "..."}）
    context: 函数运行时上下文（request_id, credentials 等）
    """
    trigger_time = ""
    if isinstance(event, dict):
        trigger_time = event.get("triggerTime", "")
    elif isinstance(event, str):
        try:
            payload = json.loads(event)
            trigger_time = payload.get("triggerTime", "")
        except json.JSONDecodeError:
            pass

    logger.info("定时触发执行，triggerTime=%s, requestId=%s",
                trigger_time, context.requestId)

    try:
        daily_news_job()
        logger.info("晨报推送完成, requestId=%s", context.requestId)
        return {"status": "ok", "requestId": context.requestId}
    except Exception:
        logger.exception("晨报执行失败, requestId=%s", context.requestId)
        raise


# 本地直接运行时的入口
if __name__ == "__main__":
    daily_news_job()
