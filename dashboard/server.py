"""Dashboard 后端服务器。

FastAPI + SSE 实时推送，提供：
- POST /api/analyze — 发起新分析（异步，通过 SSE 推送进度）
- GET /api/events/{session_id} — SSE 实时事件流
- GET /api/sessions — 历史分析列表
- GET /api/sessions/{session_id} — 单个分析详情 + 事件回放
- 静态文件服务 — React Dashboard
"""

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.event_bus import event_bus
from core.event_store import EventStore
from core.events import AnalysisEvent
from core.pipeline import AnalysisPipeline

logger = logging.getLogger(__name__)

# 全局状态
store = EventStore()
pipeline = AnalysisPipeline(bus=event_bus, store=store)
_running_tasks: dict[str, asyncio.Task] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Dashboard server starting...")
    yield
    # 清理运行中的任务
    for task in _running_tasks.values():
        task.cancel()
    logger.info("Dashboard server stopped.")


app = FastAPI(
    title="投资理财专家团队 Dashboard",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    stock_code: str


class AnalyzeResponse(BaseModel):
    session_id: str
    stock_code: str
    message: str


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def start_analysis(req: AnalyzeRequest):
    """发起新的分析任务（异步执行，通过 SSE 推送进度）。"""
    code = req.stock_code.strip()
    if not re.match(r"^[036]\d{5}$", code):
        raise HTTPException(400, f"无效的 A 股代码: {code}")

    # 创建管道实例并在后台运行
    p = AnalysisPipeline(bus=event_bus, store=store)

    async def run_task():
        try:
            result = await p.run(code)
            return result
        except Exception as e:
            logger.error(f"分析任务失败: {e}")

    task = asyncio.create_task(run_task())
    # 用简单方式获取 session_id: 等待第一个事件或设置超时
    await asyncio.sleep(0.3)

    # 从 store 获取最新的 running session
    sessions = store.list_sessions(limit=1)
    session_id = sessions[0]["session_id"] if sessions else "unknown"

    _running_tasks[session_id] = task

    return AnalyzeResponse(
        session_id=session_id,
        stock_code=code,
        message=f"分析已启动，通过 SSE 接收进度: /api/events/{session_id}",
    )


@app.get("/api/events/{session_id}")
async def sse_events(session_id: str, request: Request):
    """SSE 事件流。实时推送分析进度。"""

    async def event_generator():
        queue = await event_bus.create_sse_queue_async()
        try:
            # 先发送历史事件（用于重连或回放）
            existing = store.get_session_events(session_id)
            for evt in existing:
                data = json.dumps(evt, ensure_ascii=False, default=str)
                yield f"data: {data}\n\n"

            # 实时事件
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    if event.session_id == session_id:
                        data = json.dumps(event.to_sse_data(), ensure_ascii=False, default=str)
                        yield f"data: {data}\n\n"

                        # 如果分析完成或失败，发送完成信号后结束
                        if event.event_type.value in (
                            "analysis_completed", "analysis_failed"
                        ):
                            yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"
                            break
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield f": heartbeat\n\n"
        finally:
            await event_bus.remove_sse_queue(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/sessions")
async def list_sessions(limit: int = 20):
    """获取历史分析列表。"""
    return store.list_sessions(limit=limit)


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取单个分析的详情 + 完整事件。"""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(404, "分析记录不存在")
    events = store.get_session_events(session_id)
    return {"session": session, "events": events}


@app.get("/api/performance")
async def get_performance():
    """获取绩效汇总。"""
    from agents.performance import PerformanceTracker
    tracker = PerformanceTracker()
    summary = tracker.get_summary()
    trades = tracker.list_trades(limit=50)
    return {"summary": summary.model_dump(), "trades": trades}

# 静态文件服务
FRONTEND_DIR = Path(__file__).parent / "frontend"


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """服务 Dashboard 前端。"""
    # 优先查找 dist/index.html（构建后），否则查找 index.html（开发模式）
    for candidate in [FRONTEND_DIR / "dist" / "index.html", FRONTEND_DIR / "index.html"]:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return HTMLResponse("<h1>Dashboard 前端文件未找到</h1>", status_code=404)


# 挂载静态资源（如果 dist 目录存在）
dist_dir = FRONTEND_DIR / "dist"
if dist_dir.exists() and (dist_dir / "assets").exists():
    app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")
