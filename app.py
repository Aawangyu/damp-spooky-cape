import streamlit as st
import pandas as pd
import engine
import random

st.set_page_config(page_title="大乐透量化预测系统", layout="wide")
st.title("🧬 大乐透全维量化预测系统")
st.caption("融合：贝叶斯后验 · Dirichlet共轭 · 马尔科夫链 · 几何生存函数 · 超几何模拟")

engine.init_db()
if engine.draw_count() == 0:
    st.error("数据库为空！请上传 dlt.db。")
    st.stop()

weights = engine.get_advanced_weights()
if not weights:
    st.warning("数据量不足（至少需要10期），无法建立数学模型。")
    st.stop()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎯 综合预测与Top7", "📈 趋势联系", "🔬 深度科学生成", "📋 模拟记录", "💡 期望与风险管理"
])

with tab1:
    st.markdown("### 🌟 前区 Top 7 黄金参考号")
    st.caption("综合了贝叶斯后验概率、马尔科夫转移概率与遗漏生存函数，推演出的最高概率号码。")
    sorted_f = sorted(weights["front_prob"].items(), key=lambda x: x[1], reverse=True)[:7]
    
    cols = st.columns(7)
    for i, (num, prob) in enumerate(sorted_f):
        with cols[i]:
            st.metric(label=f"号码 {num:02d}", value=f"{prob}%")

    st.markdown("### 🔵 后区 Top 3 核心参考号")
    sorted_b = sorted(weights["back_prob"].items(), key=lambda x: x[1], reverse=True)[:3]
    b_cols = st.columns(3)
    for i, (num, prob) in enumerate(sorted_b):
        with b_cols[i]:
            st.metric(label=f"号码 {num:02d}", value=f"{prob}%")

    st.divider()
    
    st.markdown("### 📊 数据模型深度解析")
    with st.expander("点击查看：前区贝叶斯后验 & 马尔科夫链原始数据"):
        df_f = pd.DataFrame({
            "号码": range(1, 36),
            "贝叶斯后验概率": [round(weights["bayes_prob"][n]*100, 2) for n in range(1, 36)],
            "上期开出转移次数": [weights["front_trans"][n] for n in range(1, 36)],
            "当前遗漏期数": [weights["front_omit"][n] for n in range(1, 36)]
        }).sort_values("贝叶斯后验概率", ascending=False)
        st.dataframe(df_f, use_container_width=True, hide_index=True)

    # 🔥 最下方的高亮推荐栏目
    st.divider()
    st.markdown("### 🏆 最终量化决策推荐（基于全维模型权重）")
    
    top7_front = sorted([num for num, prob in sorted_f])
    top3_back = sorted([num for num, prob in sorted_b])
    
    front_str = "  ".join([f"{n:02d}" for n in top7_front])
    back_str = "  ".join([f"{n:02d}" for n in top3_back])
    
    st.success(f"**🔥 前区精选大底 (Top 7)：** \n\n## {front_str}")
    st.info(f"**🔥 后区精选大底 (Top 3)：** \n\n## {back_str}")
    
    st.caption("💡 提示：您可以从上述 Top7 和 Top3 中，按照冷热搭配（如3热2冷）自由组合，或者直接去「深度科学生成」页面提取系统自动约束出的 5+2 组合。")

with tab2:
    st.markdown("### 📈 趋势联系与独立性检验")
    st.info("基于皮尔逊相关系数与卡方检验，我们确认大乐透各个号码之间“互相独立”。这意味着冷热交替不会影响下期开奖，所有关联都是统计错觉。")
    
    rows = engine.get_all_draws()
    if len(rows) >= 2:
        st.markdown(f"**最新一期:** {rows[0][0]} | 前区: {rows[0][2:7]} | 后区: {rows[0][7:9]}")
        st.markdown(f"**上一期:** {rows[1][0]} | 前区: {rows[1][2:7]} | 后区: {rows[1][7:9]}")
        
        repeats = len(set(rows[0][2:7]) & set(rows[1][2:7]))
        st.metric("重号数 (落号)", f"{repeats} 个", "历史均值: 0~2个")

with tab3:
    st.markdown("### 🔬 蒙特卡洛模拟生成")
    st.caption("结合上述所有数学模型，进行 8000 次全量模拟，并通过重号/邻号约束过滤。")
    target = st.text_input("目标期号（选填）", placeholder="例如 26124")
    if st.button("🧬 启动量化模拟", type="primary"):
        with st.spinner("正在进行马尔科夫链演化与贝叶斯采样..."):
            rows = engine.get_all_draws()
            last_front = rows[0][2:7] if rows else None
            front, back = engine.generate_scientific(weights, last_front)
            engine.save_prediction(weights, target, front, back)
            st.success(f"🎯 最终推断 -> 前区：{front}  |  后区：{back}")

with tab4:
    st.subheader("所有模拟记录")
    preds = engine.get_predictions()
    if preds:
        df = pd.DataFrame(preds, columns=["ID", "期号", "前区", "后区", "时间", "结果", "前区命中", "后区命中"])
        st.dataframe(df, use_container_width=True, hide_index=True)

with tab5:
    st.markdown("### 💡 极限定理与风险控制指导")
    st.error("🚨 **大数定律与破产概率**：任何预测模型都无法战胜“独立随机事件”的物理本质。买得越多，结果越趋近于极低的数学期望。不要试图用加倍投注（马丁格尔策略）去回本，破产概率会呈指数上升。")
    
    st.markdown("#### 1. 超几何分布与期望收益")
    c_total = engine.comb(35, 5) * engine.comb(12, 2)
    st.write(f"大乐透总组合数：**{c_total:,}** 种。")
    st.write(f"一等奖（5+2）理论概率：**1 / {c_total:,}**。")
    st.write(f"数学期望：假设奖池为1亿，单注2元，期望收益远低于2元，属于**负和游戏**。")
    
    st.markdown("#### 2. 凯利准则 (Kelly Criterion) 的应用")
    st.info("凯利公式用于计算最佳下注比例：\(f^* = (bp - q) / b\)。因为大乐透的胜率 \(p\) 极小，且赔率 \(b\) 为固定值，算出的 \(f^*\) 是负数。**科学结论：理性的下注额永远是 0**。")
    
    st.markdown("#### 3. 理性购彩指导")
    st.success("✅ 把这款软件当做**统计学和贝叶斯推断的练习场**，享受数据可视化的乐趣。\n\n✅ 每次投入不超过一杯奶茶钱，不中当做慈善，中了当做奇迹。\n\n✅ 永远不要相信“必中规律”，只相信数学模型的演算。")