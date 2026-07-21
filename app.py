"""
无人机保险 AI 投保引擎
=====================
晶世科保 · Vibe Marketing
v0.3 — 基于ccgp.gov.cn政府采购数据校准 + 每周自动巡检
"""

import streamlit as st
import pandas as pd

from risk_engine import (
    score_drone_risk, explain_risk_factors,
    DRONE_RISK_DB, USAGE_RISK_MAP, ENV_RISK_MAP, PILOT_LEVEL_MAP, THIRD_PARTY_RATE_MAP,
    POLICYHOLDER_TYPE_MAP,
    AIRWORTHINESS_MAP, OBSTACLE_AVOIDANCE_MAP, BVLOS_MAP, VIOLATION_MAP,
)
from qcc_client import verify_company, extract_risk_score
from data_flywheel import (
    record_inquiry, get_flywheel_stats, get_recent_inquiries,
)
from data_importer import (
    parse_policy_csv, parse_claims_csv, read_uploaded_file,
)

st.set_page_config(page_title="无人机保险 AI 核保引擎", page_icon="🚁", layout="wide")

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
    .stButton button { background: #0A2F5E; color: white; border: none; padding: 0.5rem 2rem; font-weight: 600; }
    .stButton button:hover { background: #1A4F7E; }
    div[data-testid="stSidebar"] { background: #F7FAFC; }
    .badge { display: inline-block; padding: 0.15rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
    .badge-blue { background: #E3F2FD; color: #1565C0; }
    .badge-green { background: #E8F5E9; color: #2E7D32; }
    .badge-orange { background: #FFF3E0; color: #E65100; }
    .calibration-note { background: #E3F2FD; padding: 0.8rem 1rem; border-radius: 8px; font-size: 0.85rem; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/null/drone.png", width=60)
    st.markdown("### 无人机保险 AI 引擎")
    st.markdown("**晶世科保** · v0.3")
    st.markdown("---")
    st.markdown("**核心流程**")
    st.markdown("1️⃣ 填写投保问卷\n\n2️⃣ AI引擎自动评估\n\n3️⃣ 输出机身险+三者险报价\n\n4️⃣ 记录数据飞轮")
    st.markdown("---")
    stats = get_flywheel_stats()
    st.markdown("**📊 数据飞轮状态**")
    col1, col2 = st.columns(2)
    col1.metric("询价总数", stats["total_inquiries"])
    col2.metric("成交率", f"{stats['conversion_rate']}%")
    st.markdown("---")
    st.caption("📊 费率基准: 上海消防特勤支队2026标书(ccgp.gov.cn)")
    st.caption("🔄 每周自动巡检政府采购网，定价持续更新")

st.markdown('<div class="main-header">🚁 无人机保险 AI 核保引擎</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">输入飞行信息 → AI即时评估 → 输出机身险+三者险报价</div>', unsafe_allow_html=True)

st.markdown("""
<div class="calibration-note">
📌 <strong>v0.2 费率校准说明</strong><br>
• 基准标书: 上海消防救援总队特勤支队2026年无人机保险采购 
  (<a href="https://www.ccgp.gov.cn/cggg/zygg/qtgg/202604/t20260430_26490816.htm" target="_blank">ccgp.gov.cn</a>)<br>
• 预算¥180,000 / 16架无人机 + 镜头 + 三者险≥200万 / 综合费率≈0.55%<br>
• 补充数据源: DJI Care Refresh官方定价、ccgp.gov.cn公告列表10页<br>
• 🔄 <strong>每周自动巡检</strong>中国政府采购网，有新标书上线时更新费率模型
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["📋 投保评估", "📊 数据飞轮", "ℹ️ 模型说明", "📥 数据校准"])

with tab1:
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("### 📝 投保信息")

        with st.expander("🏢 投保人信息", expanded=True):
            ph_col1, ph_col2 = st.columns(2)
            with ph_col1:
                policyholder_type = st.selectbox(
                    "投保人类型",
                    options=list(POLICYHOLDER_TYPE_MAP.keys()),
                    index=0,
                    help="投保人主体类型影响风险评估"
                )
                company_name = st.text_input(
                    "企业名称（可选）",
                    placeholder="输入企业全称用于企查查核验",
                    help="填写后将通过企查查API自动核验企业风险"
                )
            with ph_col2:
                airworthiness = st.selectbox(
                    "🏭 适航认证",
                    options=list(AIRWORTHINESS_MAP.keys()),
                    index=3,
                    help="无认证的自组装无人机直接拒保"
                )
                credit_code = st.text_input(
                    "统一社会信用代码（可选）",
                    placeholder="18位信用代码",
                    max_chars=18,
                    help="填写后可通过企查查查询企业信用报告"
                )
            r_new1, r_new2 = st.columns(2)
            with r_new1:
                obstacle_avoidance = st.selectbox(
                    "🛡️ 避障能力",
                    options=list(OBSTACLE_AVOIDANCE_MAP.keys()),
                    index=1,
                    help="全向避障可获费率折扣"
                )
            with r_new2:
                bvlos_mode = st.selectbox(
                    "📡 运行类型",
                    options=list(BVLOS_MAP.keys()),
                    index=0,
                    help="BVLOS超视距飞行需加费50-100%"
                )
            violation_record = st.selectbox(
                "⚠️ 违规飞行记录",
                options=list(VIOLATION_MAP.keys()),
                index=0,
                help="有严重违规记录（如黑飞）直接拒保"
            )

        st.markdown("---")
        with st.form("insurance_form"):
            r1, r2 = st.columns(2)
            with r1:
                drone_model = st.selectbox(
                    "🛩️ 无人机型号",
                    options=[m for m in DRONE_RISK_DB.keys() if not m.startswith("other_")],
                    index=8,  # M350RTK
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
                    "⏱️ 年飞行小时数", min_value=0, max_value=3000, value=100, step=10)
            with r4:
                hull_coverage = st.number_input(
                    "💰 机身险保额（元）", min_value=10000, max_value=5000000, value=50000, step=5000)

            r5, r6 = st.columns(2)
            with r5:
                pilot_level = st.selectbox(
                    "👨‍✈️ 操作员资质", options=list(PILOT_LEVEL_MAP.keys()), index=2)
            with r6:
                env_type = st.selectbox(
                    "🌍 主要飞行环境", options=list(ENV_RISK_MAP.keys()), index=1)

            r7, r8 = st.columns(2)
            with r7:
                third_party_limit = st.selectbox(
                    "🛡️ 三者险单机保额",
                    options=[500000, 1000000, 2000000, 5000000, 10000000],
                    format_func=lambda x: f"{x//10000}万",
                    index=2,  # 默认200万（武警标书标准）
                    help="无人驾驶航空器责任险（类似无人机'交强险'）"
                )
            with r8:
                fleet_size = st.number_input(
                    "📦 机队数量（同一合同）", min_value=1, max_value=100, value=1, step=1,
                    help="批量投保可享折扣"
                )

            r9, r10 = st.columns(2)
            with r9:
                previous_claims = st.number_input("⚠️ 近3年出险次数", min_value=0, max_value=20, value=0, step=1)
            with r10:
                battery_cycles = st.number_input("🔋 电池循环次数", min_value=0, max_value=500, value=50, step=10)

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
        st.caption(f"📎 {pilot_info['factor']}x 风险系数")

        st.markdown("---")
        st.markdown("**💡 三者险说明**")
        st.caption("2026年2月三部门要求无人驾驶航空器责任险强制投保")
        st.caption("武警标书要求 ≥200万/架")
        st.caption("保额越高费率越低（规模效应）")

    if submitted:
        st.markdown("---")
        st.markdown("## 📊 评估结果")

        # 传递匿名用户ID（用于加载私有校准）
        anonymous_id = st.session_state.get("anonymous_id", None)

        result = score_drone_risk(
            drone_model=drone_model, usage=usage,
            annual_hours=annual_hours, pilot_level=pilot_level,
            env_type=env_type, hull_coverage=hull_coverage,
            third_party_limit=third_party_limit,
            previous_claims=previous_claims,
            battery_cycles=battery_cycles,
            fleet_size=fleet_size,
            policyholder_type=policyholder_type,
            airworthiness=airworthiness,
            obstacle_avoidance=obstacle_avoidance,
            bvlos_mode=bvlos_mode,
            violation_record=violation_record,
            company_id=anonymous_id,
        )

        # 企查查企业核验（如果填写了企业名称）
        qcc_status = None
        if company_name:
            with st.spinner(f"🔍 正在通过企查查核验 {company_name}..."):
                qcc_result = verify_company(company_name)
                if qcc_result.get("Status") == "101":
                    qcc_status = "⚠️ 企查查API Key未激活，企业核验暂不可用"
                elif qcc_result.get("Status") != "200":
                    qcc_status = f"ℹ️ 企查查查询: {qcc_result.get('Message', '未知')}"
                else:
                    qcc_status = "✅ 企业核验通过"
                    result_data = qcc_result.get("Result", {})
                    # 如果有企业数据，可以影响评分

        record_inquiry(
            drone_model=drone_model, usage=usage,
            annual_hours=annual_hours, pilot_level=pilot_level,
            env_type=env_type, coverage_amount=hull_coverage,
            risk_score=result["total_score"], risk_level=result["risk_level"],
            premium_min=result["total_premium_min_cny"],
            premium_max=result["total_premium_max_cny"],
        )

        risk_class = ""
        if result["total_score"] <= 20: risk_class = "risk-low"
        elif result["total_score"] <= 40: risk_class = "risk-mid-low"
        elif result["total_score"] <= 60: risk_class = "risk-mid-high"
        elif result["total_score"] <= 80: risk_class = "risk-high"
        else: risk_class = "risk-high"

        # 核心指标行
        r1, r2, r3, r4, r5 = st.columns(5)
        with r1:
            st.markdown(f'<div class="metric-box"><div class="metric-value">{result["total_score"]}</div><div class="metric-label">风险评分</div></div>', unsafe_allow_html=True)
        with r2:
            st.markdown(f'<div class="metric-box"><div class="metric-value">{result["risk_level"]}</div><div class="metric-label">风险等级</div></div>', unsafe_allow_html=True)
        with r3:
            st.markdown(f'<div class="metric-box"><div class="metric-value">¥{result["hull_premium_min_cny"]:,.0f}</div><div class="metric-label">机身险(低)</div></div>', unsafe_allow_html=True)
        with r4:
            st.markdown(f'<div class="metric-box"><div class="metric-value">¥{result["third_party_premium_cny"]:,.0f}</div><div class="metric-label">三者险</div></div>', unsafe_allow_html=True)
        with r5:
            st.markdown(f'<div class="metric-box"><div class="metric-value" style="color:#1565C0;">¥{result["total_premium_min_cny"]:,.0f}</div><div class="metric-label" style="font-weight:600;">总保费起</div></div>', unsafe_allow_html=True)

        # 风险详情框
        st.markdown(f"""
        <div class="risk-box {risk_class}">
            <strong>核保结论:</strong> {result['risk_desc']}<br>
            <strong>机身险费率:</strong> {result['hull_rate_min_permille']}% - {result['hull_rate_max_permille']}% |
            <strong>三者险费率:</strong> {result['third_party_rate_permille']}‰ |
            <strong>综合费率:</strong> {result['overall_rate_min_permille']}‰ - {result['overall_rate_max_permille']}‰<br>
            <strong>机身险保费:</strong> ¥{result['hull_premium_min_cny']:,.2f} - ¥{result['hull_premium_max_cny']:,.2f} |
            <strong>三者险保费:</strong> ¥{result['third_party_premium_cny']:,.2f} |
            <strong>总保费:</strong> ¥{result['total_premium_min_cny']:,.2f} - ¥{result['total_premium_max_cny']:,.2f}
        </div>
        """ , unsafe_allow_html=True)

        # 企查查核验状态
        if qcc_status:
            st.markdown(f"🔍 **企查查企业核验:** {qcc_status}")

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**🔍 风险因子分解**")
            factors_df = pd.DataFrame([
                {"因子": k, "得分": v, "占比": f"{v/result['total_score']*100:.0f}%" if result['total_score'] > 0 else "N/A"}
                for k, v in result["factor_breakdown"].items()
            ])
            st.dataframe(factors_df, use_container_width=True, hide_index=True)

        with col_b:
            st.markdown("**📈 风险分析报告**")
            st.markdown(explain_risk_factors(result).replace("\n", "  \n"))

        if result["missing_info"]:
            st.warning("⚠️ **AI检测到以下信息缺失:**")
            for msg in result["missing_info"]:
                st.caption(f"- {msg}")

with tab2:
    st.markdown("### 📊 数据飞轮仪表盘")
    st.markdown("*数据飞轮是AI核心护城河——积累越多，定价越准*")

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("询价总数", stats["total_inquiries"])
    col_b.metric("成交", stats["bought"])
    col_c.metric("未成交", stats["not_bought"])
    col_d.metric("转化率", f"{stats['conversion_rate']}%")

    st.markdown("---")
    st.markdown("**数据飞轮成长路径**")
    phases = pd.DataFrame([
        {"阶段": "🚀 启动期", "数据量": "0-50条", "能力": "基础风险画像", "可做的": "了解客户分布、常用机型"},
        {"阶段": "⚡ 积累期", "数据量": "50-200条", "能力": "识别最优客户画像", "可做的": "优化投保问卷、匹配最佳保司"},
        {"阶段": "🔥 成型期", "数据量": "200-1000条", "能力": "拿数据找保司谈专属产品", "可做的": "用需求数据说服保司定制费率"},
        {"阶段": "🏆 飞轮期", "数据量": "1000+条", "能力": "AI模型替代规则引擎", "可做的": "接入遥测数据实现动态实时定价"},
    ])
    st.dataframe(phases, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("**最近询价记录**")
    recent = get_recent_inquiries(20)
    if recent:
        df_recent = pd.DataFrame(recent)
        display_cols = ["timestamp", "drone_model", "usage", "risk_score", "risk_level", "bought"]
        available = [c for c in display_cols if c in df_recent.columns]
        st.dataframe(df_recent[available].tail(10), use_container_width=True, hide_index=True)
    else:
        st.info("还没有询价记录，去「投保评估」Tab开始吧！")

with tab3:
    st.markdown("### 🧠 AI模型架构说明")

    st.markdown("""
    **版本: v0.2 — 规则引擎（基于政府采购数据校准）**

    **费率校准基准**:
    - 上海消防救援总队特勤支队2026年无人机保险采购 
      （[ccgp.gov.cn](https://www.ccgp.gov.cn/cggg/zygg/qtgg/202604/t20260430_26490816.htm)）
    - 预算 ¥180,000 / 16架 + 三者险≥200万
    - 综合费率 ≈ **0.55%**
    - 补充数据: DJI Care Refresh 官方定价, ccgp.gov.cn 公告列表10页

    ---

    #### 📊 机身险费率表

    | 风险等级 | 费率%/年 | 适用场景 |
    |---------|---------|---------|
    | 🟢 低风险 | 2.5% - 4.0% | 航拍·郊区·有证飞手 |
    | 🟡 中低风险 | 4.0% - 6.0% | 巡检·行业级·标准任务 |
    | 🟠 中高风险 | 6.0% - 10.0% | 消防/警用·城市环境 |
    | 🔴 高风险 | 10.0% - 15.0% | 运载投送·特殊任务 |

    #### 📊 三者险费率表

    | 单机保额 | 费率‰ | 保费/年 |
    |---------|-------|--------|
    | 50万 | 0.35‰ | ¥175 |
    | 100万 | 0.45‰ | ¥450 |
    | **200万** | **0.55‰** | **¥1,100 ← 标书基准** |
    | 500万 | 0.70‰ | ¥3,500 |
    | 1000万 | 0.85‰ | ¥8,500 |

    #### 📊 按机型报价（标准场景: 巡检·郊区·机长·三者险200万）

    | 机型 | 设备价 | 机身险 | 三者险 | 总保费 |
    |------|-------|-------|-------|-------|
    | Mini 4 Pro | ¥8,000 | ¥480 | ¥1,100 | ¥1,580 |
    | Mavic 3 Pro | ¥22,000 | ¥1,320 | ¥1,100 | ¥2,420 |
    | Mavic 3T (企业版) | ¥25,000 | ¥1,500 | ¥1,100 | ¥2,600 |
    | Matrice 30T (M30T) | ¥35,000 | ¥1,400 | ¥1,100 | ¥2,500 |
    | Matrice 350 RTK | ¥65,000 | ¥2,600 | ¥1,100 | ¥3,700 |
    | FlyCart 30 | ¥125,000 | ¥7,500 | ¥1,100 | ¥8,600 |

    #### 🔑 定价公式

    ```
    总保费 = 机身险(保额 × 2.5%-15%) + 三者险(保额 × 0.35‰-0.85‰) - 机队折扣
    ```

    #### 🧩 16维度评分卡（v0.8 基于行业标准重构）

    | 维度 | 权重 | 说明 |
    |------|------|------|
    | **设备风险** | ~8% | 型号基础事故率 |
    | **电池老化** | ~5% | 循环次数/200 |
    | **运载额外风险** | ~4% | 运载类机型特殊加费 |
    | **适航认证** | ~8% | **无认证直接拒保**（行业标准） |
    | **避障能力** | ~6% | 全向避障→折扣，无避障→加费 |
    | **使用场景** | ~12% | 航拍/物流/公共安全/运载等 |
    | **超视距(BVLOS)** | ~8% | **BVLOS加费50-100%** |
    | **操作员资质** | ~12% | CAAC/AOPA等级，无证行业级→拒保 |
    | **违规记录** | ~6% | **严重违规→拒保** |
    | **飞行环境** | ~7% | 城市密集度/水域/室内 |
    | **飞行暴露量** | ~6% | 年飞行小时 |
    | **历史理赔** | ~10% | 近3年出险次数 |
    | **保额配置** | ~6% | 保额/设备价值比 |
    | **三者险风险** | ~4% | 保额对应风险敞口 |
    | **投保人类型** | ~4% | 政府/国企/民企/个人 |
    | **机队折扣** | ~-4% | 批量投保折扣 |

    #### 📋 拒保条件（新增）

    | 条件 | 依据 |
    |------|------|
    | ❌ 无适航认证（自组装/开源飞控） | Munich Re核保标准 — 认证机型损失率低40-60% |
    | ❌ 严重违规飞行记录（黑飞/禁飞区） | Allianz/Ping An均为关键因子 |
    | ❌ 无证操作行业级/运载级无人机 | CAAC《暂行条例》强制要求 |
    | ⚠️ 评分>80 | 自动拒保，建议转再保 |

    #### 📚 参考标准

    | 来源 | 参考内容 |
    |------|---------|
    | **平安产险** 四级风险体系（第一财经） | 飞行器35%/场景30%/人员20%/环境15%权重分配 |
    | **中再产险×平安** UBI产品（新华网） | 基于用户行为动态定价框架 |
    | **Munich Re** 无人机保险白皮书 | 适航认证要求、分层再保模型 |
    | **Allianz** AGCS核保标准 | 场景优先级权重、BVLOS加费50-100% |
    | **CAAC** 《暂行条例》第12条 | 第三者责任险强制投保 |

    #### 💰 政府采购比价验证

    **上海消防特勤支队2026年标书** (预算¥180,000 / 16架):
    - AI引擎估算纯保费: ~¥49,400 (27%)
    - 服务+利润+镜头险: ~¥130,600 (73%)
    - AI可替代服务环节，将报价降至 ¥95,000-120,000

    #### 📡 数据来源

    | 来源 | 类型 | 用途 |
    |------|------|------|
    | [ccgp.gov.cn](https://www.ccgp.gov.cn) 中国政府采购网 | 官方招标公告 | 费率基准校准 |
    | DJI Care Refresh 官方定价 | 消费级保险参考 | 费率下限验证 |
    | ccgp.gov.cn 公告列表(10页) | 行业采购趋势 | 场景验证 |
    | Google News RSS | 行业动态 | 政策信号追踪 |

    #### 🔄 每周更新

    系统每7天自动巡检以下数据源:
    - ✅ ccgp.gov.cn 无人机相关采购公告
    - ✅ Google News 无人机保险行业动态
    - 新数据发现后将自动更新费率模型

    ---

    **政策背景（2026年）**
    - 🔴 2026.01.01 无人机"黑飞"正式入法
    - 🔴 2026.02.13 三部门：无人驾驶航空器责任保险**强制投保**
    - 🔴 2026.03 40余家险企推出约 **180款** 低空保险产品
    - 🟢 **行业痛点**：数据不通、风险复杂是公认最大障碍
    """)

with tab4:
    st.markdown("### 📥 导入保险公司数据，自动校准模型")

    st.markdown("""
    <div class="calibration-note">
    <strong>📌 怎么做？</strong><br>
    1. 从保险公司系统导出 <strong>保单数据</strong> 和 <strong>理赔数据</strong>（CSV格式）<br>
    2. 拖入下方上传区 → AI自动对比 <strong>实际保费 vs 模型保费</strong><br>
    3. 系统自动调整<strong>16维</strong>权重，输出<strong>校准报告</strong><br>
    4. 校准后的模型可用于后续报价
    </div>
    """, unsafe_allow_html=True)

    col_upload1, col_upload2 = st.columns(2)

    policies = []
    claims = []

    # 自动分配匿名用户ID（核保不可见，用于数据隔离）
    if "anonymous_id" not in st.session_state:
        import uuid
        st.session_state.anonymous_id = str(uuid.uuid4())[:8]
    anonymous_id = st.session_state.anonymous_id

    with col_upload1:
        st.markdown("**📋 保单数据**")
        policy_file = st.file_uploader(
            "上传保单CSV/Excel",
            type=["csv", "xlsx"],
            key="policy_upload",
            help="字段: 保单号, 机型, 机身保额, 三者保额, 实际总保费, 投保人类型, 投保日期"
        )
        if policy_file:
            raw = read_uploaded_file(policy_file.read(), policy_file.name)
            policies = parse_policy_csv(raw)
            st.success(f"已读取 {len(policies)} 条保单")

    with col_upload2:
        st.markdown("**💥 理赔数据**（可选）")
        claims_file = st.file_uploader(
            "上传理赔CSV/Excel",
            type=["csv", "xlsx"],
            key="claims_upload",
            help="字段: 保单号, 出险日期, 赔付金额, 事故原因"
        )
        if claims_file:
            raw = read_uploaded_file(claims_file.read(), claims_file.name)
            claims = parse_claims_csv(raw)
            st.success(f"已读取 {len(claims)} 条理赔")

    if policies:
        if st.button("🚀 开始校准", type="primary", use_container_width=True):
            with st.spinner("正在对比实际保费与模型保费..."):
                # 静默调用后台学习器（核保不可见）
                from glm_learner import learn_from_policies
                result = learn_from_policies(policies, claims, company_id=anonymous_id)

                # 记录公司名到日志（可选，用于行业统计聚合）
                report = result.get("report", {})
                st.balloons()
                st.markdown("### 📊 校准报告")

                mcol1, mcol2, mcol3 = st.columns(3)
                mcol1.metric("📋 保单数", report.get("total_policies", 0))
                mcol2.metric("💥 理赔数", report.get("total_claims", 0))
                mcol3.metric("📈 赔付率", f"{report.get('loss_ratio', 0)}%")

                adj = report.get("dimension_adjustments", {})
                if adj:
                    st.markdown("**需要调整的维度：**")
                    for dim, pct in adj.items():
                        direction = "🔺 上调" if pct > 0 else "🔻 下调"
                        st.write(f"{direction} {dim}: {abs(pct):.0f}%")
                else:
                    st.success("✅ 当前模型与输入数据偏差在合理范围内")

                notes = report.get("notes", "")
                if notes:
                    st.markdown("**校准建议：**")
                    st.info(notes)

                st.markdown("---")
                st.caption("📊 校准结果已持久化，后续报价将自动应用学习到的修正")

    else:
        st.info("👆 上传保单数据后，校准按钮将自动激活")

    # 显示CSV模板
    with st.expander("📎 下载CSV模板"):
        st.markdown("**保单模板：**")
        st.code("保单号,机型,机身保额,三者保额,实际总保费,投保人类型,投保日期\nP001,M350,650000,2000000,4500,政府,2025-03-15\nP002,M30T,350000,2000000,3200,企业,2025-06-20")
        st.markdown("**理赔模板：**")
        st.code("保单号,出险日期,赔付金额,事故原因\nP001,2025-08-12,12000,炸机\nP002,2025-09-03,3200,挂树")

st.markdown("---")
st.markdown("*晶世科保 · 无人机保险AI引擎 v0.2 · 数据校准: ccgp.gov.cn 上海消防特勤支队2026标书 · 🔄 每周自动巡检更新*")
