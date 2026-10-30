import streamlit as st
import pandas as pd
import engine
import random

st.set_page_config(page_title="大乐透概率模拟台", layout="wide")
st.title("🎱 大乐透深度预测与复盘台")
st.caption("融合：位置形态分布 + 蒙特卡洛模拟 + 往期趋势关联 (重号/邻号)")

engine.init_db()
if engine.draw_count() == 0:
    st.error("数据库为空！请上传 dlt.db。")
    st.stop()

weights = engine.compute_weights()
stats = engine.compute_position_stats()
trend = engine.analyze_trend()

# 核心科学过滤函数：引入上一期的趋势关联
def generate_scientific(weights, stats, last_front):
    fw = weights["front_weight"]
    bw = weights["back_weight"]
    f_ranges = [(stats["front"][i]["avg"] - 4.5, stats["front"][i]["avg"] + 4.5) for i in range(5)]
    
    best_candidate = None
    highest_score = -1

    # 模拟 8000 次摇奖机
    for _ in range(8000):
        front = sorted(random.sample(range(1, 36), 5))
        back = sorted(random.sample(range(1, 13), 2))

        # 1. 基础约束过滤
        if not engine.constraint_ok(front, back):
            continue

        # 2. 位置形态过滤
        valid_shape = True
        for i in range(5):
            if not (f_ranges[i][0] <= front[i] <= f_ranges[i][1]):
                valid_shape = False
                break
        if not valid_shape:
            continue

        # 3. 往期趋势联系过滤（与上期号码的对比）
        if last_front:
            repeats = len(set(front) & set(last_front))  # 重号数
            neighbors = 0  # 邻号数
            for n in front:
                if (n-1 in last_front) or (n+1 in last_front):
                    neighbors += 1
            
            # 经验逻辑：重号一般在 0-2 个，邻号一般在 0-2 个
            if repeats > 2 or neighbors > 2:
                continue

        # 4. 打分机制
        score = sum([fw[n] for n in front]) + sum([bw[n] for n in back])
        if score > highest_score:
            highest_score = score
            best_candidate = (front, back)

    if not best_candidate:
        return engine.generate_one(weights)
    return best_candidate

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 综合概率", "📈 趋势联系", "🔬 深度科学生成", "📋 模拟记录", "📅 历史开奖"
])

with tab1:
    st.subheader("前区号码总权重（%）")
    fp_df = pd.DataFrame({
        "号码": list(weights["front_prob"].keys()),
        "权重%": list(weights["front_prob"].values()),
        "遗漏": [weights["front_omit"][n] for n in weights["front_prob"]],
    }).sort_values("权重%", ascending=False)
    st.bar_chart(fp_df.set_index("号码")["权重%"])

with tab2:
    st.subheader("📈 往期趋势与号码联系")
    if trend:
        st.info(f"最新一期：{trend['last_period']}，开奖号码：{trend['last_front']}")
        col1, col2, col3 = st.columns(3)
        col1.metric("与上一期的重号数", f"{trend['repeats']} 个", "落号现象")
        col2.metric("与上一期的邻号数", f"{trend['neighbors']} 个", "边号现象")
        col3.metric("预测期的历史参考", "重号0~2个", "邻号0~2个")
        
        st.markdown("""
        **🧠 趋势逻辑解读：**
        1. **重号（落号）**：大乐透经常出现上期出过、这期继续出的号码。但通常不会超过2个。
        2. **邻号（边号）**：上期号码前后的数字，也是高频发生的联系。
        我们在下方的“科学生成”中，会严格校验生成号码与上期号码的联系，淘汰掉“重号过多”或“邻号过多”的畸形组合。
        """)
    else:
        st.warning("数据不足，无法分析趋势。")

with tab3:
    st.subheader("🔬 深度科学生成")
    st.caption("后台将纯随机模拟 8000 次，通过历史位置形态过滤，并强制关联上一期的重号/邻号特征，为您优中选优。")
    target = st.text_input("目标期号（选填）", placeholder="例如 26131")
    if st.button("🔬 启动深度模拟", type="primary"):
        with st.spinner("正在进行万次蒙特卡洛模拟与趋势关联比对..."):
            last_front = trend['last_front'] if trend else None
            front, back = generate_scientific(weights, stats, last_front)
            engine.save_prediction(weights, target, front, back)
            st.success(f"前区：{front}  |  后区：{back}")
            st.write("这注号码的权重%：")
            st.write("前区", {n: weights["front_prob"][n] for n in front})
            st.write("后区", {n: weights["back_prob"][n] for n in back})

with tab4:
    st.subheader("所有模拟记录")
    rows = engine.get_predictions()
    if rows:
        df = pd.DataFrame(rows, columns=["ID", "期号", "前区", "后区", "时间", "结果", "前区命中", "后区命中"])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无记录")

with tab5:
    st.subheader("历史开奖记录（真实数据）")
    draws = engine.get_all_draws()
    if draws:
        draw_df = pd.DataFrame(draws, columns=["期号", "开奖日期", "前区1", "前区2", "前区3", "前区4", "前区5", "后区1", "后区2"])
        draw_df["前区号码"] = draw_df.apply(lambda x: f"{x['前区1']:02d} {x['前区2']:02d} {x['前区3']:02d} {x['前区4']:02d} {x['前区5']:02d}", axis=1)
        draw_df["后区号码"] = draw_df.apply(lambda x: f"{x['后区1']:02d} {x['后区2']:02d}", axis=1)
        st.dataframe(draw_df[["期号", "开奖日期", "前区号码", "后区号码"]], use_container_width=True, hide_index=True)