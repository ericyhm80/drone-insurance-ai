"""
行业风控数据看板
==============
从 accidents.json 提取事故数据，按原因归类、统计趋势。
只输出聚合统计和趋势结论，不展示具体新闻标题。
"""
import json, os, re
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


# 事故原因分类规则
CAUSE_RULES = [
    ("禁飞区/违规飞行", ["黑飞", "禁飞区", "违规飞行", "拘留", "罚款", "管制"]),
    ("操作失误", ["炸机", "失控", "坠落", "贴脸", "漂移", "操作不当"]),
    ("机械/技术故障", ["故障", "信号丢失", "电池", "电机"]),
    ("碰撞/第三方事故", ["撞", "伤人", "损物", "撞击"]),
    ("恶意/人为破坏", ["轻生", "焦虑", "恶意"]),
    ("其他/待分类", []),  # 兜底
]

CAUSE_COLORS = {
    "禁飞区/违规飞行": "#E53935",
    "操作失误": "#FB8C00",
    "机械/技术故障": "#FDD835",
    "碰撞/第三方事故": "#8E24AA",
    "恶意/人为破坏": "#D32F2F",
    "其他/待分类": "#9E9E9E",
}


def _classify_accident(title: str) -> str:
    """根据标题将事故归类"""
    for cause, keywords in CAUSE_RULES:
        if not keywords:
            continue
        if any(kw in title for kw in keywords):
            return cause
    return "其他/待分类"


def get_risk_dashboard() -> dict:
    """
    生成风控数据看板（仅聚合统计，不含具体新闻）
    """
    acc_path = os.path.join(DATA_DIR, "accidents.json")
    all_accidents = []
    if os.path.exists(acc_path):
        with open(acc_path, encoding="utf-8") as f:
            all_accidents = json.load(f)

    # 按原因分类统计
    cause_stats = {}
    for a in all_accidents:
        cause = _classify_accident(a.get("title", ""))
        cause_stats[cause] = cause_stats.get(cause, 0) + 1

    # 按来源统计
    source_stats = {}
    for a in all_accidents:
        src = a.get("source", "unknown")
        source_stats[src] = source_stats.get(src, 0) + 1

    # 计算占比
    total = len(all_accidents)
    cause_pct = {}
    for cause, count in cause_stats.items():
        cause_pct[cause] = {
            "count": count,
            "pct": round(count / total * 100, 0) if total > 0 else 0,
        }

    # 排序（数量降序）
    cause_ranking = sorted(cause_pct.items(), key=lambda x: -x[1]["count"])

    return {
        "total_accidents": total,
        "cause_ranking": [
            {"cause": c, "count": v["count"], "pct": v["pct"]}
            for c, v in cause_ranking
        ],
        "sources": source_stats,
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "data_period": "持续收集中",
    }


def get_data_coverage() -> dict:
    """返回数据覆盖范围（展示用）"""
    acc_path = os.path.join(DATA_DIR, "accidents.json")
    news_path = os.path.join(DATA_DIR, "industry_news.json")

    acc_count = 0
    news_count = 0
    if os.path.exists(acc_path):
        with open(acc_path, encoding="utf-8") as f:
            acc_count = len(json.load(f))
    if os.path.exists(news_path):
        with open(news_path, encoding="utf-8") as f:
            news_count = len(json.load(f))

    return {
        "事故案例": acc_count,
        "行业动态": news_count,
        "数据源": ["Google News", "CAAC官网(国内)", "百度新闻(国内)", "ccgp.gov.cn"],
    }
