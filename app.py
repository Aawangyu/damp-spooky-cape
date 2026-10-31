import streamlit as st
import pandas as pd
import engine
import json
import extra_streamlit_components as stx
import plotly.graph_objects as go

st.set_page_config(page_title="大乐透量化预测系统", layout="wide")

cookie_manager = stx.CookieManager()
saved_user = cookie_manager.get(cookie="dlt_user")
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""

st.sidebar.header("👤 用户中心")
if saved_user and not st.session_state.logged_in:
    st.session_state.logged_in = True
    st.session_state.user_id = saved_user

if not st.session_state.logged_in:
    username = st.sidebar.text_input("请输入专属ID：")
    if st.sidebar.button("登录 / 注册"):
        if username.strip():
            st.session_state.logged_in = True
            st.session_state.user_id = username.strip()
            cookie_manager.set("dlt_user", username.strip(), expires_at=None)
            st.rerun()
    st.info("👈 请在左侧输入 ID 登录。")
    st.stop()
else:
    user_id = st.session_state.user_id
    st.sidebar.success(f"欢迎回来，{user_id}!")
    if st.sidebar.button("退出登录"):
        st.session_state.logged_in = False
        st.session_state.user_id = ""
        cookie_manager.delete("dlt_user")
        st.rerun()

st.title("🧬 大乐透全维量化预测系统")
st.caption(f"当前账号：**{user_id}** | 融合：时间衰减 · 位置连线 · 深度反推")

engine.init_db()
weights = engine.get_advanced_weights()
if not weights:
    st.warning("数据量不足，无法建立模型。")
    st.stop()

tabs = st.tabs(["🎯 综合预测与反推", "📈 位置对比走势图", "🔬 深度生成与套票", "📋 模拟与盈亏", "🔪 科学杀号器", "🏹 极限回测"])

with tabs[0]:
    st.markdown("### 🌟 前区 Top 7 黄金参考号")
    sorted_f = sorted(weights["front_prob"].items(), key=lambda x: x[1], reverse=True)[:7]
    cols = st.columns(7)
    for i, (num, prob) in enumerate(sorted_f):
        with cols[i]: st.metric(label=f"号码 {num:02d}", value=f"{prob}%")

    st.markdown("### 🔵 后区 Top 3 核心参考号")
    sorted_b = sorted(weights["back_prob"].items(), key=lambda x: x[1], reverse=True)[:3]
    b_cols = st.columns(3)
    for i, (num, prob) in enumerate(sorted_b):
        with b_cols[i]: st.metric(label=f"号码 {num:02d}", value=f"{prob}%")

    st.divider()
    st.markdown("### 🏆 最终量化决策推荐")
    top7_front = sorted([num for num, prob in sorted_f])
    top3_back = sorted([num for num, prob in sorted_b])
    st.success(f"**🔥 前区精选 (Top 7)：** \n\n## {'  '.join([f'{n:02d}' for n in top7_front])}")
    st.info(f"**🔥 后区精选 (Top 3)：** \n\n## {'  '.join([f'{n:02d}' for n in top3_back])}")
    
    if st.button("🔄 反推：为什么推荐这些号码？", type="primary"):
        st.info("""
        **反推解析：**
        1. **时间衰减**：系统赋予了最近 30 期的数据极高权重，因此推荐的是近期状态最火热/最符合回补概率的。
        2. **综合概率**：结合遗漏值、上期重邻号和衰减频率得出的期望值。
        """)

# 🔥 全新的位置对比走势图
with tabs[1]:
    st.markdown("### 📈 位置对比连线图")
    st.info("比较上一期真实开奖号码 vs 你最新生成的一注号码。直观看出每位数字的升降趋势。")
    
    latest_draws = weights["latest_three"]
    user_preds = engine.get_predictions(user_id)
    
    if latest_draws and user_preds:
        last_draw = latest_draws[0]
        actual_f = [last_draw[2], last_draw[3], last_draw[4], last_draw[5], last_draw[6]]
        
        latest_pred = user_preds[0]
        pred_f = json.loads(latest_pred[2])
        
        fig = go.Figure()
        # 画前区连线（从开奖号到推荐号）
        for i in range(5):
            fig.add_trace(go.Scatter(
                x=["上期开奖", "我的预测"], y=[actual_f[i], pred_f[i]],
                mode='lines+markers+text',
                text=[f"第{i+1}位: {actual_f[i]}", f"{pred_f[i]}"],
                textposition="top center",
                name=f"位置{i+1}",
                line=dict(width=3)
            ))
            
        fig.update_layout(
            title="前区 5 个位置独立走势对比",
            yaxis=dict(title="号码值", range=[0, 36]),
            height=400,
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("暂无数据，请先去『深度生成』页面生成一注号码！")

with tabs[2]:
    st.markdown("### 🔬 智能量化生成")
    
    latest_period = weights["latest_three"][0][0] if weights["latest_three"] else "26123"
    try:
        next_period = str(int(latest_period) + 1)
    except:
        next_period = "下一期"
        
    target = st.text_input("目标期号（已自动推算，可修改）", value=next_period)
    
    st.markdown("#### 选择生成模式")
    col1, col2, col3 = st.columns(3)
    with col1: btn1 = st.button("🎯 生成 1 注推荐")
    with col2: btn5 = st.button("📦 生成 5 注推荐")
    with col3: btn9 = st.button("💰 生成 9 注 (18元套票)")
        
    gen_count = 1 if btn1 else (5 if btn5 else (9 if btn9 else 0))
    
    if gen_count > 0:
        latest = weights["latest_three"]
        lf = latest[0][2:7] if latest else None
        lb = latest[0][7:9] if latest else None
        
        with st.spinner(f"正在生成 {gen_count} 注..."):
            results = engine.generate_numbers(weights, lf, lb, count=gen_count)
            engine.save_predictions_batch(weights, target, results, user_id)
            
            st.success(f"✅ 已生成 {gen_count} 注并存入数据库！")
            
            # 结果直接展示在当前页面下方
            for idx, res in enumerate(results):
                st.markdown(f"**第 {idx+1} 注**")
                st.code(f"前区：{res['front']}  |  后区：{res['back']}", language="text")
                st.caption(f"💡 依据：{res['reason']}")

with tabs[3]:
    st.subheader(f"📋 {user_id} 的模拟记录")
    if st.button("🔄 同步开奖复盘"):
        engine.review_all()
        st.success("复盘完成！")
        st.rerun()
        
    preds = engine.get_predictions(user_id)
    if preds:
        df = pd.DataFrame(preds, columns=["ID", "期号", "前区", "后区", "时间", "结果", "前区命中", "后区命中"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        wins = df[~df["结果"].isin(["未中", "待开奖"])]
        if not wins.empty:
            st.success(f"🎉 恭喜！你一共中奖了 {len(wins)} 注！")
    else:
        st.info("暂无记录。")

with tabs[4]:
    st.markdown("### 🔪 科学杀号分析")
    col_a, col_b = st.columns(2)
    with col_a: kill_f = st.multiselect("选择要杀的前区号码：", list(range(1, 36)))
    with col_b: kill_b = st.multiselect("选择要杀的后区号码：", list(range(1, 13)))
        
    if st.button("📊 分析杀号合理性"):
        if not kill_f and not kill_b: st.warning("请至少选择一个号码！")
        else:
            latest = weights["latest_three"]
            lf = latest[0][2:7] if latest else []
            lb = latest[0][7:9] if latest else []
            for n in kill_f: st.warning(engine.analyze_kill_number(n, True, lf, lb))
            for n in kill_b: st.warning(engine.analyze_kill_number(n, False, lf, lb))

with tabs[5]:
    st.markdown("### 🏹 极限模拟回测器")
    test_period = st.text_input("输入你想测试的历史期号：", placeholder="例如 26123")
    if st.button("🚀 开始疯狂回测", type="primary"):
        if not test_period: st.warning("请输入期号！")
        else:
            with st.spinner("引擎正在疯狂摇奖中..."):
                hit_count, msg = engine.simulate_hit_test(weights, test_period, user_id)
                if hit_count:
                    st.balloons()
                    st.success(f"🎉 **奇迹发生了！** 系统在模拟了 **{hit_count:,} 次** 后，成功摇出了 {test_period} 期的大奖号码！")
                    st.markdown(f"**🔍 深度分析：**\n\n{msg}")
                else:
                    st.error(f"😭 **回测结束**：{msg}。")

    st.divider()
    st.markdown("#### 📜 我的历史回测档案")
    logs = engine.get_backtest_logs(user_id)
    if logs:
        log_df = pd.DataFrame(logs, columns=["回测期号", "模拟次数", "深度归因分析", "回测时间"])
        st.dataframe(log_df, use_container_width=True, hide_index=True)