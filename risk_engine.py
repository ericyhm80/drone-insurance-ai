"""
无人机保险AI核保引擎 - 风险评分与定价建议
=====================================
Phase 1: 规则引擎 + 简易评分卡
Phase 2: 替换为 XGBoost 模型
"""

DRONE_RISK_DB = {
    # 消费级
    "DJI Mini 4 Pro":   {"category": "consumer",   "base_price_cny": 8000,   "crash_rate": 0.08, "parts_cost": "low"},
    "DJI Air 3":        {"category": "consumer",   "base_price_cny": 12000,  "crash_rate": 0.06, "parts_cost": "low"},
    "DJI Mavic 3 Pro":  {"category": "prosumer",   "base_price_cny": 22000,  "crash_rate": 0.05, "parts_cost": "medium"},
    "DJI Mavic 4":      {"category": "prosumer",   "base_price_cny": 28000,  "crash_rate": 0.04, "parts_cost": "medium"},
    # 行业级
    "DJI Matrice 350 RTK": {"category": "industrial", "base_price_cny": 65000, "crash_rate": 0.03, "parts_cost": "high"},
    "DJI Matrice 4T":   {"category": "industrial", "base_price_cny": 55000,  "crash_rate": 0.03, "parts_cost": "high"},
    "DJI Agras T60":    {"category": "agriculture","base_price_cny": 60000,  "crash_rate": 0.04, "parts_cost": "high"},
    "Autel EVO Max 4T": {"category": "industrial", "base_price_cny": 50000,  "crash_rate": 0.04, "parts_cost": "high"},
    "Autel EVO Lite":   {"category": "consumer",   "base_price_cny": 10000,  "crash_rate": 0.07, "parts_cost": "low"},
    # 默认
    "other_consumer":   {"category": "consumer",   "base_price_cny": 15000,  "crash_rate": 0.07, "parts_cost": "medium"},
    "other_industrial": {"category": "industrial", "base_price_cny": 50000,  "crash_rate": 0.04, "parts_cost": "high"},
}

USAGE_RISK_MAP = {
    "航拍摄影":     {"base_factor": 0.8,  "desc": "低空慢速，风险最低"},
    "农业植保":     {"base_factor": 1.2,  "desc": "低空作业，环境复杂"},
    "物流配送":     {"base_factor": 1.5,  "desc": "城市低空，人流量大"},
    "巡检/测绘":    {"base_factor": 1.1,  "desc": "中等高度，任务明确"},
    "应急/消防":    {"base_factor": 1.3,  "desc": "高风险环境"},
    "教育培训":     {"base_factor": 0.9,  "desc": "受控环境"},
    "其他":         {"base_factor": 1.0,  "desc": "通用场景"},
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


def score_drone_risk(drone_model: str, usage: str, annual_hours: float,
                     pilot_level: str, env_type: str, coverage_amount: float,
                     previous_claims: int = 0, battery_cycles: int = 0) -> dict:
    """
    核心风险评估函数
    返回风险评分(0-100)、建议费率区间(‰)、详细因子分解
    """
    # ---- 1. 设备风险 ----
    drone_info = DRONE_RISK_DB.get(drone_model)
    if not drone_info:
        # 如果模型不在库里，按类别匹配
        if "agriculture" in usage.lower() or "植保" in usage:
            drone_info = DRONE_RISK_DB["DJI Agras T60"]
        elif "industrial" in str(drone_model).lower() or "行业" in str(drone_model).lower():
            drone_info = DRONE_RISK_DB["other_industrial"]
        else:
            drone_info = DRONE_RISK_DB["other_consumer"]

    device_score = drone_info["crash_rate"] * 100  # 0-10分

    # 电池老化风险
    battery_risk = min(battery_cycles / 200, 1.0) * 5  # 0-5分

    # ---- 2. 使用场景风险 ----
    usage_info = USAGE_RISK_MAP.get(usage, USAGE_RISK_MAP["其他"])
    usage_score = (usage_info["base_factor"] - 0.7) * 20  # 0-16分

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
        exposure_score = 12  # 年飞行超500小时，暴露量高
    exposure_score = min(exposure_score, 15)

    # ---- 6. 历史理赔 ----
    claims_score = min(previous_claims * 8, 20)

    # ---- 7. 保额与设备价值比 ----
    value_ratio = coverage_amount / drone_info["base_price_cny"]
    if value_ratio < 0.5:
        coverage_score = 2  # 不足额投保
    elif value_ratio < 1.0:
        coverage_score = 5  # 常规保额
    elif value_ratio < 1.5:
        coverage_score = 8  # 偏高保额
    else:
        coverage_score = 12  # 超额投保
    coverage_score = min(coverage_score, 12)

    # ---- 综合评分 ----
    raw_score = (device_score + battery_risk + usage_score + env_score +
                 pilot_score + exposure_score + claims_score + coverage_score)

    # 归一化到0-100
    total_score = min(raw_score, 100)

    # ---- 风险等级 ----
    if total_score <= 25:
        risk_level = "低风险 🟢"
        risk_desc = "AI自动承保，费率优惠"
        premium_rate_min = 0.3
        premium_rate_max = 0.6
    elif total_score <= 50:
        risk_level = "中低风险 🟡"
        risk_desc = "AI快速核保，标准费率"
        premium_rate_min = 0.6
        premium_rate_max = 1.2
    elif total_score <= 75:
        risk_level = "中高风险 🟠"
        risk_desc = "需人工复核，附加条款"
        premium_rate_min = 1.2
        premium_rate_max = 2.5
    else:
        risk_level = "高风险 🔴"
        risk_desc = "建议转人工核保，可能拒保"
        premium_rate_min = 2.5
        premium_rate_max = 5.0

    # ---- 建议保费 ----
    premium_min = round(coverage_amount * premium_rate_min / 1000, 2)
    premium_max = round(coverage_amount * premium_rate_max / 1000, 2)

    # ---- 缺失信息检测 ----
    missing_info = []
    if annual_hours <= 0:
        missing_info.append("年飞行小时数未填写，将使用默认值50小时估算")
    if battery_cycles <= 0 and drone_info["category"] in ("industrial", "agriculture"):
        missing_info.append("建议补充电池循环次数，可优化费率")
    if previous_claims < 0:
        missing_info.append("历史出险记录未提供，按0次计算")

    return {
        "total_score": round(total_score, 1),
        "risk_level": risk_level,
        "risk_desc": risk_desc,
        "premium_rate_min_permille": premium_rate_min,
        "premium_rate_max_permille": premium_rate_max,
        "premium_min_cny": premium_min,
        "premium_max_cny": premium_max,
        "factor_breakdown": {
            "设备风险": round(device_score + battery_risk, 1),
            "使用场景": round(usage_score, 1),
            "飞行环境": round(env_score, 1),
            "操作员资质": round(pilot_score, 1),
            "飞行暴露量": round(exposure_score, 1),
            "历史理赔": round(claims_score, 1),
            "保额配置": round(coverage_score, 1),
        },
        "missing_info": missing_info,
        "drone_insured_value": coverage_amount,
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
    lines.append(f"**建议费率**: {result['premium_rate_min_permille']}‰ - {result['premium_rate_max_permille']}‰")
    lines.append(f"**建议保费**: ¥{result['premium_min_cny']} - ¥{result['premium_max_cny']}")
    lines.append(f"**核保结论**: {result['risk_desc']}")
    return "\n".join(lines)
