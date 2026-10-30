import streamlit as st
import pandas as pd
import engine
import random
import json
import extra_streamlit_components as stx

st.set_page_config(page_title="大乐透量化预测系统", layout="wide")

# 🔥 初始化 Cookie 管理器，实现永久登录
cookie_manager = stx.CookieManager()

# 尝试从浏览器 Cookie 里读取用户 ID
saved_user = cookie_manager.get(cookie="dlt_user")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""

st.sidebar.header("👤 用户中心")

# 如果读到了 Cookie，自动登录
if saved_user and not st.session_state.logged_in:
    st.session_state.logged_in = True
    st.session_state.user_id = saved_user

if not st.session_state.logged_in:
    username = st.sidebar.text_input("请输入专属ID：")
    if st.sidebar.button("登录 / 注册"):
        if username.strip():
            st.session_state.logged_in = True
            st.session_state.user_id = username.strip()
            # 将 ID 存入浏览器 Cookie，有效期 365 天
            cookie_manager.set("dlt_user", username.strip(), expires_at=None)
            st.rerun()
        else:
            st.sidebar.warning("ID不能为空！")
    st.info("👈 请在左侧输入您的专属 ID 登录。登录一次后，系统会自动记住您。")
    st.stop()
else:
    user_id = st.session_state.user_id
    st.sidebar.success(f"欢迎回来，{user_id}!")
    if st.sidebar.button("退出登录"):
        st.session_state.logged_in = False
        st.session_state.user_id = ""
        cookie_manager.delete("dlt_user") # 清除 Cookie
        st.rerun()

st.title("🧬 大乐透全维量化预测系统")
st.caption(f"当前账号：**{user_id}** | 融合：全维概率 · 动态寻优 · 极限回测")

engine.init_db()
weights = engine.get_advanced_weights()
if not weights:
    st.warning("数据量不足，无法建立数学模型。")
    st.stop()

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🎯 综合预测", "📈 趋势联系", "🔬 深度生成", "📋 模拟记录", "🧠 经验修正", "🏹 极限回测", "💡 风控"
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
        latest_f = list(rows[0][2:7])
        prev_f = list(rows[1][2:7])
        latest_b = list(rows[0][7:9])
        prev_b = list(rows[1][7:9])
        st.info(f"**最新一期:** {rows[0][0]} | 前区: {latest_f} | 后区: {latest_b}")
        st.info(f"**上一期:** {rows[1][0]} | 前区: {prev_f} | 后区: {prev_b}")
        c1, c2, c3 = st.columns(3)
        c1.metric("前区重号数", len(set(latest_f) & set(prev_f)), "0~2个")
        c2.metric("后区重号数", len(set(latest_b) & set(prev_b)), "0~1个")

with tab3:
    st.markdown("### 🔬 融合生成 (海量摇奖+高分随机+经验修正)")
    target = st.text_input("目标期号（务必填入）", placeholder="例如 26124")
    if st.button("🧬 启动量化模拟", type="primary"):
        with st.spinner("正在进行万次物理抽样与形态打分..."):
            rows = engine.get_all_draws()
            last_front = rows[0][2:7] if rows else None
            last_back = rows[0][7:9] if rows else None
            front, back = engine.generate_scientific(weights, last_front, last_back, user_id)
            engine.save_prediction(weights, target, front, back, user_id)
            st.success(f"🎯 最终推断 -> 前区：{front}  |  后区：{back}")

with tab4:
    st.subheader(f"📋 {user_id} 的模拟记录")
    preds = engine.get_predictions(user_id)
    if preds:
        df = pd.DataFrame(preds, columns=["ID", "期号", "前区", "后区", "时间", "结果", "前区命中", "后区命中"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    if st.button("🔄 同步复盘所有记录"):
        engine.review_all()
        st.success("复盘完成！")
        st.rerun()

with tab5:
    st.subheader(f"🧠 经验库")
    correction = engine.get_global_correction(user_id)
    c1, c2, c3 = st.columns(3)
    c1.metric("累积教训", f"{correction['total_lessons']} 条")
    c2.metric("和值平均偏差", f"{correction['avg_sum_delta']}")
    
    lessons = engine.get_all_lessons(user_id)
    if lessons:
        l_df = pd.DataFrame(lessons, columns=["期号", "预和值", "实和值", "和值偏差", "预奇", "实奇", "奇偏差", "归因"])
        st.dataframe(l_df, use_container_width=True, hide_index=True)

with tab7:
    st.markdown("### 🏹 极限模拟回测器")
    test_period = st.text_input("输入你想测试的期号（必须是数据库里已有的）：", placeholder="例如 26123")
    
    if st.button("🚀 开始疯狂回测", type="primary"):
        if not test_period:
            st.warning("请输入期号！")
        else:
            with st.spinner("引擎正在疯狂摇奖中，请稍候（最多模拟 500 万次）..."):
                hit_count, msg = engine.simulate_hit_test(weights, test_period, user_id)
                
                if hit_count:
                    st.balloons()
                    st.success(f"🎉 **奇迹发生了！** 系统在模拟了 **{hit_count:,} 次** 后，成功摇出了 {test_period} 期的大奖号码！")
                    st.info(f"**🔍 深度分析（为什么会是这组号码？）**\n\n{msg}")
                else:
                    st.error(f"😭 **回测结束**：{msg}。")

    st.divider()
    st.markdown("#### 📜 我的历史回测档案")
    logs = engine.get_backtest_logs(user_id)
    if logs:
        log_df = pd.DataFrame(logs, columns=["回测期号", "模拟次数", "深度归因分析", "回测时间"])
        st.dataframe(log_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无历史回测记录，快去上面测一把吧！")

with tab6:
    st.markdown("### 💡 风控")
    st.error("🚨 模型只能逼近历史期望，无法预知未来。大数定律不可违背。")