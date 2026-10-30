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

tab1, tab2, tab3, tab4 = st.tabs(["📊 概率总览", "🎲 生成一注", "📋 模拟记录", "🔄 复盘反推"])

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
