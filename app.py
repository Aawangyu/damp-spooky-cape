import streamlit as st
import pandas as pd
import engine

st.set_page_config(page_title="大乐透概率模拟台", layout="wide")
st.title("🎱 大乐透概率模拟与复盘台")
st.caption("百分比是本工具规则里的权重占比，不是真实中奖概率。仅供数据分析与模拟。")

engine.init_db()

if engine.draw_count() == 0:
    st.error("数据库为空！请确保你上传了 dlt.db 文件。")
    st.stop()

weights = engine.compute_weights()

# 这里增加了第五个标签页：📅 历史开奖
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 概率总览", "🎲 生成一注", "📋 模拟记录", "🔄 复盘反推", "📅 历史开奖"])

with tab1:
    st.subheader("前区号码权重占比（%）")
    fp_df = pd.DataFrame({
        "号码": list(weights["front_prob"].keys()),
        "权重%": list(weights["front_prob"].values()),
        "当前遗漏": [weights["front_omit"][n] for n in weights["front_prob"]],
        "历史出现次数": [weights["front_freq"][n] for n in weights["front_prob"]],
    }).sort_values("权重%", ascending=False)
    st.bar_chart(fp_df.set_index("号码")["权重%"])
    st.dataframe(fp_df, use_container_width=True, hide_index=True)

    st.subheader("后区号码权重占比（%）")
    bp_df = pd.DataFrame({
        "号码": list(weights["back_prob"].keys()),
        "权重%": list(weights["back_prob"].values()),
        "当前遗漏": [weights["back_omit"][n] for n in weights["back_prob"]],
    }).sort_values("权重%", ascending=False)
    st.dataframe(bp_df, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("按权重和结构约束生成一注")
    target = st.text_input("目标期号（可以不填）", placeholder="例如 26130")
    if st.button("🎲 生成并保存一注", type="primary"):
        front, back = engine.generate_one(weights)
        engine.save_prediction(weights, target, front, back)
        st.success(f"前区：{front}  |  后区：{back}")

with tab3:
    st.subheader("所有模拟记录")
    rows = engine.get_predictions()
    if not rows:
        st.info("还没有记录。先去“生成一注”点一次按钮。")
    else:
        df = pd.DataFrame(rows, columns=["ID", "目标期号", "前区", "后区", "生成时间", "复盘结果", "前区命中", "后区命中"])
        st.dataframe(df, use_container_width=True, hide_index=True)

with tab4:
    st.subheader("开奖后自动复盘")
    if st.button("🔄 执行复盘"):
        engine.review_all()
        st.success("复盘完成，去“模拟记录”看结果。")
        st.rerun()

with tab5:
    st.subheader("历史开奖记录（真实数据）")
    draws = engine.get_all_draws()
    if not draws:
        st.info("暂无历史数据，请确认 dlt.db 已经上传。")
    else:
        # 把数据库里的数据转成好看的表格
        draw_df = pd.DataFrame(draws, columns=["期号", "开奖日期", "前区1", "前区2", "前区3", "前区4", "前区5", "后区1", "后区2"])
        
        # 拼一个“完整号码”列，方便查看
        draw_df["前区号码"] = draw_df.apply(lambda x: f"{x['前区1']:02d} {x['前区2']:02d} {x['前区3']:02d} {x['前区4']:02d} {x['前区5']:02d}", axis=1)
        draw_df["后区号码"] = draw_df.apply(lambda x: f"{x['后区1']:02d} {x['后区2']:02d}", axis=1)
        
        # 只展示需要的列
        show_df = draw_df[["期号", "开奖日期", "前区号码", "后区号码"]]
        st.dataframe(show_df, use_container_width=True, hide_index=True)