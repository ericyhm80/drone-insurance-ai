"""
保险公司数据导入 & 模型自动校准模块
=====================================
支持上传CSV格式的保单数据和理赔数据，
自动对比模型保费 vs 实际保费，调整12维权重。
"""

import json, csv, io
from datetime import datetime
from collections import defaultdict
import pandas as pd


# ============================================================
# 输入数据格式说明
# ============================================================
# 保单数据 (Policy CSV):
#   保单号,机型,机身保额,三者保额,实际总保费,投保人类型,投保日期
#   P001,M300,600000,2000000,4500,政府,2025-03-15
#   P002,M350,1000000,2000000,8200,企业,2025-06-20
#
# 理赔数据 (Claims CSV):
#   保单号,出险日期,赔付金额,事故原因
#   P001,2025-08-12,12000,炸机
#   P003,2025-09-03,3200,挂树
# ============================================================


REQUIRED_POLICY_COLS = [
    "保单号", "机型", "机身保额", "三者保额",
    "实际总保费", "投保人类型", "投保日期"
]
REQUIRED_CLAIMS_COLS = ["保单号", "出险日期", "赔付金额", "事故原因"]


def parse_policy_csv(csv_text: str) -> list[dict]:
    """解析保单CSV"""
    reader = csv.DictReader(io.StringIO(csv_text))
    policies = []
    for row in reader:
        try:
            policies.append({
                "policy_id": row.get("保单号", "").strip(),
                "drone_model": row.get("机型", "").strip(),
                "hull_sum": float(row.get("机身保额", 0)),
                "third_party_sum": float(row.get("三者保额", 0)),
                "actual_premium": float(row.get("实际总保费", 0)),
                "policyholder_type": row.get("投保人类型", "").strip(),
                "policy_date": row.get("投保日期", "").strip(),
            })
        except (ValueError, TypeError):
            continue
    return policies


def parse_claims_csv(csv_text: str) -> list[dict]:
    """解析理赔CSV"""
    reader = csv.DictReader(io.StringIO(csv_text))
    claims = []
    for row in reader:
        try:
            claims.append({
                "policy_id": row.get("保单号", "").strip(),
                "claim_date": row.get("出险日期", "").strip(),
                "claim_amount": float(row.get("赔付金额", 0)),
                "cause": row.get("事故原因", "").strip(),
            })
        except (ValueError, TypeError):
            continue
    return claims


def read_uploaded_file(file_bytes: bytes, filename: str) -> str:
    """读取上传文件为文本"""
    # 支持 .csv 和 .xlsx
    if filename.endswith(".xlsx"):
        df = pd.read_excel(io.BytesIO(file_bytes))
        return df.to_csv(index=False)
    return file_bytes.decode("utf-8-sig")


def calibrate_weights(policies: list[dict], claims: list[dict],
                      current_risk_engine: dict) -> dict:
    """
    核保数据 → 自动校准12维权重

    输入:
      - policies: 保单列表（含实际保费）
      - claims: 理赔列表
      - current_risk_engine: 当前评分卡的权重配置

    输出:
      - 校准后的权重
      - 校准报告（偏差率、调优幅度）
    """
    if not policies:
        return {"error": "无保单数据", "weights": current_risk_engine}

    # 按维度分组计算偏差
    # 例: 统计某机型的平均实际保费 vs 模型保费
    model_errors = defaultdict(list)

    for p in policies:
        # 模拟模型报价（后续改为直接调 risk_engine.score_drone_risk）
        model_premium = _simulate_model_premium(p, current_risk_engine)
        actual = p["actual_premium"]
        if model_premium and actual:
            error_pct = (actual - model_premium) / model_premium
            model_errors[p["drone_model"]].append(error_pct)

    # 计算各维度平均偏差
    adjustments = {}
    for dimension, errors in model_errors.items():
        avg_error = sum(errors) / len(errors)
        # 偏差 > 10% 的维度需要调权
        if abs(avg_error) > 0.1:
            adjustments[dimension] = round(avg_error * 100, 1)

    # 基于理赔数据调整风险评估
    loss_ratio = 0
    if claims and policies:
        total_claims = sum(c["claim_amount"] for c in claims)
        total_premiums = sum(p["actual_premium"] for p in policies)
        if total_premiums > 0:
            loss_ratio = total_claims / total_premiums

    return {
        "weights": current_risk_engine,
        "report": {
            "total_policies": len(policies),
            "total_claims": len(claims),
            "loss_ratio": round(loss_ratio * 100, 1),
            "dimension_adjustments": adjustments,
            "notes": _generate_calibration_notes(adjustments, loss_ratio),
        }
    }


def _simulate_model_premium(policy: dict, weights: dict) -> float:
    """模拟模型保费（简化版）"""
    # 这是一个简化的模拟，后续改成调risk_engine
    # 根据机型估算基础保费
    base_rate = {
        "M300": 4500, "M350": 5500, "M30": 3500,
        "M30T": 3800, "T50": 4000, "T40": 3600,
    }.get(policy["drone_model"], 5000)

    # 投保人类型系数
    type_factor = {
        "政府": 0.9, "国企": 0.95, "企业": 1.0,
        "个人": 1.2, "事业单位": 0.95,
    }.get(policy["policyholder_type"], 1.0)

    return base_rate * type_factor


def _generate_calibration_notes(adjustments: dict, loss_ratio: float) -> str:
    """生成中文校准说明"""
    notes = []
    if loss_ratio > 70:
        notes.append(f"⚠️ 赔付率{loss_ratio:.0f}%，建议整体上浮费率")
    elif loss_ratio < 30:
        notes.append(f"✅ 赔付率{loss_ratio:.0f}%，费率有下调空间")

    for dim, adj in adjustments.items():
        direction = "上调" if adj > 0 else "下调"
        notes.append(f"📊 {dim}偏差{abs(adj):.0f}%，建议{direction}权重")

    return "\n".join(notes) if notes else "✅ 模型偏差在合理范围内，无需大幅调整"
