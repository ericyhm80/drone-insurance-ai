"""
后台GLM学习器
=============
核保上传数据后静默运行，从保单数据中学习各维度偏差，
自动生成权重修正因子并持久化存储。

对核保完全透明——他们只看校准报告，不知道权重在变。
"""
import math
from collections import defaultdict
from calibration_store import save_company_corrections, log_calibration

# 维度到风险评分的映射函数名（简化版模型模拟）
DIMENSION_WEIGHT_KEYS = [
    "device_score", "battery_risk", "cargo_risk",
    "airworthiness", "obstacle_score",
    "usage_score", "bvlos_score",
    "pilot_score", "violation_score",
    "env_score", "exposure_score",
    "claims_score", "coverage_score", "tp_risk_score",
    "ph_risk_score", "fleet_discount",
]


def learn_from_policies(policies: list[dict], claims: list[dict],
                         company_id: str = "_default") -> dict:
    """
    核心学习函数：分析保单数据，生成维度修正因子

    原理：
      1. 对每条保单，估算模型预期的保费
      2. 对比实际保费 → 计算偏差率
      3. 按维度分组聚合偏差
      4. 偏差显著的维度生成修正因子
      5. 保存到持久化存储

    返回: 校准报告（与之前一致，不含权重信息）
    """
    if not policies:
        return {"note": "无数据", "dimension_adjustments": {}}

    # Step 1: 计算每条保单的偏差
    total_error = 0
    dimension_errors = defaultdict(list)

    for p in policies:
        model_premium = _estimate_model_premium(p)
        actual = p.get("actual_premium", 0)
        if model_premium <= 0 or actual <= 0:
            continue
        error_pct = (actual - model_premium) / model_premium
        total_error += abs(error_pct)

        # 按机型分组
        dim_key = ("drone_model", p.get("drone_model", "unknown"))
        dimension_errors[dim_key].append(error_pct)

        # 按投保人类型分组
        dim_key2 = ("policyholder_type", p.get("policyholder_type", "unknown"))
        dimension_errors[dim_key2].append(error_pct)

    avg_error = total_error / len(policies)

    # Step 2: 计算赔付率
    loss_ratio = 0
    if claims and policies:
        total_claims = sum(c.get("claim_amount", 0) for c in claims)
        total_premiums = sum(p.get("actual_premium", 0) for p in policies)
        if total_premiums > 0:
            loss_ratio = total_claims / total_premiums

    # Step 3: 生成修正因子
    corrections = {}
    adjustments = {}

    for (dim, sub_key), errors in dimension_errors.items():
        if len(errors) < 2:
            continue  # 样本太少，不修正
        avg_dim_error = sum(errors) / len(errors)
        if abs(avg_dim_error) > 0.05:  # 偏差>5%才需要修正
            # 修正因子 = 偏差的一半（保守学习，防止过拟合）
            correction = round(avg_dim_error * 0.5, 4)
            if dim not in corrections:
                corrections[dim] = {}
            corrections[dim][str(sub_key)] = correction
            adjustments[f"{dim}:{sub_key}"] = round(avg_dim_error * 100, 1)

    # Step 4: 如果有赔付数据，计算赔付率修正
    if loss_ratio > 0 and len(policies) >= 5:
        # 赔付率修正系数
        loss_correction = 0
        if loss_ratio > 0.7:
            loss_correction = 0.15  # 赔付率高 → 整体加费
        elif loss_ratio < 0.3:
            loss_correction = -0.08  # 赔付率低 → 整体降费
        if loss_correction != 0:
            corrections["_global"] = {"loss_ratio_correction": loss_correction}
            adjustments["赔付率校正"] = round(loss_correction * 100, 1)

    # Step 5: 保存修正因子（按公司隔离）
    if corrections:
        save_company_corrections(company_id, corrections)

    # Step 6: 记录校准日志
    log_calibration(
        company_id=company_id,
        policy_count=len(policies),
        claim_count=len(claims),
        avg_error=round(avg_error * 100, 1),
        loss_ratio=round(loss_ratio * 100, 1),
    )

    return {
        "dimension_adjustments": adjustments,
        "total_policies": len(policies),
        "total_claims": len(claims),
        "loss_ratio": round(loss_ratio * 100, 1),
        "notes": _generate_notes(adjustments, loss_ratio),
    }


def _estimate_model_premium(policy: dict) -> float:
    """估算模型对该保单的预期保费（简化版）"""
    from risk_engine import DRONE_RISK_DB, POLICYHOLDER_TYPE_MAP

    drone = policy.get("drone_model", "other_consumer")
    drone_info = DRONE_RISK_DB.get(drone, DRONE_RISK_DB["other_consumer"])

    # 基础费率
    base_rate = {
        "consumer": 4.0, "prosumer": 4.5,
        "industrial": 5.0, "agriculture": 5.5,
        "cargo": 7.0,
    }.get(drone_info["category"], 5.0)

    hull_sum = policy.get("hull_sum", 50000)
    tp_sum = policy.get("third_party_sum", 2000000)

    # 投保人类型修正
    ph_type = policy.get("policyholder_type", "国有企业")
    ph_info = POLICYHOLDER_TYPE_MAP.get(ph_type, POLICYHOLDER_TYPE_MAP["国有企业"])
    ph_factor = ph_info["factor"]

    hull_premium = hull_sum * base_rate / 100 * ph_factor
    tp_premium = tp_sum * 0.55 / 1000

    return hull_premium + tp_premium


def _generate_notes(adjustments: dict, loss_ratio: float) -> str:
    """生成校准说明（保持与之前一致）"""
    notes = []
    if loss_ratio > 70:
        notes.append(f"⚠️ 赔付率{loss_ratio:.0f}%，建议关注费率水平")
    elif loss_ratio < 30 and loss_ratio > 0:
        notes.append(f"✅ 赔付率{loss_ratio:.0f}%，风险可控")
    for dim, adj in adjustments.items():
        direction = "偏高" if adj > 0 else "偏低"
        notes.append(f"📊 {dim}偏差{abs(adj):.0f}%，{direction}")
    return "\n".join(notes) if notes else "✅ 模型偏差在合理范围内"
