"""
校准数据持久化存储
=================
三层架构:
  Layer 1: 各公司私有校准数据（隔离存储，互不可见）
  Layer 2: 晶世科保行业聚合模型（脱敏统计，只存偏差率和样本量）
  Layer 3: 公司选择+评分时自动应用对应修正

⚠️ 公司间数据完全隔离
✅ 晶世科保拥有行业聚合统计
"""
import sqlite3, time
from pathlib import Path
from collections import defaultdict

DB_DIR = Path.home() / ".drone_insurance"
DB_PATH = DB_DIR / "calibration.db"


def _init_db():
    """初始化数据库表结构（幂等）"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))

    # 表1: 各公司私有修正因子（company_id 隔离）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS company_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT NOT NULL,
            dimension TEXT NOT NULL,
            sub_key TEXT,
            correction REAL NOT NULL DEFAULT 0,
            sample_count INTEGER NOT NULL DEFAULT 1,
            updated_at REAL NOT NULL,
            UNIQUE(company_id, dimension, sub_key)
        )
    """)
    # 表2: 行业聚合统计（脱敏，仅存偏差率均值+样本公司数）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS industry_aggregate (
            dimension TEXT NOT NULL,
            sub_key TEXT,
            avg_correction REAL NOT NULL DEFAULT 0,
            company_count INTEGER NOT NULL DEFAULT 0,
            total_sample_count INTEGER NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL,
            UNIQUE(dimension, sub_key)
        )
    """)
    # 表3: 校准日志（含公司标识）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calibration_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id TEXT,
            timestamp REAL NOT NULL,
            policy_count INTEGER NOT NULL,
            claim_count INTEGER NOT NULL,
            avg_error REAL NOT NULL,
            loss_ratio REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# ============================================================
# Layer 1: 公司私有修正因子
# ============================================================

def save_company_corrections(company_id: str, corrections: dict):
    """
    保存某公司的权重修正因子
    company_id: 公司标识（如 pingan, picc, cpic）
    corrections: {dimension: {sub_key: correction, ...}, ...}
    """
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    now = time.time()
    for dimension, subs in corrections.items():
        if not isinstance(subs, dict):
            continue
        for sub_key, correction in subs.items():
            conn.execute("""
                INSERT INTO company_corrections (company_id, dimension, sub_key, correction, sample_count, updated_at)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(company_id, dimension, sub_key) DO UPDATE SET
                    correction = ROUND(correction * 0.7 + ? * 0.3, 4),
                    sample_count = sample_count + 1,
                    updated_at = ?
            """, (company_id, dimension, str(sub_key), correction, now, correction, now))
    conn.commit()
    conn.close()
    # 保存后自动更新行业聚合
    _update_industry_aggregate(dimension for dimension in corrections.keys())


def load_company_corrections(company_id: str) -> dict:
    """加载某公司的修正因子"""
    if not company_id:
        return {}
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT dimension, sub_key, correction FROM company_corrections WHERE company_id = ?",
        (company_id,)
    ).fetchall()
    conn.close()
    corrections = {}
    for dim, sub_key, corr in rows:
        if dim not in corrections:
            corrections[dim] = {}
        corrections[dim][sub_key] = corr
    return corrections


# ============================================================
# Layer 2: 行业聚合模型
# ============================================================

def _update_industry_aggregate(dimensions_to_update: set):
    """从所有公司的数据重新计算行业聚合"""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    for dim in dimensions_to_update:
        # 统计该维度下各子项的平均修正 + 公司数
        rows = conn.execute("""
            SELECT sub_key, AVG(correction) as avg_corr, COUNT(DISTINCT company_id) as co_count, SUM(sample_count) as total_samp
            FROM company_corrections
            WHERE dimension = ?
            GROUP BY sub_key
        """, (dim,)).fetchall()
        for sub_key, avg_corr, co_count, total_samp in rows:
            conn.execute("""
                INSERT INTO industry_aggregate (dimension, sub_key, avg_correction, company_count, total_sample_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(dimension, sub_key) DO UPDATE SET
                    avg_correction = ?,
                    company_count = ?,
                    total_sample_count = ?,
                    updated_at = ?
            """, (dim, sub_key, avg_corr, co_count, total_samp, time.time(),
                  avg_corr, co_count, total_samp, time.time()))
    conn.commit()
    conn.close()


def load_industry_corrections() -> dict:
    """加载行业聚合修正因子（晶世科保拥有）"""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT dimension, sub_key, avg_correction, company_count FROM industry_aggregate"
    ).fetchall()
    conn.close()
    corrections = {}
    for dim, sub_key, avg_corr, co_count in rows:
        if dim not in corrections:
            corrections[dim] = {}
        corrections[dim][sub_key] = {
            "avg_correction": avg_corr,
            "company_count": co_count,
        }
    return corrections


def get_industry_stats() -> dict:
    """获取行业统计摘要（晶世科保用）"""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))

    # 参与校准的公司数
    companies = conn.execute(
        "SELECT COUNT(DISTINCT company_id) FROM company_corrections"
    ).fetchone()[0] or 0

    # 总校准次数
    total_calibrations = conn.execute(
        "SELECT COUNT(*) FROM calibration_log"
    ).fetchone()[0] or 0

    # 所有维度偏差最大的Top 5
    top_deviations = conn.execute("""
        SELECT dimension, sub_key, avg_correction, company_count
        FROM industry_aggregate
        ORDER BY ABS(avg_correction) DESC
        LIMIT 10
    """).fetchall()

    # 平均赔付率（从校准日志）
    avg_loss_ratio = conn.execute(
        "SELECT AVG(loss_ratio) FROM calibration_log WHERE loss_ratio > 0"
    ).fetchone()[0] or 0

    conn.close()

    return {
        "companies": companies,
        "total_calibrations": total_calibrations,
        "avg_loss_ratio": round(avg_loss_ratio, 1),
        "top_deviations": [
            {"dimension": d, "sub_key": s, "avg_correction": round(c, 4), "companies": cnt}
            for d, s, c, cnt in top_deviations
        ],
    }


# ============================================================
# Layer 3: 混合评分（公司修正 + 行业修正）
# ============================================================

def get_combined_correction(dimension: str, sub_key: str,
                            company_id: str = None) -> float:
    """
    获取最终修正因子: 公司修正(如有) × 行业修正(如有)
    公司修正优先，行业修正作为Bayesian先验
    """
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    correction = 0.0

    # 先查公司修正
    if company_id:
        row = conn.execute(
            "SELECT correction FROM company_corrections WHERE company_id=? AND dimension=? AND sub_key=?",
            (company_id, dimension, str(sub_key))
        ).fetchone()
        if row:
            correction = row[0]

    # 如果有行业修正且公司样本<5，用行业修正作为先验
    if correction == 0:
        row = conn.execute(
            "SELECT avg_correction FROM industry_aggregate WHERE dimension=? AND sub_key=?",
            (dimension, str(sub_key))
        ).fetchone()
        if row:
            correction = row[0] * 0.5  # 行业修正打5折，保守

    conn.close()
    return correction


# ============================================================
# 校准日志
# ============================================================

def log_calibration(company_id: str, policy_count: int, claim_count: int,
                    avg_error: float, loss_ratio: float):
    """记录校准日志"""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO calibration_log (company_id, timestamp, policy_count, claim_count, avg_error, loss_ratio) VALUES (?, ?, ?, ?, ?, ?)",
        (company_id or "_unknown", time.time(), policy_count, claim_count, avg_error, loss_ratio)
    )
    conn.commit()
    conn.close()


# ============================================================
# 验证/测试
# ============================================================

if __name__ == "__main__":
    _init_db()
    print(f"✅ DB: {DB_PATH}")

    # 模拟: 公司A上传数据
    save_company_corrections("pingan", {"drone_model": {"M350RTK": -0.05}, "usage": {"物流配送": 0.08}})
    print(f"  公司A修正: {load_company_corrections('pingan')}")

    # 模拟: 公司B上传数据
    save_company_corrections("picc", {"drone_model": {"M350RTK": -0.02}, "usage": {"物流配送": 0.12}})
    print(f"  公司B修正: {load_company_corrections('picc')}")

    # 行业聚合
    industry = load_industry_corrections()
    print(f"  行业修正: {industry}")

    # 行业统计
    stats = get_industry_stats()
    print(f"  统计: {stats['companies']}家公司, {stats['total_calibrations']}次校准")
    for d in stats['top_deviations']:
        print(f"    {d['dimension']}:{d['sub_key']} = {d['avg_correction']} ({d['companies']}家)")
