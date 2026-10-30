import streamlit as st
import pandas as pd
import engine
import random
import json

st.set_page_config(page_title="大乐透量化预测系统", layout="wide")

# 🔥 核心多用户入口：在左侧边栏输入专属ID
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

with tab2:
    st.markdown("### 📈 趋势联系")
    rows = engine.get_all_draws()
    if len(rows) >= 2:
        st.markdown(f"**最新一期:** {rows[0][0]} | 前区: {rows[0][2:7]}")
        repeats = len(set(rows[0][2:7]) & set(rows[1][2:7]))
        st.metric("重号数", f"{repeats} 个")

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

with tab4:
    st.subheader(f"📋 {user_id} 的模拟记录")
    # 只查询当前用户的记录
    preds = engine.get_predictions(user_id)
    if preds:
        df = pd.DataFrame(preds, columns=["ID", "期号", "前区", "后区", "时间", "结果", "前区命中", "后区命中"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("还没有属于你的记录，快去“深度生成”生成一注吧！")
        
    if st.button("🔄 同步复盘所有记录"):
        engine.review_all()
        st.success("复盘完成！快去看看经验库有没有更新！")
        st.rerun()

with tab5:
    st.subheader(f"🧠 {user_id} 的全局经验教训库")
    st.markdown("这里记录了你从第1次到第N次所有的数学偏差。")
    
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

with tab6:
    st.markdown("### 💡 风控")
    st.error("大数定律不可违背，模型只能逼近历史期望，无法预知未来。")