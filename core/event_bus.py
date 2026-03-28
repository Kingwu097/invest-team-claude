"""事件总线。支持发布-订阅模式和 SSE 推送。

EventBus 是 Agent 系统和 Dashboard 之间的桥梁：
- Agent/辩论协调器发布事件
- Dashboard 通过 SSE 订阅事件
- EventStore 持久化事件到 SQLite
"""

import asyncio
import logging
from typing import Callable, Coroutine, Any

from core.events import AnalysisEvent

logger = logging.getLogger(__name__)

# 订阅回调类型
EventCallback = Callable[[AnalysisEvent], Coroutine[Any, Any, None]]


class EventBus:
    """事件总线。线程安全的发布-订阅。"""

    def __init__(self):
        self._subscribers: list[EventCallback] = []
        self._queues: list[asyncio.Queue[AnalysisEvent]] = []
        self._lock = asyncio.Lock()

    async def publish(self, event: AnalysisEvent):
        """发布事件到所有订阅者和队列。"""
        # 通知回调订阅者
        for callback in self._subscribers:
            try:
                await callback(event)
            except Exception as e:
                logger.warning(f"事件回调失败: {e}")

        # 推送到所有 SSE 队列
        async with self._lock:
            for queue in self._queues:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("SSE 队列已满，丢弃事件")

    def subscribe(self, callback: EventCallback):
        """注册事件回调。"""
        self._subscribers.append(callback)

    def create_sse_queue(self) -> asyncio.Queue[AnalysisEvent]:
        """为 SSE 连接创建事件队列。"""
        queue: asyncio.Queue[AnalysisEvent] = asyncio.Queue(maxsize=200)
        asyncio.get_event_loop().run_until_complete(self._add_queue(queue))
        return queue

    async def create_sse_queue_async(self) -> asyncio.Queue[AnalysisEvent]:
        """异步版本：为 SSE 连接创建事件队列。"""
        queue: asyncio.Queue[AnalysisEvent] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._queues.append(queue)
        return queue

    async def remove_sse_queue(self, queue: asyncio.Queue):
        """移除 SSE 队列（连接断开时）。"""
        async with self._lock:
            if queue in self._queues:
                self._queues.remove(queue)

    async def _add_queue(self, queue: asyncio.Queue):
        async with self._lock:
            self._queues.append(queue)


# 全局事件总线单例
event_bus = EventBus()
