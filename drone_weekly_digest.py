"""
每周行业动态简报
==============
从 accidents.json 和 industry_news.json 提取最新内容，
生成供核保参考的周报数据
"""
import json, os
from datetime import datetime, timedelta

DATA_DIR = os.path.expanduser("~/.drone_insurance")


def get_weekly_digest() -> dict:
    """获取最近7天的行业动态简报"""
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    accidents = []
    news = []

    # 加载事故库
    acc_path = os.path.join(DATA_DIR, "accidents.json")
    if os.path.exists(acc_path):
        with open(acc_path, encoding="utf-8") as f:
            all_acc = json.load(f)
        for a in all_acc:
            try:
                date_str = a.get("date", "")
                # Google News日期格式: Thu, 02 Jul 2026
                if "202" in date_str:
                    d = datetime.strptime(date_str.strip()[:16], "%a, %d %b %Y")
                    if d > week_ago:
                        accidents.append(a)
            except:
                pass

    # 加载行业动态
    news_path = os.path.join(DATA_DIR, "industry_news.json")
    if os.path.exists(news_path):
        with open(news_path, encoding="utf-8") as f:
            all_news = json.load(f)
        for n in all_news[-15:]:  # 最近15条
            news.append(n)

    return {
        "accidents": accidents[-5:],  # 最多5条事故
        "news": news[-8:],            # 最多8条行业动态
        "total_accidents": len(accidents),
        "total_news": len(news),
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
    }
