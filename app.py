import streamlit as st
import pandas as pd
import engine
import random

st.set_page_config(page_title="大乐透概率模拟台", layout="wide")
st.title("🎱 大乐透科学概率与复盘台")
st.caption("基于“物理随机抽样 + 历史位置形态过滤”的科学模拟模型。")

engine.init_db()
if engine.draw_count() == 0:
    st.error("数据库为空！请上传 dlt.db。")
    st.stop()

weights = engine.compute_weights()
stats = engine.compute_position_stats()

# 核心科学过滤函数：纯随机生成，但必须符合历史位置形态
def generate_scientific(weights, stats):
    fw = weights["front_weight"]
    bw = weights["back_weight"]
    
    # 计算历史各位置的合理区间（比如均值上下浮动 3.5 左右）
    f_ranges = [(stats["front"][i]["avg"] - 4.5, stats["front"][i]["avg"] + 4.5) for i in range(5)]
    
    best_candidate = None
    highest_score = -1

    # 模拟 5000 次摇奖机
    for _ in range(5000):
        # 1. 纯随机抽取（模拟摇奖机）
        front = sorted(random.sample(range(1, 36), 5))
        back = sorted(random.sample(range(1, 13), 2))

        # 2. 基础约束过滤（和值、奇偶、三区）
        if not engine.constraint_ok(front, back):
            continue

        # 3. 位置形态过滤（检查排序后的号码是否偏离历史均值太远）
        valid_shape = True
        for i in range(5):
            if not (f_ranges[i][0] <= front[i] <= f_ranges[i][1]):
                valid_shape = False
                break
        if not valid_shape:
            continue

        # 4. 打分机制：看这组号码的总权重分高不高
        score = sum([fw[n] for n in front]) + sum([bw[n] for n in back])
        
        if score > highest_score:
            highest_score = score
            best_candidate = (front, back)

    # 如果过滤太严没找到，就退回到普通生成
    if not best_candidate:
        return engine.generate_one(weights)
    return best_candidate


tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 综合概率", "📍 位置规律", "🔬 科学模拟生成", "📋 模拟记录", "📅 历史开奖"
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
    st.subheader("🔍 前区各位置形态分析（历史均值）")
    st.markdown("大乐透虽然摇奖时是乱序的，但排序后，每个位置都有其天然的“物理分布区间”。")
    
    cols = st.columns(5)
    for i in range(5):
        with cols[i]:
            st.metric(label=f"第 {i+1} 位均值", value=stats["front"][i]["avg"])
            top3 = sorted(stats["front"][i]["freq"].items(), key=lambda x: x[1], reverse=True)[:3]
            st.caption(f"高频号：{top3[0][0]}, {top3[1][0]}, {top3[2][0]}")

    st.divider()
    st.subheader("🔍 后区各位置分布分析")
    b_cols = st.columns(2)
    for i in range(2):
        with b_cols[i]:
            st.metric(label=f"后区第 {i+1} 位均值", value=stats["back"][i]["avg"])
            top3_b = sorted(stats["back"][i]["freq"].items(), key=lambda x: x[1], reverse=True)[:3]
            st.caption(f"高频号：{top3_b[0][0]}, {top3_b[1][0]}, {top3_b[2][0]}")

with tab3:
    st.subheader("🔬 蒙特卡洛科学模拟")
    st.caption("逻辑：后台纯随机模拟 5000 次摇奖机，利用历史位置规律淘汰“畸形”号码（如首位出20），再结合冷热权重选出最优解。")
    target = st.text_input("目标期号（选填）", placeholder="例如 26130")
    if st.button("🔬 启动科学模拟", type="primary"):
        with st.spinner("正在模拟 5000 次摇奖机..."):
            front, back = generate_scientific(weights, stats)
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