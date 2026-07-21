"""
晶世科保行业聚合统计查询
======================
私密命令行工具，仅你可见。

用法:
  python3 industry_stats.py

输出:
  - 参与校准的用户数（匿名）
  - 累计校准次数
  - 市场平均赔付率
  - 偏差最大的维度Top 10
"""
import sys
sys.path.insert(0, ".")

from calibration_store import get_industry_stats

stats = get_industry_stats()

print("=" * 55)
print("  晶世科保 · 行业聚合统计")
print("=" * 55)
print(f"  参与校准的用户: {stats['companies']} (匿名)")
print(f"  累计校准次数:   {stats['total_calibrations']}")
print(f"  市场平均赔付率: {stats['avg_loss_ratio']}%")
print()

if stats["top_deviations"]:
    print("  偏差最大的维度（跨用户聚合）:")
    print(f"  {'维度':<30} {'偏差':>8} {'用户数':>6}")
    print(f"  {'-'*30} {'-'*8} {'-'*6}")
    for d in stats["top_deviations"]:
        direction = "🔺" if d["avg_correction"] > 0 else "🔻"
        deviation = f"{abs(d['avg_correction'])*100:.1f}%"
        label = f"{d['dimension']}:{d['sub_key']}"[:28]
        print(f"  {direction} {label:<28} {deviation:>8} {d['companies']:>5}家")
else:
    print("  暂无校准数据")

print("=" * 55)
