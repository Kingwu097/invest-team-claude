"""通用重试装饰器，供 data 层所有模块使用。"""

import logging
import time
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
RETRY_INTERVAL = 3


def retry_fetch(func: Callable) -> Callable:
    """重试装饰器：失败重试 2 次，间隔 3s，仍失败返回 None 并记录警告。"""

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"{func.__name__} 失败 (attempt {attempt + 1}), "
                        f"{RETRY_INTERVAL}s 后重试: {e}"
                    )
                    time.sleep(RETRY_INTERVAL)
        logger.error(f"{func.__name__} 最终失败: {last_error}")
        return None

    return wrapper
