"""
无人机保险AI核保引擎 - 风险评分与定价建议
=====================================
Phase 1: 规则引擎 + 简易评分卡
Phase 2: 替换为 XGBoost 模型

v0.2 — 基于武警特勤支队2026年无人机保险采购标书校准
"""

DRONE_RISK_DB = {
    # 消费级
    "DJI Mini 4 Pro":       {"category": "consumer",    "base_price_cny": 8000,   "crash_rate": 0.08, "parts_cost": "low"},
    "DJI Air 3":            {"category": "consumer",    "base_price_cny": 12000,  "crash_rate": 0.06, "parts_cost": "low"},
    "DJI Mavic 3 Pro":      {"category": "prosumer",    "base_price_cny": 22000,  "crash_rate": 0.05, "parts_cost": "medium"},
    "DJI Mavic 4":          {"category": "prosumer",    "base_price_cny": 28000,  "crash_rate": 0.04, "parts_cost": "medium"},
    "DJI Mavic 2":          {"category": "prosumer",    "base_price_cny": 15000,  "crash_rate": 0.06, "parts_cost": "medium"},
    # 行业级
    "DJI Matrice 350 RTK":  {"category": "industrial",  "base_price_cny": 65000,  "crash_rate": 0.03, "parts_cost": "high"},
    "DJI Matrice 4T":       {"category": "industrial",  "base_price_cny": 55000,  "crash_rate": 0.03, "parts_cost": "high"},
    "DJI Matrice 30T (M30T)": {"category": "industrial","base_price_cny": 35000,  "crash_rate": 0.04, "parts_cost": "high"},
    "DJI H30T":             {"category": "industrial",  "base_price_cny": 40000,  "crash_rate": 0.04, "parts_cost": "high"},
    "DJI Mavic 3T (企业版)": {"category": "industrial", "base_price_cny": 25000,  "crash_rate": 0.05, "parts_cost": "medium"},
    # 运载无人机
    "DJI FlyCart 30":       {"category": "cargo",       "base_price_cny": 125000, "crash_rate": 0.035, "parts_cost": "very_high"},
    # 农业
    "DJI Agras T60":        {"category": "agriculture", "base_price_cny": 60000,  "crash_rate": 0.04, "parts_cost": "high"},
    # 其他品牌
    "Autel EVO Max 4T":     {"category": "industrial",  "base_price_cny": 50000,  "crash_rate": 0.04, "parts_cost": "high"},
    "Autel EVO Lite":       {"category": "consumer",    "base_price_cny": 10000,  "crash_rate": 0.07, "parts_cost": "low"},
    # 默认
    "other_consumer":       {"category": "consumer",    "base_price_cny": 15000,  "crash_rate": 0.07, "parts_cost": "medium"},
    "other_industrial":     {"category": "industrial",  "base_price_cny": 50000,  "crash_rate": 0.04, "parts_cost": "high"},
}

USAGE_RISK_MAP = {
    "航拍摄影":        {"base_factor": 0.8,  "desc": "低空慢速，风险最低"},
    "农业植保":        {"base_factor": 1.2,  "desc": "低空作业，环境复杂"},
    "物流配送":        {"base_factor": 1.5,  "desc": "城市低空，人流量大"},
    "巡检/测绘":       {"base_factor": 1.1,  "desc": "中等高度，任务明确"},
    "应急/消防":       {"base_factor": 1.3,  "desc": "高风险环境"},
    "应急/公共安全":    {"base_factor": 1.4,  "desc": "武警/警务任务，任务环境不可控"},
    "警用侦查/监控":   {"base_factor": 1.3,  "desc": "城市低空侦查，行动频次高"},
    "运载/物资投送":   {"base_factor": 1.6,  "desc": "载重飞行，坠毁损失大，第三方风险高"},
    "教育培训":        {"base_factor": 0.9,  "desc": "受控环境"},
    "其他":            {"base_factor": 1.0,  "desc": "通用场景"},
}

ENV_RISK_MAP = {
    "城市密集区":  {"factor": 1.4, "desc": "人车密集，第三方风险高"},
    "城市郊区":    {"factor": 1.1, "desc": "人口密度中等"},
    "野外/农村":   {"factor": 0.8, "desc": "人员稀少，碰撞风险低"},
    "工业厂区":    {"factor": 1.2, "desc": "设备密集，电磁干扰"},
    "水域/海岸":   {"factor": 1.3, "desc": "坠落回收困难"},
    "室内":        {"factor": 0.7, "desc": "受控环境"},
}

PILOT_LEVEL_MAP = {
    "无证（需在飞手指导下操作）": {"factor": 1.6, "min_hours": 0},
    "CAAC视距内驾驶员":            {"factor": 1.2, "min_hours": 50},
    "CAAC超视距驾驶员（机长）":    {"factor": 1.0, "min_hours": 100},
    "CAAC教员":                    {"factor": 0.8, "min_hours": 200},
    "AOPA合格证":                  {"factor": 1.3, "min_hours": 30},
}

# 三者险费率基准（参考市场行情：¥180K/¥32.67M ≈ 0.55%）
# 按保额分档
THIRD_PARTY_RATE_MAP = {
    500000:  0.35,    # 50万三者险
    1000000: 0.45,    # 100万
    2000000: 0.55,    # 200万（武警标书基准）
    5000000: 0.70,    # 500万
    10000000: 0.85,   # 1000万
}


def score_drone_risk(drone_model: str, usage: str, annual_hours: float,
                     pilot_level: str, env_type: str, hull_coverage: float,
                     third_party_limit: float = 2000000,
                     previous_claims: int = 0, battery_cycles: int = 0,
                     fleet_size: int = 1) -> dict:
    """
    核心风险评估函数
    返回风险评分(0-100)、建议费率区间(‰)、详细因子分解

    参数:
        hull_coverage: 机身险保额（元）
        third_party_limit: 三者险单机保额（元）
        fleet_size: 同一合同下的机队数量（批量折扣）
    """
    # ---- 1. 设备风险 ----
    drone_info = DRONE_RISK_DB.get(drone_model)
    if not drone_info:
        if "agriculture" in usage.lower() or "植保" in usage:
            drone_info = DRONE_RISK_DB["DJI Agras T60"]
        elif "运载" in usage or "cargo" in str(drone_model).lower():
            drone_info = DRONE_RISK_DB["DJI FlyCart 30"]
        elif "industrial" in str(drone_model).lower() or "行业" in str(drone_model).lower():
            drone_info = DRONE_RISK_DB["other_industrial"]
        else:
            drone_info = DRONE_RISK_DB["other_consumer"]

    device_score = drone_info["crash_rate"] * 100  # 0-10分
    battery_risk = min(battery_cycles / 200, 1.0) * 5  # 0-5分

    # 运载无人机额外风险
    cargo_risk = 3 if drone_info["category"] == "cargo" else 0

    # ---- 2. 使用场景风险 ----
    usage_info = USAGE_RISK_MAP.get(usage, USAGE_RISK_MAP["其他"])
    usage_score = (usage_info["base_factor"] - 0.7) * 20  # 0-18分

    # ---- 3. 环境风险 ----
    env_info = ENV_RISK_MAP.get(env_type, ENV_RISK_MAP["城市郊区"])
    env_score = (env_info["factor"] - 0.5) * 15  # 0-13.5分

    # ---- 4. 操作员风险 ----
    pilot_info = PILOT_LEVEL_MAP.get(pilot_level, PILOT_LEVEL_MAP["无证（需在飞手指导下操作）"])
    pilot_score = (pilot_info["factor"] - 0.6) * 25  # 0-25分

    # ---- 5. 暴露量风险 ----
    if annual_hours < 50:
        exposure_score = 2
    elif annual_hours < 200:
        exposure_score = 5
    elif annual_hours < 500:
        exposure_score = 8
    else:
        exposure_score = 12
    exposure_score = min(exposure_score, 15)

    # ---- 6. 历史理赔 ----
    claims_score = min(previous_claims * 8, 20)

    # ---- 7. 机身保额配置 ----
    value_ratio = hull_coverage / drone_info["base_price_cny"]
    if value_ratio < 0.5:
        coverage_score = 2
    elif value_ratio < 1.0:
        coverage_score = 5
    elif value_ratio < 1.5:
        coverage_score = 8
    else:
        coverage_score = 12
    coverage_score = min(coverage_score, 12)

    # ---- 8. 三者险风险 ----
    # 三者险保额越高，整体风险敞口越大
    tp_rate = THIRD_PARTY_RATE_MAP.get(third_party_limit, 0.55)
    tp_risk_score = min(tp_rate * 10, 8)  # 0-8分

    # ---- 9. 机队批量折扣 ----
    fleet_discount = max(0, (fleet_size - 1) * 0.5)  # 每多一架减0.5分
    fleet_discount = min(fleet_discount, 5)

    # ---- 综合评分 ----
    raw_score = (device_score + battery_risk + cargo_risk + usage_score +
                 env_score + pilot_score + exposure_score + claims_score +
                 coverage_score + tp_risk_score - fleet_discount)

    total_score = max(0, min(raw_score, 100))

    # ---- 风险等级 & 费率（基于真实市场数据校准）----
    # 机身险费率参考（%）：DJI Care Refresh 约3-8%/年，工业级更高
    # 三者险费率参考（‰）：0.3-0.7‰（TML为主，赔付率低）
    if total_score <= 25:
        risk_level = "低风险 🟢"
        risk_desc = "AI自动承保，费率优惠"
        hull_rate_min = 2.5  # 2.5%
        hull_rate_max = 4.0  # 4.0%
    elif total_score <= 50:
        risk_level = "中低风险 🟡"
        risk_desc = "AI快速核保，标准费率"
        hull_rate_min = 4.0
        hull_rate_max = 6.0
    elif total_score <= 75:
        risk_level = "中高风险 🟠"
        risk_desc = "需人工复核，附加条款"
        hull_rate_min = 6.0
        hull_rate_max = 10.0
    else:
        risk_level = "高风险 🔴"
        risk_desc = "建议转人工核保，可能拒保"
        hull_rate_min = 10.0
        hull_rate_max = 15.0

    # ---- 保费计算（机身险 % + 三者险 ‰）----
    hull_premium_min = round(hull_coverage * hull_rate_min / 100, 2)
    hull_premium_max = round(hull_coverage * hull_rate_max / 100, 2)

    tp_premium = round(third_party_limit * tp_rate / 1000, 2)

    total_premium_min = round(hull_premium_min + tp_premium, 2)
    total_premium_max = round(hull_premium_max + tp_premium, 2)

    # ---- 整体综合费率 ----
    total_value = hull_coverage + third_party_limit
    if total_value > 0:
        overall_rate_min = round(total_premium_min / total_value * 1000, 2)
        overall_rate_max = round(total_premium_max / total_value * 1000, 2)
    else:
        overall_rate_min = overall_rate_max = 0

    # ---- 缺失信息检测 ----
    missing_info = []
    if annual_hours <= 0:
        missing_info.append("年飞行小时数未填写，将使用默认值50小时估算")
    if battery_cycles <= 0 and drone_info["category"] in ("industrial", "agriculture", "cargo"):
        missing_info.append("建议补充电池循环次数，可优化费率")
    if previous_claims < 0:
        missing_info.append("历史出险记录未提供，按0次计算")
    if fleet_size <= 0:
        missing_info.append("机队数量未填写，按单机计算")

    return {
        "total_score": round(total_score, 1),
        "risk_level": risk_level,
        "risk_desc": risk_desc,
        "hull_rate_min_permille": hull_rate_min,
        "hull_rate_max_permille": hull_rate_max,
        "third_party_rate_permille": round(tp_rate, 2),
        "overall_rate_min_permille": overall_rate_min,
        "overall_rate_max_permille": overall_rate_max,
        "hull_premium_min_cny": hull_premium_min,
        "hull_premium_max_cny": hull_premium_max,
        "third_party_premium_cny": tp_premium,
        "total_premium_min_cny": total_premium_min,
        "total_premium_max_cny": total_premium_max,
        "factor_breakdown": {
            "设备风险": round(device_score + battery_risk + cargo_risk, 1),
            "使用场景": round(usage_score, 1),
            "飞行环境": round(env_score, 1),
            "操作员资质": round(pilot_score, 1),
            "飞行暴露量": round(exposure_score, 1),
            "历史理赔": round(claims_score, 1),
            "保额配置": round(coverage_score, 1),
            "三者险风险": round(tp_risk_score, 1),
            "机队折扣": round(fleet_discount, 1),
        },
        "missing_info": missing_info,
        "hull_insured_value": hull_coverage,
        "third_party_limit": third_party_limit,
        "fleet_size": fleet_size,
    }


def explain_risk_factors(result: dict) -> str:
    """生成中文化的风险因素说明"""
    factors = result["factor_breakdown"]
    sorted_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)
    lines = [f"**综合风险评分**: {result['total_score']}/100  {result['risk_level']}"]
    lines.append("")
    lines.append("**风险因子贡献排名:**")
    for name, score in sorted_factors:
        bar = "█" * int(score / 2) + "░" * (10 - int(score / 2))
        lines.append(f"  {bar}  {name}: {score}分")
    lines.append("")
    lines.append(f"**机身险费率**: {result['hull_rate_min_permille']}% - {result['hull_rate_max_permille']}%")
    lines.append(f"**三者险费率**: {result['third_party_rate_permille']}‰")
    lines.append(f"**综合费率**: {result['overall_rate_min_permille']}‰ - {result['overall_rate_max_permille']}‰")
    lines.append(f"**机身险保费**: ¥{result['hull_premium_min_cny']} - ¥{result['hull_premium_max_cny']}")
    lines.append(f"**三者险保费**: ¥{result['third_party_premium_cny']}")
    lines.append(f"**总保费**: ¥{result['total_premium_min_cny']} - ¥{result['total_premium_max_cny']}")
    lines.append(f"**核保结论**: {result['risk_desc']}")
    return "\n".join(lines)
