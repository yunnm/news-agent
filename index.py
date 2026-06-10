import json
import logging
from main import daily_news_job

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    trigger_time = ""
    if isinstance(event, dict):
        trigger_time = event.get("triggerTime", "")
    elif isinstance(event, str):
        try:
            payload = json.loads(event)
            trigger_time = payload.get("triggerTime", "")
        except json.JSONDecodeError:
            pass

    logger.info("timer trigger: triggerTime=%s, requestId=%s", trigger_time, context.requestId)

    try:
        daily_news_job()
        logger.info("report done, requestId=%s", context.requestId)
        return {"status": "ok", "requestId": context.requestId}
    except Exception:
        logger.exception("report failed, requestId=%s", context.requestId)
        raise


if __name__ == "__main__":
    daily_news_job()
