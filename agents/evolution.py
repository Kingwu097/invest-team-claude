"""Agent 自进化系统。

基于历史绩效数据，自动调整每个 Agent 在共识投票中的权重：
- 准确率高的 Agent → 权重提升
- 准确率低的 Agent → 权重降低
- 没有足够历史数据时 → 使用默认等权重

权重影响共识投票中的信心度加权：
  weighted_confidence = agent_confidence × agent_weight
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

WEIGHTS_PATH = Path(__file__).parent.parent / "data" / "agent_weights.json"
PERFORMANCE_DB = Path(__file__).parent.parent / "data" / "performance.db"

DEFAULT_WEIGHTS = {
    "fundamental": 1.0,
    "macro": 1.0,
    "sentiment": 1.0,
}

# 权重调整参数
MIN_TRADES_FOR_CALIBRATION = 5  # 至少 5 次交易才开始校准
MAX_WEIGHT = 1.5  # 权重上限
MIN_WEIGHT = 0.5  # 权重下限
LEARNING_RATE = 0.1  # 每次调整幅度


class AgentEvolution:
    """Agent 自进化管理器。"""

    def __init__(self, weights_path: Optional[Path] = None):
        self.weights_path = weights_path or WEIGHTS_PATH
        self._weights = self._load_weights()

    def _load_weights(self) -> dict[str, float]:
        """加载已保存的权重。"""
        if self.weights_path.exists():
            try:
                with open(self.weights_path) as f:
                    data = json.load(f)
                return data.get("weights", DEFAULT_WEIGHTS.copy())
            except Exception:
                pass
        return DEFAULT_WEIGHTS.copy()

    def _save_weights(self):
        """保存权重到文件。"""
        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "weights": self._weights,
            "updated_at": datetime.now().isoformat(),
            "calibration_history": self._get_history(),
        }
        with open(self.weights_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_weights(self) -> dict[str, float]:
        """获取当前 Agent 权重。"""
        return self._weights.copy()

    def get_weight(self, agent_role: str) -> float:
        """获取单个 Agent 的权重。"""
        return self._weights.get(agent_role, 1.0)

    def calibrate(self) -> dict[str, any]:
        """基于历史绩效数据校准 Agent 权重。

        校准逻辑：
        1. 计算每个 Agent 的历史"信心度校准偏差"
           = 平均信心度 vs 实际准确率 的差距
        2. 过度自信（信心度 > 准确率）的 Agent 降权
        3. 保守准确（信心度 ≤ 准确率）的 Agent 升权
        """
        db_path = PERFORMANCE_DB
        if not db_path.exists():
            return {"status": "no_data", "weights": self._weights}

        try:
            with sqlite3.connect(str(db_path)) as conn:
                total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
                if total < MIN_TRADES_FOR_CALIBRATION:
                    return {
                        "status": "insufficient_data",
                        "total_trades": total,
                        "required": MIN_TRADES_FOR_CALIBRATION,
                        "weights": self._weights,
                    }

                # 计算整体准确率和信心度
                evaluated = conn.execute(
                    "SELECT COUNT(*) FROM trades WHERE is_correct IS NOT NULL"
                ).fetchone()[0]
                if evaluated == 0:
                    return {"status": "no_evaluated_trades", "weights": self._weights}

                correct = conn.execute(
                    "SELECT COUNT(*) FROM trades WHERE is_correct=1"
                ).fetchone()[0]
                accuracy = correct / evaluated * 100
                avg_confidence = conn.execute(
                    "SELECT AVG(confidence) FROM trades WHERE is_correct IS NOT NULL"
                ).fetchone()[0] or 50

                # 校准偏差 = 信心度 - 准确率
                # 正值 = 过度自信，负值 = 过度保守
                calibration_gap = avg_confidence - accuracy

                adjustments = {}
                for role in DEFAULT_WEIGHTS:
                    old_w = self._weights.get(role, 1.0)

                    # 简单策略：如果系统整体过度自信，降低所有权重
                    # 未来可以按 Agent 分别计算
                    if calibration_gap > 10:
                        # 过度自信，降权
                        delta = -LEARNING_RATE
                    elif calibration_gap < -10:
                        # 过度保守，升权
                        delta = LEARNING_RATE
                    else:
                        delta = 0

                    new_w = max(MIN_WEIGHT, min(MAX_WEIGHT, old_w + delta))
                    self._weights[role] = round(new_w, 2)
                    adjustments[role] = {
                        "old": old_w, "new": new_w,
                        "delta": round(delta, 3),
                    }

                self._save_weights()

                return {
                    "status": "calibrated",
                    "total_trades": total,
                    "evaluated": evaluated,
                    "accuracy": round(accuracy, 1),
                    "avg_confidence": round(avg_confidence, 1),
                    "calibration_gap": round(calibration_gap, 1),
                    "adjustments": adjustments,
                    "weights": self._weights,
                }

        except Exception as e:
            logger.error(f"权重校准失败: {e}")
            return {"status": "error", "error": str(e), "weights": self._weights}

    def _get_history(self) -> list[dict]:
        """获取校准历史。"""
        if self.weights_path.exists():
            try:
                with open(self.weights_path) as f:
                    data = json.load(f)
                history = data.get("calibration_history", [])
                history.append({
                    "timestamp": datetime.now().isoformat(),
                    "weights": self._weights.copy(),
                })
                return history[-10:]  # 只保留最近 10 条
            except Exception:
                pass
        return []

    def to_markdown(self) -> str:
        """输出当前权重的 Markdown。"""
        lines = ["### Agent 权重（自进化）"]
        for role, w in self._weights.items():
            bar = "█" * int(w * 10) + "░" * (15 - int(w * 10))
            lines.append(f"- {role}: {w:.2f} {bar}")
        return "\n".join(lines)
