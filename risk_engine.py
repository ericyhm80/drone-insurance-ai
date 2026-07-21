"""
无人机保险AI核保引擎 - 风险评分与定价建议 v0.8
=====================================
基于行业标准重构（参考来源: 平安产险四级风险体系、
中再产险×平安UBI产品、Munich Re/Allianz/AIG核保框架、
CAAC《无人驾驶航空器飞行管理暂行条例》）

修订内容：
  - 新增: 适航认证、避障能力、BVLOS运行类型、违规飞行记录
  - 删除: 运营年限(与投保人类型冗余)、行业风险(合并到使用场景)
  - 新增: 拒保条件（无认证/严重违规直接拒保）
  - 权重: 按行业标准重新分配
"""

import math

# ============================================================
# 机型数据库
# ============================================================
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

# ============================================================
# 使用场景风险（合并原行业风险因子）
# ============================================================
USAGE_RISK_MAP = {
    "航拍摄影":              {"base_factor": 0.8,  "desc": "低空慢速，风险最低"},
    "农业植保":              {"base_factor": 1.2,  "desc": "低空作业，环境复杂"},
    "物流配送":              {"base_factor": 1.5,  "desc": "城市低空，人流量大"},
    "巡检/测绘":             {"base_factor": 1.1,  "desc": "中等高度，任务明确"},
    "应急/消防":             {"base_factor": 1.3,  "desc": "高风险消防/救援任务"},
    "应急/公共安全":          {"base_factor": 1.4,  "desc": "警务任务，环境不可控"},
    "警用侦查/监控":         {"base_factor": 1.3,  "desc": "城市低空侦查，频次高"},
    "运载/物资投送":         {"base_factor": 1.6,  "desc": "载重飞行，坠毁损失大"},
    "教育培训":              {"base_factor": 0.9,  "desc": "受控环境"},
    "其他":                  {"base_factor": 1.0,  "desc": "通用场景"},
}

# ============================================================
# 飞行环境风险
# ============================================================
ENV_RISK_MAP = {
    "城市密集区":  {"factor": 1.4, "desc": "人车密集，第三方风险高"},
    "城市郊区":    {"factor": 1.1, "desc": "人口密度中等"},
    "野外/农村":   {"factor": 0.8, "desc": "人员稀少，碰撞风险低"},
    "工业厂区":    {"factor": 1.2, "desc": "设备密集，电磁干扰"},
    "水域/海岸":   {"factor": 1.3, "desc": "坠落回收困难"},
    "室内":        {"factor": 0.7, "desc": "受控环境"},
}

# ============================================================
# 飞行员资质
# ============================================================
PILOT_LEVEL_MAP = {
    "无证（需在飞手指导下操作）": {"factor": 1.6, "min_hours": 0},
    "CAAC视距内驾驶员":            {"factor": 1.2, "min_hours": 50},
    "CAAC超视距驾驶员（机长）":    {"factor": 1.0, "min_hours": 100},
    "CAAC教员":                    {"factor": 0.8, "min_hours": 200},
    "AOPA合格证":                  {"factor": 1.3, "min_hours": 30},
}

# ============================================================
# 三者险费率基准
# ============================================================
THIRD_PARTY_RATE_MAP = {
    500000:  0.35,    # 50万
    1000000: 0.45,    # 100万
    2000000: 0.55,    # 200万（消防标书基准）
    5000000: 0.70,    # 500万
    10000000: 0.85,   # 1000万
}

# ============================================================
# 投保人类型
# ============================================================
POLICYHOLDER_TYPE_MAP = {
    "政府/事业单位":  {"factor": 0.8,  "desc": "管理规范，合规性强"},
    "国有企业":       {"factor": 0.9,  "desc": "制度完善，风险意识好"},
    "大型民营企业":   {"factor": 1.0,  "desc": "运营标准化，中等风险"},
    "中小微企业":     {"factor": 1.2,  "desc": "管理松散，风险不一"},
    "个人/个体飞手":  {"factor": 1.3,  "desc": "安全意识参差不齐"},
}

# ============================================================
# <<< 新增: 适航认证 >>
# 参考: Munich Re要求EASA/FAA认证; Allianz认证机型损失率低40-60%
# ============================================================
AIRWORTHINESS_MAP = {
    "有CAAC适航认证（TC/PC）": {"factor": 1.0, "desc": "认证机型，风险可控"},
    "有国外适航认证（FAA/EASA）": {"factor": 1.1, "desc": "国外认证，需CAAC认可"},
    "无认证（自组装/开源飞控）":  {"factor": 2.5, "desc": "不可靠，建议拒保"},
    "不适用（消费级/轻型）":    {"factor": 1.0, "desc": "法规豁免，正常核保"},
}

# ============================================================
# <<< 新增: 避障能力 >>
# 参考: Ping An评级★★★★; Allianz列为重要因子
# ============================================================
OBSTACLE_AVOIDANCE_MAP = {
    "全向避障（6向+）": {"factor": 0.8,  "desc": "最优，费率折扣"},
    "前/后/下三向避障":  {"factor": 0.9,  "desc": "良好，标准费率"},
    "仅前向避障":        {"factor": 1.1,  "desc": "有限，加费"},
    "无避障":            {"factor": 1.3,  "desc": "高风险，显著加费"},
}

# ============================================================
# <<< 新增: BVLOS运行类型 >>
# 参考: Ping An评分★★★★★; Allianz: BVLOS加费50-100%
# ============================================================
BVLOS_MAP = {
    "VLOS（视距内飞行）": {"factor": 1.0, "desc": "目视范围内，风险可控"},
    "BVLOS（超视距飞行）": {"factor": 1.6, "desc": "超视距，风险高，需额外审批"},
    "BVLOS（超视距+城市上空）": {"factor": 2.0, "desc": "高风险组合，建议再保"},
}

# ============================================================
# <<< 新增: 违规飞行记录 >>
# 参考: Allianz: 有违规加费50%+; Ping An: 关键因子
# ============================================================
VIOLATION_MAP = {
    "无违规记录":   {"factor": 1.0, "desc": "合规良好"},
    "有轻微违规":    {"factor": 1.3, "desc": "如超区域飞行警告，加费"},
    "有严重违规":    {"factor": 2.0, "desc": "如黑飞/禁飞区飞行，建议拒保"},
}


def score_drone_risk(drone_model: str, usage: str, annual_hours: float,
                     pilot_level: str, env_type: str, hull_coverage: float,
                     third_party_limit: float = 2000000,
                     previous_claims: int = 0, battery_cycles: int = 0,
                     fleet_size: int = 1,
                     policyholder_type: str = "国有企业",
                     # 新增参数
                     airworthiness: str = "不适用（消费级/轻型）",
                     obstacle_avoidance: str = "前/后/下三向避障",
                     bvlos_mode: str = "VLOS（视距内飞行）",
                     violation_record: str = "无违规记录",
                     ) -> dict:
    """
    核心风险评估函数 v0.8
    基于行业标准: 平安产险四级风险体系 + Munich Re/Allianz核保框架

    新增维度:
      - 适航认证（无认证→拒保）
      - 避障能力（全向避障→费率折扣）
      - BVLOS超视距（BVLOS→加费50%+）
      - 违规记录（有严重违规→拒保）

    删除维度:
      - 运营年限（与投保人类型冗余）
      - 行业风险（合并到使用场景中）
    """
    # ---- 机型数据 ----
    drone_info = DRONE_RISK_DB.get(drone_model)
    if not drone_info:
        if "agriculture" in usage or "植保" in usage:
            drone_info = DRONE_RISK_DB["DJI Agras T60"]
        elif "运载" in usage or "cargo" in str(drone_model).lower():
            drone_info = DRONE_RISK_DB["DJI FlyCart 30"]
        elif "industrial" in str(drone_model).lower() or "行业" in str(drone_model):
            drone_info = DRONE_RISK_DB["other_industrial"]
        else:
            drone_info = DRONE_RISK_DB["other_consumer"]

    # ============================================================
    # 拒保条件（Gate: 先判断是否可承保）
    # ============================================================
    rejection_reasons = []

    # 适航认证检查
    aw_info = AIRWORTHINESS_MAP.get(airworthiness, AIRWORTHINESS_MAP["不适用（消费级/轻型）"])
    if airworthiness == "无认证（自组装/开源飞控）":
        rejection_reasons.append("飞行器无适航认证，不符合行业承保最低准入要求（参考Munich Re核保标准）")

    # 违规记录检查
    vio_info = VIOLATION_MAP.get(violation_record, VIOLATION_MAP["无违规记录"])
    if violation_record == "有严重违规":
        rejection_reasons.append("存在严重违规飞行记录（禁飞区飞行/黑飞），依据行业标准拒绝承保")

    # 无证飞手检查
    if pilot_level == "无证（需在飞手指导下操作）" and drone_info["category"] != "consumer":
        rejection_reasons.append("操作行业级/运载级无人机需持CAAC执照，无证操作不符合承保条件")

    # 如果触发拒保条件，直接返回拒保结果
    if rejection_reasons:
        return {
            "total_score": 100,
            "risk_level": "拒绝承保 🔴",
            "risk_desc": "; ".join(rejection_reasons),
            "hull_rate_min_permille": 0,
            "hull_rate_max_permille": 0,
            "third_party_rate_permille": 0,
            "overall_rate_min_permille": 0,
            "overall_rate_max_permille": 0,
            "hull_premium_min_cny": 0,
            "hull_premium_max_cny": 0,
            "third_party_premium_cny": 0,
            "total_premium_min_cny": 0,
            "total_premium_max_cny": 0,
            "rejected": True,
            "rejection_reasons": rejection_reasons,
            "factor_breakdown": {},
        }

    # ============================================================
    # 一级: 飞行器因素（权重约35%）
    # ============================================================
    # 1. 设备基础风险
    device_score = drone_info["crash_rate"] * 100  # 0-8分

    # 2. 电池老化风险
    battery_risk = min(battery_cycles / 200, 1.0) * 5  # 0-5分

    # 3. 运载额外风险
    cargo_risk = 4 if drone_info["category"] == "cargo" else 0

    # 4. <<< 新增: 适航认证风险 >>>
    airworthiness_score = (aw_info["factor"] - 0.8) * 8  # 1.0→1.6分, 2.5→13.6分

    # 5. <<< 新增: 避障能力风险 >>>
    oa_info = OBSTACLE_AVOIDANCE_MAP.get(obstacle_avoidance, OBSTACLE_AVOIDANCE_MAP["前/后/下三向避障"])
    obstacle_score = (oa_info["factor"] - 0.6) * 8  # 0.8→1.6, 1.3→5.6

    # ============================================================
    # 二级: 运行场景因素（权重约30%）
    # ============================================================
    # 6. 使用场景风险（已合并原行业风险）
    usage_info = USAGE_RISK_MAP.get(usage, USAGE_RISK_MAP["其他"])
    usage_score = (usage_info["base_factor"] - 0.6) * 15  # 0-15分

    # 7. <<< 新增: BVLOS超视距风险 >>>
    bv_info = BVLOS_MAP.get(bvlos_mode, BVLOS_MAP["VLOS（视距内飞行）"])
    bvlos_score = (bv_info["factor"] - 0.8) * 10  # 1.0→2分, 1.6→8分, 2.0→12分

    # ============================================================
    # 三级: 飞行员因素（权重约20%）
    # ============================================================
    # 8. 操作员资质
    pilot_info = PILOT_LEVEL_MAP.get(pilot_level, PILOT_LEVEL_MAP["无证（需在飞手指导下操作）"])
    pilot_score = (pilot_info["factor"] - 0.6) * 15  # 0-15分

    # 9. <<< 新增: 违规飞行记录 >>>
    violation_score = (vio_info["factor"] - 0.8) * 8  # 1.0→1.6, 1.3→4, 2.0→9.6

    # ============================================================
    # 四级: 外部环境因素（权重约15%）
    # ============================================================
    # 10. 飞行环境
    env_info = ENV_RISK_MAP.get(env_type, ENV_RISK_MAP["城市郊区"])
    env_score = (env_info["factor"] - 0.5) * 10  # 0-9分

    # 11. 飞行暴露量
    if annual_hours < 50:
        exposure_score = 2
    elif annual_hours < 200:
        exposure_score = 5
    elif annual_hours < 500:
        exposure_score = 8
    else:
        exposure_score = 12

    # ============================================================
    # 其他因素
    # ============================================================
    # 12. 历史理赔
    claims_score = min(previous_claims * 8, 18)

    # 13. 保额配置
    value_ratio = hull_coverage / drone_info["base_price_cny"]
    if value_ratio < 0.5:
        coverage_score = 2
    elif value_ratio < 1.0:
        coverage_score = 5
    elif value_ratio < 1.5:
        coverage_score = 8
    else:
        coverage_score = 10

    # 14. 三者险风险
    tp_rate = THIRD_PARTY_RATE_MAP.get(third_party_limit, 0.55)
    tp_risk_score = min(tp_rate * 8, 6)

    # 15. 投保人类型
    ph_info = POLICYHOLDER_TYPE_MAP.get(policyholder_type, POLICYHOLDER_TYPE_MAP["国有企业"])
    ph_risk_score = (ph_info["factor"] - 0.6) * 6  # 0-4.2分

    # 16. 机队批量折扣
    fleet_discount = max(0, (fleet_size - 1) * 0.5)
    fleet_discount = min(fleet_discount, 5)

    # ============================================================
    # 综合评分
    # ============================================================
    raw_score = (device_score + battery_risk + cargo_risk +
                 airworthiness_score + obstacle_score +
                 usage_score + bvlos_score +
                 pilot_score + violation_score +
                 env_score + exposure_score +
                 claims_score + coverage_score +
                 tp_risk_score + ph_risk_score -
                 fleet_discount)

    total_score = max(0, min(raw_score, 100))

    # ============================================================
    # 风险等级 & 费率
    # ============================================================
    if total_score <= 20:
        risk_level = "低风险 🟢"
        risk_desc = "AI自动承保，费率优惠"
        hull_rate_min = 2.5
        hull_rate_max = 4.0
    elif total_score <= 40:
        risk_level = "中低风险 🟡"
        risk_desc = "AI快速核保，标准费率"
        hull_rate_min = 4.0
        hull_rate_max = 6.0
    elif total_score <= 60:
        risk_level = "中高风险 🟠"
        risk_desc = "需人工复核，附加条款"
        hull_rate_min = 6.0
        hull_rate_max = 10.0
    elif total_score <= 80:
        risk_level = "高风险 🔴"
        risk_desc = "建议转人工核保，可能拒保"
        hull_rate_min = 10.0
        hull_rate_max = 14.0
    else:
        risk_level = "极高风险 ⚠️"
        risk_desc = "拒保建议，请联系再保"
        hull_rate_min = 14.0
        hull_rate_max = 18.0

    # ---- 保费计算 ----
    hull_premium_min = round(hull_coverage * hull_rate_min / 100, 2)
    hull_premium_max = round(hull_coverage * hull_rate_max / 100, 2)
    tp_premium = round(third_party_limit * tp_rate / 1000, 2)
    total_premium_min = round(hull_premium_min + tp_premium, 2)
    total_premium_max = round(hull_premium_max + tp_premium, 2)

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
        "rejected": False,
        "rejection_reasons": [],
        "factor_breakdown": {
            "设备基础风险": round(device_score, 1),
            "电池老化": round(battery_risk, 1),
            "运载额外风险": round(cargo_risk, 1),
            "适航认证": round(airworthiness_score, 1),
            "避障能力": round(obstacle_score, 1),
            "使用场景": round(usage_score, 1),
            "超视距(BVLOS)": round(bvlos_score, 1),
            "操作员资质": round(pilot_score, 1),
            "违规记录": round(violation_score, 1),
            "飞行环境": round(env_score, 1),
            "飞行暴露量": round(exposure_score, 1),
            "历史理赔": round(claims_score, 1),
            "保额配置": round(coverage_score, 1),
            "三者险风险": round(tp_risk_score, 1),
            "投保人类型": round(ph_risk_score, 1),
            "机队折扣": round(fleet_discount, 1),
        },
        "missing_info": missing_info,
        "hull_insured_value": hull_coverage,
        "third_party_limit": third_party_limit,
        "fleet_size": fleet_size,
        "policyholder_type": ph_info["desc"],
        "reference_standard": "基于平安产险四级风险体系 + Munich Re/Allianz核保框架修订 v0.8",
    }


def explain_risk_factors(result: dict) -> str:
    """生成中文化的风险因素说明"""
    if result.get("rejected"):
        lines = [f"**❌ 拒绝承保**"]
        lines.append(f"**综合风险评分**: {result['total_score']}/100  {result['risk_level']}")
        lines.append("")
        lines.append("**拒保原因:**")
        for r in result.get("rejection_reasons", []):
            lines.append(f"  - {r}")
        lines.append("")
        lines.append("**建议:** 解决上述问题后重新提交评估")
        return "\n".join(lines)

    factors = result["factor_breakdown"]
    sorted_factors = sorted(factors.items(), key=lambda x: x[1], reverse=True)
    lines = [f"**综合风险评分**: {result['total_score']}/100  {result['risk_level']}"]
    lines.append(f"**参考标准**: {result.get('reference_standard', '规则引擎')}")
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
