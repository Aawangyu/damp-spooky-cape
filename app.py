import streamlit as st
import pandas as pd
import engine
import random
import json

st.set_page_config(page_title="大乐透量化预测系统", layout="wide")

# 用户中心
st.sidebar.header("👤 用户中心")
user_id = st.sidebar.text_input("请输入你的专属昵称/ID：", value="default")
if not user_id.strip():
    st.sidebar.warning("请先输入ID才能使用哦！")
    st.stop()

st.title("🧬 大乐透全维量化预测系统")
st.caption(f"当前登录账号：**{user_id}** | 融合：贝叶斯推断 · 马尔科夫链 · 独立经验库")

engine.init_db()
if engine.draw_count() == 0:
    st.error("数据库为空！请上传 dlt.db。")
    st.stop()

weights = engine.get_advanced_weights()
if not weights:
    st.warning("数据量不足，无法建立数学模型。")
    st.stop()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎯 综合预测", "📈 趋势联系", "🔬 深度生成", "📋 我的模拟记录", "🧠 我的经验修正", "💡 风控"
])

with tab1:
    st.markdown("### 🌟 前区 Top 7 黄金参考号")
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
    st.markdown("### 🏆 最终量化决策推荐")
    top7_front = sorted([num for num, prob in sorted_f])
    top3_back = sorted([num for num, prob in sorted_b])
    st.success(f"**🔥 前区精选 (Top 7)：** \n\n## {'  '.join([f'{n:02d}' for n in top7_front])}")
    st.info(f"**🔥 后区精选 (Top 3)：** \n\n## {'  '.join([f'{n:02d}' for n in top3_back])}")

# 🔥 满血复活的趋势联系页面
with tab2:
    st.markdown("### 📈 趋势联系与独立性检验")
    st.info("基于皮尔逊相关系数与卡方检验，我们确认大乐透各个号码之间“互相独立”。这意味着冷热交替不会影响下期开奖，所有关联都是统计错觉。")
    
    rows = engine.get_all_draws()
    if len(rows) >= 2:
        latest_f = list(rows[0][2:7])
        prev_f = list(rows[1][2:7])
        latest_b = list(rows[0][7:9])
        prev_b = list(rows[1][7:9])
        
        st.info(f"**最新一期:** {rows[0][0]} | 前区: {latest_f} | 后区: {latest_b}")
        st.info(f"**上一期:** {rows[1][0]} | 前区: {prev_f} | 后区: {prev_b}")
        
        st.markdown("### 🔴 前区联系分析")
        repeats_f = len(set(latest_f) & set(prev_f))
        neighbors_f = 0
        for n in latest_f:
            if (n-1 in prev_f) or (n+1 in prev_f): neighbors_f += 1
            
        c1, c2, c3 = st.columns(3)
        c1.metric("前区重号数 (落号)", f"{repeats_f} 个", "历史均值: 0~2个")
        c2.metric("前区邻号数 (边号)", f"{neighbors_f} 个", "历史均值: 0~2个")
        c3.metric("预测参考范围", "重号 0~2 个", "邻号 0~2 个")

        st.markdown("### 🔵 后区联系分析")
        repeats_b = len(set(latest_b) & set(prev_b))
        neighbors_b = 0
        for n in latest_b:
            if (n-1 in prev_b) or (n+1 in prev_b): neighbors_b += 1
            
        bc1, bc2, bc3 = st.columns(3)
        bc1.metric("后区重号数 (落号)", f"{repeats_b} 个")
        bc2.metric("后区邻号数 (边号)", f"{neighbors_b} 个")
        bc3.metric("预测参考范围", "重号 0~1 个")
        
        st.markdown("""
        **🧠 趋势逻辑深度解读：**
        *   **落号（重号）**：大乐透经常出现上期出过、这期继续出的号码。但通常不会超过2个。
        *   **边号（邻号）**：上期号码前后的数字（如出12，下期出11或13），也是高频发生的联系。
        我们在「深度生成」页面，会严格校验生成号码与上期号码的联系，淘汰掉“重号过多”或“邻号过多”的畸形组合。
        """)
    else:
        st.warning("数据不足，无法分析趋势。")

with tab3:
    st.markdown("### 🔬 蒙特卡洛生成 (读取我的专属经验)")
    st.caption("系统已提取【你】从第1次到现在的所有累积误差，动态调整过滤边界。")
    target = st.text_input("目标期号（选填，务必填入）", placeholder="例如 26124")
    if st.button("🧬 启动量化模拟", type="primary"):
        with st.spinner("正在读取你的专属经验库并进行采样..."):
            rows = engine.get_all_draws()
            last_front = rows[0][2:7] if rows else None
            # 传入 user_id
            front, back = engine.generate_scientific(weights, last_front, user_id)
            engine.save_prediction(weights, target, front, back, user_id)
            st.success(f"🎯 最终推断 -> 前区：{front}  |  后区：{back}")
            st.write("这注号码的综合权重占比：")
            st.write("前区", {n: weights["front_prob"][n] for n in front})
            st.write("后区", {n: weights["back_prob"][n] for n in back})

with tab4:
    st.subheader(f"📋 {user_id} 的模拟记录")
    # 只查询当前用户的记录
    preds = engine.get_predictions(user_id)
    if preds:
        df = pd.DataFrame(preds, columns=["ID", "期号", "前区", "后区", "时间", "结果", "前区命中", "后区命中"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("还没有属于你的记录，快去“深度生成”生成一注吧！")
        
    st.divider()
    if st.button("🔄 同步复盘所有记录"):
        engine.review_all()
        st.success("复盘完成！快去看看经验库有没有更新！")
        st.rerun()

with tab5:
    st.subheader(f"🧠 {user_id} 的全局经验教训库")
    st.markdown("这里记录了你从第1次到第N次所有的数学偏差，系统通过“经验回放”进行全局修正。")
    
    # 只读取当前用户的经验
    correction = engine.get_global_correction(user_id)
    c1, c2, c3 = st.columns(3)
    c1.metric("我的累积教训记录", f"{correction['total_lessons']} 条")
    c2.metric("我的和值平均偏差", f"{correction['avg_sum_delta']}")
    c3.metric("我的奇偶平均偏差", f"{correction['avg_odd_delta']}")
    
    if correction['total_lessons'] > 0:
        st.info(f"📌 **【你】的模型当前修正状态**：下一次生成时，和值基准将自动偏移 `{correction['avg_sum_delta']}` 点，以逼近真实开奖的期望。")
    
    st.markdown("#### 📝 我的历史偏差明细表")
    lessons = engine.get_all_lessons(user_id)
    if lessons:
        l_df = pd.DataFrame(lessons, columns=["期号", "预测和值", "实际和值", "和值偏差", "预测奇数", "实际奇数", "奇数偏差", "归因分类"])
        st.dataframe(l_df, use_container_width=True, hide_index=True)
    else:
        st.success("你的经验库目前还是空白的。等你复盘后，这里会自动生成数据。")

# 🔥 满血复活的风控页面
with tab6:
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