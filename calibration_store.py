"""
校准数据持久化存储
=================
SQLite 存储: 各维度权重修正因子、校准历史记录
透明运行，无用户可见痕迹
"""
import sqlite3, json, os, time
from pathlib import Path

DB_DIR = Path.home() / ".drone_insurance"
DB_PATH = DB_DIR / "calibration.db"

# 默认权重（与risk_engine.py一致）
DEFAULT_WEIGHTS = {
    "device_score": {"weight": 8, "adjustments": {}},
    "battery_risk": {"weight": 5, "adjustments": {}},
    "cargo_risk": {"weight": 4, "adjustments": {}},
    "airworthiness": {"weight": 8, "adjustments": {}},
    "obstacle_score": {"weight": 6, "adjustments": {}},
    "usage_score": {"weight": 12, "adjustments": {}},
    "bvlos_score": {"weight": 8, "adjustments": {}},
    "pilot_score": {"weight": 12, "adjustments": {}},
    "violation_score": {"weight": 6, "adjustments": {}},
    "env_score": {"weight": 7, "adjustments": {}},
    "exposure_score": {"weight": 6, "adjustments": {}},
    "claims_score": {"weight": 10, "adjustments": {}},
    "coverage_score": {"weight": 6, "adjustments": {}},
    "tp_risk_score": {"weight": 4, "adjustments": {}},
    "ph_risk_score": {"weight": 4, "adjustments": {}},
    "fleet_discount": {"weight": -4, "adjustments": {}},
}

# 维度特定修正因子（按具体值细调）
DIMENSION_CORRECTIONS = {
    "airworthiness": {},
    "obstacle_avoidance": {},
    "usage": {},
    "bvlos_mode": {},
    "pilot_level": {},
    "violation_record": {},
    "env_type": {},
    "policyholder_type": {},
    "drone_model": {},
}


def _init_db():
    """初始化数据库表结构"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS weight_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dimension TEXT NOT NULL,
            sub_key TEXT,
            correction REAL NOT NULL DEFAULT 0,
            sample_count INTEGER NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL,
            UNIQUE(dimension, sub_key)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calibration_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            policy_count INTEGER NOT NULL,
            claim_count INTEGER NOT NULL,
            avg_error REAL NOT NULL,
            loss_ratio REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def save_corrections(corrections: dict):
    """保存权重修正因子到数据库"""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    now = time.time()
    for dimension, subs in corrections.items():
        if isinstance(subs, dict):
            for sub_key, correction in subs.items():
                conn.execute("""
                    INSERT INTO weight_corrections (dimension, sub_key, correction, sample_count, updated_at)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(dimension, sub_key) DO UPDATE SET
                        correction = correction * 0.7 + ? * 0.3,
                        sample_count = sample_count + 1,
                        updated_at = ?
                """, (dimension, str(sub_key), correction, now, correction, now))
    conn.commit()
    conn.close()


def load_corrections() -> dict:
    """加载所有已学习的修正因子"""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT dimension, sub_key, correction FROM weight_corrections"
    ).fetchall()
    conn.close()
    corrections = {}
    for dim, sub_key, corr in rows:
        if dim not in corrections:
            corrections[dim] = {}
        corrections[dim][sub_key] = corr
    return corrections


def log_calibration(policy_count: int, claim_count: int, avg_error: float, loss_ratio: float):
    """记录校准日志"""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO calibration_log (timestamp, policy_count, claim_count, avg_error, loss_ratio) VALUES (?, ?, ?, ?, ?)",
        (time.time(), policy_count, claim_count, avg_error, loss_ratio)
    )
    conn.commit()
    conn.close()


def get_calibration_count() -> int:
    """获取累计校准次数（仅内部统计用）"""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    count = conn.execute("SELECT COUNT(*) FROM calibration_log").fetchone()[0]
    conn.close()
    return count


if __name__ == "__main__":
    # 测试
    _init_db()
    print(f"DB 已创建: {DB_PATH}")
    save_corrections({"usage": {"应急/消防": -0.05, "物流配送": 0.08}})
    print(f"修正因子: {load_corrections()}")
