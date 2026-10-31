import streamlit as st
import pandas as pd
import engine
import json
import extra_streamlit_components as stx

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
st.caption(f"当前账号：**{user_id}** | 核心功能：逐位归因反推 · 开奖差异比对")

engine.init_db()
weights = engine.get_advanced_weights()
if not weights:
    st.warning("数据量不足。")
    st.stop()

tabs = st.tabs(["🎯 综合预测", "📈 历史关联解析", "🔬 深度生成与反推", "📋 复盘与差异比对", "🔪 科学杀号器"])

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

# 🔥 重构：位置关联解析
with tabs[1]:
    st.markdown("### 📈 历史位置规律关联分析")
    st.info("分析上一期各位置的落点，与本期该位置数学引力区间的关联。")
    
    last_draw = weights["latest_three"][0] if weights["latest_three"] else None
    if last_draw:
        st.markdown(f"**上期开奖（{last_draw[0]}）**：前区 `{[last_draw[i] for i in range(2,7)]}` | 后区 `{[last_draw[i] for i in range(7,9)]}`")
        
        st.markdown("#### 逐位联系推演")
        for i in range(5):
            val = last_draw[2+i]
            avg = weights["f_pos_avgs"][i]
            st.markdown(f"**第 {i+1} 位**：上期开出 `{val}`，历史均值 `{avg}`。本期系统将围绕均值 `{avg}` 与上期偏移量进行综合计算，寻找高概率的反弹或回落点。")

# 🔥 重构：生成页面增加“反推”按钮
with tabs[2]:
    st.markdown("### 🔬 智能量化生成")
    
    latest_period = weights["latest_three"][0][0] if weights["latest_three"] else "26123"
    try: next_period = str(int(latest_period) + 1)
    except: next_period = "下一期"
        
    target = st.text_input("目标期号", value=next_period)
    
    col1, col2, col3 = st.columns(3)
    with col1: btn1 = st.button("🎯 生成 1 注推荐")
    with col2: btn5 = st.button("📦 生成 5 注推荐")
    with col3: btn9 = st.button("💰 生成 9 注 (18元套票)")
        
    gen_count = 1 if btn1 else (5 if btn5 else (9 if btn9 else 0))
    
    if gen_count > 0:
        latest = weights["latest_three"]
        lf = latest[0][2:7] if latest else None
        lb = latest[0][7:9] if latest else None
        
        with st.spinner(f"生成中..."):
            results = engine.generate_numbers(weights, lf, lb, count=gen_count)
            engine.save_predictions_batch(weights, target, results, user_id)
            
            # 存入 session_state 以便反推
            st.session_state['last_results'] = results
            st.success(f"✅ 已生成 {gen_count} 注！")
            
    # 渲染结果与反推
    if 'last_results' in st.session_state:
        for idx, res in enumerate(st.session_state['last_results']):
            st.markdown(f"--- \n**第 {idx+1} 注**")
            st.code(f"前区：{res['front']}  |  后区：{res['back']}", language="text")
            
            # 反推按钮
            if st.button(f"🔍 查看第 {idx+1} 注反推逻辑", key=f"reverse_{idx}"):
                st.info("### 🧠 数学模型推导过程：\n\n" + "\n\n".join(res['reason']))

# 🔥 重构：复盘增加差异归因按钮
with tabs[3]:
    st.subheader(f"📋 {user_id} 的模拟记录")
    if st.button("🔄 同步开奖复盘"):
        engine.review_all()
        st.success("复盘完成！")
        st.rerun()
        
    preds = engine.get_predictions(user_id)
    if preds:
        # 获取所有开奖数据用于比对
        draws = {r[0]: r for r in engine.get_all_draws()}
        
        for p in preds:
            pid, tp, fj, bj, created, level, hit_f, hit_b = p
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**ID {pid}** | 期号 `{tp}` | 预测：前区 `{json.loads(fj)}` 后区 `{json.loads(bj)}` | 状态：**{level}**")
            with col2:
                # 如果已开奖，提供比对按钮
                if tp in draws:
                    if st.button("📊 差异归因", key=f"gap_{pid}"):
                        actual = draws[tp]
                        act_f = [actual[1], actual[2], actual[3], actual[4], actual[5]]
                        act_b = [actual[6], actual[7]]
                        
                        report = engine.analyze_gap(json.loads(fj), json.loads(bj), act_f, act_b)
                        st.warning(f"**实际开奖：** 前区 `{act_f}` 后区 `{act_b}`\n\n---\n**分析报告：**\n\n{report}")
    else:
        st.info("暂无记录。")

with tabs[4]:
    st.markdown("### 🔪 科学杀号分析")
    col_a, col_b = st.columns(2)
    with col_a: kill_f = st.multiselect("选择要杀的前区号码：", list(range(1, 36)))
    with col_b: kill_b = st.multiselect("选择要杀的后区号码：", list(range(1, 13)))
    if st.button("📊 分析合理性"):
        latest = weights["latest_three"]
        lf = latest[0][2:7] if latest else []
        lb = latest[0][7:9] if latest else []
        for n in kill_f: st.warning(engine.analyze_kill_number(n, True, lf, lb))
        for n in kill_b: st.warning(engine.analyze_kill_number(n, False, lf, lb))