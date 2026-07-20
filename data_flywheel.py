"""
无人机保险数据飞轮 - 6字段数据记录
===================================
记录询价→报价→成交/拒保全链路数据
"""

import csv
import os
import json
from datetime import datetime

FLYWHEEL_FILE = os.path.join(os.path.dirname(__file__), "data", "flywheel_records.csv")
FLYWHEEL_SCHEMA = [
    "timestamp",                # 询价时间
    "drone_model",              # 无人机型号
    "usage",                    # 使用场景
    "annual_hours",             # 年飞行小时
    "pilot_level",              # 操作员资质
    "env_type",                 # 飞行环境
    "coverage_amount",          # 期望保额
    "risk_score",               # AI风险评分
    "risk_level",               # 风险等级
    "suggested_premium_min",    # 建议保费下限
    "suggested_premium_max",    # 建议保费上限
    "carrier_quote",            # 保司实际报价（如有）
    "bought",                   # 是否成交 (Y/N/null)
    "not_bought_reason",        # 未成交原因
    "actual_premium",           # 实际成交保费
]


def ensure_flywheel_file():
    """确保数据文件存在并含表头"""
    os.makedirs(os.path.dirname(FLYWHEEL_FILE), exist_ok=True)
    if not os.path.exists(FLYWHEEL_FILE):
        with open(FLYWHEEL_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(FLYWHEEL_SCHEMA)
        print(f"[数据飞轮] 创建文件: {FLYWHEEL_FILE}")
        return False
    return True


def record_inquiry(drone_model: str, usage: str, annual_hours: float,
                   pilot_level: str, env_type: str, coverage_amount: float,
                   risk_score: float, risk_level: str,
                   premium_min: float, premium_max: float) -> None:
    """记录一次询价"""
    ensure_flywheel_file()
    row = {
        "timestamp": datetime.now().isoformat(),
        "drone_model": drone_model,
        "usage": usage,
        "annual_hours": annual_hours,
        "pilot_level": pilot_level,
        "env_type": env_type,
        "coverage_amount": coverage_amount,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "suggested_premium_min": premium_min,
        "suggested_premium_max": premium_max,
        "carrier_quote": "",
        "bought": "",
        "not_bought_reason": "",
        "actual_premium": "",
    }
    with open(FLYWHEEL_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FLYWHEEL_SCHEMA)
        writer.writerow(row)
    return row


def update_outcome(row_index: int, bought: str = None,
                   not_bought_reason: str = None,
                   actual_premium: float = None,
                   carrier_quote: float = None) -> bool:
    """更新成交状态（手动或后续回填）"""
    ensure_flywheel_file()
    rows = []
    with open(FLYWHEEL_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i == row_index:
                if bought is not None:
                    row["bought"] = bought
                if not_bought_reason is not None:
                    row["not_bought_reason"] = not_bought_reason
                if actual_premium is not None:
                    row["actual_premium"] = str(actual_premium)
                if carrier_quote is not None:
                    row["carrier_quote"] = str(carrier_quote)
            rows.append(row)

    with open(FLYWHEEL_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FLYWHEEL_SCHEMA)
        writer.writeheader()
        writer.writerows(rows)
    return True


def get_flywheel_stats() -> dict:
    """返回数据飞轮统计"""
    ensure_flywheel_file()
    total = 0
    bought = 0
    not_bought = 0
    pending = 0

    with open(FLYWHEEL_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            if row.get("bought") == "Y":
                bought += 1
            elif row.get("bought") == "N":
                not_bought += 1
            else:
                pending += 1

    return {
        "total_inquiries": total,
        "bought": bought,
        "not_bought": not_bought,
        "pending_outcome": pending,
        "conversion_rate": round(bought / total * 100, 1) if total > 0 else 0,
    }


def get_recent_inquiries(limit: int = 10) -> list:
    """获取最近N条询价记录"""
    ensure_flywheel_file()
    rows = []
    with open(FLYWHEEL_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows[-limit:]
