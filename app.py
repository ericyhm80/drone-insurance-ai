"""
无人机保险 AI 投保引擎
=====================
晶世科保 · Vibe Marketing
2周MVP Demo — 展示"原来3天→现5分钟"的核保效率提升
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from risk_engine import (
    score_drone_risk, explain_risk_factors,
    DRONE_RISK_DB, USAGE_RISK_MAP, ENV_RISK_MAP, PILOT_LEVEL_MAP,
)
from data_flywheel import (
    record_inquiry, update_outcome, get_flywheel_stats, get_recent_inquiries,
)

# ── 页面配置 ──
st.set_page_config(
    page_title="无人机保险 AI 核保引擎",
    page_icon="🚁",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS 美化 ──
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #0A2F5E; margin-bottom: 0.5rem; }
    .sub-header { font-size: 1.1rem; color: #5A7A9A; margin-bottom: 1.5rem; }
    .risk-box { padding: 1.5rem; border-radius: 12px; margin: 1rem 0; }
    .risk-low { background: #E8F5E9; border-left: 5px solid #2E7D32; }
    .risk-mid-low { background: #FFF8E1; border-left: 5px solid #F57F17; }
    .risk-mid-high { background: #FFF3E0; border-left: 5px solid #E65100; }
    .risk-high { background: #FFEBEE; border-left: 5px solid #C62828; }
    .metric-box { background: #F0F4F8; padding: 1rem; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 1.8rem; font-weight: 700; color: #0A2F5E; }
    .metric-label { font-size: 0.85rem; color: #5A7A9A; }
    .footer { text-align: center; color: #999; font-size: 0.8rem; margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #eee; }
    .stButton button { background: #0A2F5E; color: white; border: none; padding: 0.5rem 2rem; font-weight: 600; }
    .stButton button:hover { background: #1A4F7E; }
    div[data-testid="stSidebar"] { background: #F7FAFC; }
    .badge { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .badge-blue { background: #E3F2FD; color: #1565C0; }
    .badge-green { background: #E8F5E9; color: #2E7D32; }
    .badge-orange { background: #FFF3E0; color: #E65100; }
</style>
""", unsafe_allow_html=True)

# ── 侧边栏 ──
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/null/drone.png", width=60)
    st.markdown("### 无人机保险 AI 引擎")
    st.markdown("**晶世科保**  ·  2周MVP原型")
    st.markdown("---")
    st.markdown("**核心流程**")
    st.markdown("1️⃣ 填写投保问卷\n\n2️⃣ AI引擎自动评估\n\n3️⃣ 输出风险评分+费率\n\n4️⃣ 记录数据飞轮")
    st.markdown("---")

    # 数据飞轮状态
    stats = get_flywheel_stats()
    st.markdown("**📊 数据飞轮状态**")
    col1, col2, col3 = st.columns(3)
    col1.metric("询价总数", stats["total_inquiries"])
    col2.metric("成交率", f"{stats['conversion_rate']}%")
    col3.metric("待跟踪", stats["pending_outcome"])

    st.markdown("---")
    st.caption("v0.1 · Phase 1 规则引擎 · 2026")

# ── 主页面 ──
st.markdown('<div class="main-header">🚁 无人机保险 AI 核保引擎</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">输入飞行信息 → AI即时评估 → 输出风险评分及建议费率</div>', unsafe_allow_html=True)

# ── Tab 布局 ──
tab1, tab2, tab3 = st.tabs(["📋 投保评估", "📊 数据飞轮", "ℹ️ 模型说明"])

# ════════════════════════════════════════════
# TAB 1: 投保评估
# ════════════════════════════════════════════
with tab1:
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("### 📝 投保信息")
        st.markdown("*所有字段均为投保评估所需，用于AI模型风险评分*")

        with st.form("insurance_form"):
            r1, r2 = st.columns(2)
            with r1:
                drone_model = st.selectbox(
                    "🛩️ 无人机型号",
                    options=list(DRONE_RISK_DB.keys()),
                    index=2,
                    help="选择无人机具体型号"
                )
            with r2:
                usage = st.selectbox(
                    "🎯 主要用途",
                    options=list(USAGE_RISK_MAP.keys()),
                    index=0,
                    help="使用场景影响风险因子"
                )

            r3, r4 = st.columns(2)
            with r3:
                annual_hours = st.number_input(
                    "⏱️ 年飞行小时数",
                    min_value=0, max_value=3000, value=100, step=10,
                    help="预估年度总飞行时长"
                )
            with r4:
                coverage_amount = st.number_input(
                    "💰 期望保额（元）",
                    min_value=10000, max_value=5000000, value=50000, step=5000,
                    help="机身险+第三方责任险合计保额"
                )

            r5, r6 = st.columns(2)
            with r5:
                pilot_level = st.selectbox(
                    "👨‍✈️ 操作员资质",
                    options=list(PILOT_LEVEL_MAP.keys()),
                    index=2,
                    help="CAAC/AOPA无人机驾驶员资质等级"
                )
            with r6:
                env_type = st.selectbox(
                    "🌍 主要飞行环境",
                    options=list(ENV_RISK_MAP.keys()),
                    index=1,
                    help="飞行环境直接影响第三方风险"
                )

            r7, r8 = st.columns(2)
            with r7:
                previous_claims = st.number_input(
                    "⚠️ 近3年出险次数",
                    min_value=0, max_value=20, value=0, step=1,
                )
            with r8:
                battery_cycles = st.number_input(
                    "🔋 电池循环次数",
                    min_value=0, max_value=500, value=50, step=10,
                    help="电池老化是无人机事故的重要因子"
                )

            submitted = st.form_submit_button("🚀 AI风险评分", use_container_width=True)

    with col_right:
        st.markdown("### 📋 填写提示")

        drone_info = DRONE_RISK_DB.get(drone_model, DRONE_RISK_DB["other_consumer"])
        st.info(
            f"**{drone_model}**  \n"
            f"类别: {drone_info['category']}  \n"
            f"参考售价: ¥{drone_info['base_price_cny']:,}  \n"
            f"基础事故率: {drone_info['crash_rate']*100:.1f}%"
        )

        usage_info = USAGE_RISK_MAP.get(usage, USAGE_RISK_MAP["其他"])
        st.caption(f"📎 {usage}: {usage_info['desc']}")

        env_info = ENV_RISK_MAP.get(env_type, ENV_RISK_MAP["城市郊区"])
        st.caption(f"📎 {env_type}: {env_info['desc']}")

        pilot_info = PILOT_LEVEL_MAP.get(pilot_level, PILOT_LEVEL_MAP["无证（需在飞手指导下操作）"])
        st.caption(f"📎 {pilot_level}: 风险系数 {pilot_info['factor']}x")

        st.markdown("---")
        st.markdown("**💡 影响因素**")
        st.caption("• 设备风险: 型号、机龄、电池状态")
        st.caption("• 操作风险: 资质、经验、飞行频次")
        st.caption("• 环境风险: 城市密度、天气、空域")
        st.caption("• 保额配置: 保额/设备价值比")

    # ── 评估结果 ──
    if submitted:
        st.markdown("---")
        st.markdown("## 📊 评估结果")

        result = score_drone_risk(
            drone_model=drone_model,
            usage=usage,
            annual_hours=annual_hours,
            pilot_level=pilot_level,
            env_type=env_type,
            coverage_amount=coverage_amount,
            previous_claims=previous_claims,
            battery_cycles=battery_cycles,
        )

        # 记录飞轮
        record_inquiry(
            drone_model=drone_model,
            usage=usage,
            annual_hours=annual_hours,
            pilot_level=pilot_level,
            env_type=env_type,
            coverage_amount=coverage_amount,
            risk_score=result["total_score"],
            risk_level=result["risk_level"],
            premium_min=result["premium_min_cny"],
            premium_max=result["premium_max_cny"],
        )

        # 三列核心指标
        r1, r2, r3, r4 = st.columns(4)
        risk_class = ""
        if result["total_score"] <= 25:
            risk_class = "risk-low"
        elif result["total_score"] <= 50:
            risk_class = "risk-mid-low"
        elif result["total_score"] <= 75:
            risk_class = "risk-mid-high"
        else:
            risk_class = "risk-high"

        with r1:
            st.markdown(f'<div class="metric-box"><div class="metric-value">{result["total_score"]}</div><div class="metric-label">风险评分 /100</div></div>', unsafe_allow_html=True)
        with r2:
            st.markdown(f'<div class="metric-box"><div class="metric-value">{result["risk_level"]}</div><div class="metric-label">风险等级</div></div>', unsafe_allow_html=True)
        with r3:
            st.markdown(f'<div class="metric-box"><div class="metric-value">¥{result["premium_min_cny"]:,.0f}</div><div class="metric-label">建议保费(低)</div></div>', unsafe_allow_html=True)
        with r4:
            st.markdown(f'<div class="metric-box"><div class="metric-value">¥{result["premium_max_cny"]:,.0f}</div><div class="metric-label">建议保费(高)</div></div>', unsafe_allow_html=True)

        # 风险详情框
        st.markdown(f"""
        <div class="risk-box {risk_class}">
            <strong>核保结论:</strong> {result['risk_desc']}<br>
            <strong>建议费率区间:</strong> {result['premium_rate_min_permille']}‰ - {result['premium_rate_max_permille']}‰<br>
            <strong>对应保费:</strong> ¥{result['premium_min_cny']:,.2f} - ¥{result['premium_max_cny']:,.2f}/年
        </div>
        """, unsafe_allow_html=True)

        # 风险因子分解
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**🔍 风险因子分解**")
            factors_df = pd.DataFrame([
                {"因子": k, "得分": v, "占比": f"{v/result['total_score']*100:.0f}%" if result['total_score'] > 0 else "N/A"}
                for k, v in result["factor_breakdown"].items()
            ])
            st.dataframe(factors_df, use_container_width=True, hide_index=True)

        with col_b:
            st.markdown("**📈 风险雷达**")
            st.markdown(
                explain_risk_factors(result).replace("\n", "  \n")
            )

        # 缺失信息提示
        if result["missing_info"]:
            st.warning("⚠️ **AI检测到以下信息缺失，补充后可优化评分精度:**")
            for msg in result["missing_info"]:
                st.caption(f"- {msg}")

        # 成交跟踪
        st.markdown("---")
        st.markdown("**📝 成交跟踪**（数据飞轮用，可选填）")
        c1, c2, c3 = st.columns(3)
        with c1:
            bought = st.selectbox("是否成交", ["", "是", "否（价格过高）", "否（被保司拒保）", "否（客户犹豫）", "否（找到其他渠道）"])
        with c2:
            actual_premium = st.number_input("实际成交保费", min_value=0, value=0, step=100)
        with c3:
            carrier = st.text_input("承保保司", placeholder="如：平安产险")

        if st.button("📊 记录成交结果", type="secondary"):
            bought_flag = "Y" if bought and "否" not in bought else ("N" if bought else "")
            reason = bought.replace("否（", "").replace("）", "") if bought and "否" in bought else ""
            st.success(f"✅ 已记录: {'成交' if bought_flag == 'Y' else ('未成交: ' + reason) if bought_flag == 'N' else '待跟踪'}")

    elif not submitted and st.session_state.get("form_submitted"):
        pass

# ════════════════════════════════════════════
# TAB 2: 数据飞轮
# ════════════════════════════════════════════
with tab2:
    st.markdown("### 📊 数据飞轮仪表盘")
    st.markdown("*数据飞轮是AI核心护城河——积累越多，定价越准，拒保率越低*")

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("询价总数", stats["total_inquiries"])
    col_b.metric("成交", stats["bought"])
    col_c.metric("未成交", stats["not_bought"])
    col_d.metric("成交转化率", f"{stats['conversion_rate']}%")

    st.markdown("---")
    st.markdown("**数据飞轮成长路径**")

    flywheel_phases = pd.DataFrame([
        {"阶段": "🚀 启动期", "数据量": "0-50条", "能力": "建立基础风险画像", "可做的": "了解客户分布、常用机型"},
        {"阶段": "⚡ 积累期", "数据量": "50-200条", "能力": "识别最优客户画像", "可做的": "优化投保问卷、匹配最佳保司"},
        {"阶段": "🔥 成型期", "数据量": "200-1000条", "能力": "拿数据找保司谈专属产品", "可做的": "用需求数据说服保司定制费率"},
        {"阶段": "🏆 飞轮期", "数据量": "1000+条", "能力": "AI模型替代规则引擎", "可做的": "接入DJI SDK实现动态实时定价"},
    ])
    st.dataframe(flywheel_phases, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("**最近询价记录**")
    recent = get_recent_inquiries(20)
    if recent:
        df_recent = pd.DataFrame(recent)
        display_cols = ["timestamp", "drone_model", "usage", "risk_score", "risk_level", "bought"]
        available = [c for c in display_cols if c in df_recent.columns]
        st.dataframe(df_recent[available].tail(10), use_container_width=True, hide_index=True)
    else:
        st.info("还没有询价记录。去「投保评估」Tab完成第一次评估吧！")

# ════════════════════════════════════════════
# TAB 3: 模型说明
# ════════════════════════════════════════════
with tab3:
    st.markdown("### 🧠 AI模型架构说明")

    st.markdown("""
    **当前版本: Phase 1 — 规则引擎**
    基于精算经验构建的评分卡，覆盖7大风险维度：

    | 维度 | 权重 | 数据来源 |
    |------|------|---------|
    | 设备风险 | ~15% | 型号数据库 + 电池状态 |
    | 使用场景 | ~16% | 投保人填写 |
    | 飞行环境 | ~13% | 投保人填写 |
    | 操作员资质 | ~25% | CAAC/AOPA等级 |
    | 飞行暴露量 | ~15% | 年飞行小时 |
    | 历史理赔 | ~20% | 保司系统/投保人自述 |
    | 保额配置 | ~12% | 保额/设备价值比 |

    **后续迭代路线:**

    | Phase | 时间 | 内容 |
    |-------|------|------|
    | **Phase 1** (当前) | 2周 | 规则引擎+评分卡，MVP验证流程 |
    | **Phase 2** | 1-2个月 | XGBoost替换规则，需要200+真实数据 |
    | **Phase 3** | 3-6个月 | 接DJI SDK遥测数据，实现动态实时费率 |
    | **Phase 4** | 6-12个月 | Tweedie GLM精算模型，监管合规定价 |
    """)

    st.markdown("---")
    st.markdown("""
    **数据飞轮逻辑**（引用 `business-opportunity-research-officer` 框架）:

    ```
    投保询价 → 收集6字段 → AI引擎初筛 → 保司报价
        ↑                                      ↓
    记录成交/拒保原因 ← 结果回传 ← 自动跟踪成交状态
        ↓
    路由优化：下次相似询价自动匹配最优保司
        ↓
    200条后：拿需求数据找保司谈专属费率
        ↓
    接遥测数据：实现"按次飞行实时定价"
    ```
    """)

    st.markdown("---")
    st.markdown("""
    **政策背景（2026年最新）**:

    - 🔴 **2026.01.01** 无人机"黑飞"正式入法
    - 🔴 **2026.02.13** 三部门：无人驾驶航空器责任保险**强制投保**
    - 🔴 **2026.03** 40余家险企已推出约**180款**低空保险产品
    - 🟢 **行业共识**：数据不通、风险复杂是最大障碍——**这正是AI的机会**
    """)

# ── Footer ──
st.markdown('<div class="footer">晶世科保 · 无人机保险AI引擎 v0.1 · 2周MVP原型 · 2026</div>', unsafe_allow_html=True)
