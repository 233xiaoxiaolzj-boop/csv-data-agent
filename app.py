from pathlib import Path
from time import perf_counter

import pandas as pd
import streamlit as st

from agent import generate_code_with_trace
from business_analysis import build_business_overview, supports_business_overview
from data_loader import load_csv
from data_profile import build_data_profile
from executor import execute_code
from sql_agent import execute_sql, generate_sql, should_use_python

st.set_page_config(page_title="CSV Data Agent", page_icon="📊", layout="wide")
st.title("📊 CSV 智能数据分析 Agent")
st.caption("上传 CSV，用自然语言提出分析问题。模型生成受限 pandas 代码后在本地执行。")

with st.sidebar:
    st.header("设置")
    model = st.text_input("本地 Ollama 模型", value="qwen2.5-coder:7b")
    engine_mode = st.selectbox("分析引擎", ("自动选择", "只读 SQL", "受控 Python"))
    st.caption("免费、本地运行。请先启动 Ollama 和下载所选模型。")

uploaded = st.file_uploader("上传 CSV 文件", type=["csv"])
demo_clicked = st.button("使用示例电商数据", use_container_width=False)
if demo_clicked:
    st.session_state["use_demo_data"] = True
if uploaded is not None:
    st.session_state["use_demo_data"] = False
use_demo_data = bool(st.session_state.get("use_demo_data", False))

if not uploaded and not use_demo_data:
    st.info("请先上传一个 CSV 文件；仓库 sample_data/ 中有可试用的数据。")
    st.stop()

try:
    if use_demo_data:
        demo_path = Path(__file__).parent / "sample_data" / "ecommerce_sales.csv"
        loaded = load_csv(demo_path.read_bytes())
    else:
        loaded = load_csv(uploaded.getvalue())
    df = loaded.dataframe
except Exception as error:
    st.error(f"无法读取 CSV：{error}")
    st.stop()

st.success(f"已读取 {len(df):,} 行 × {len(df.columns)} 列")
st.caption(f"编码：{loaded.encoding} · 分隔符：{repr(loaded.delimiter)}")
for warning in loaded.warnings:
    st.warning(warning)
profile = build_data_profile(df)
metric_columns = st.columns(4)
metric_columns[0].metric("数据行数", f"{profile.overview['rows']:,}")
metric_columns[1].metric("字段数", profile.overview["columns"])
metric_columns[2].metric("缺失率", f"{profile.overview['missing_rate']}%")
metric_columns[3].metric("重复行", f"{profile.overview['duplicate_rows']:,}")

tab_names = ["数据预览", "质量画像", "字段分布"]
if supports_business_overview(df):
    tab_names.insert(0, "经营看板")
tabs = st.tabs(tab_names)
if supports_business_overview(df):
    business_tab, preview_tab, quality_tab, distribution_tab = tabs
    with business_tab:
        overview = build_business_overview(df)
        st.caption(
            "口径：原价销售额 = 数量 × 单价；折后销售额扣除 discount_rate；"
            "回款销售额进一步剔除 returned=1 的订单。"
        )
        kpi_columns = st.columns(4)
        kpi_columns[0].metric("订单数", f"{overview.kpis['orders']:,}")
        kpi_columns[1].metric("原价销售额", f"¥{overview.kpis['gross_sales']:,.0f}")
        kpi_columns[2].metric("回款销售额", f"¥{overview.kpis['realized_sales']:,.0f}")
        kpi_columns[3].metric("退货率", f"{overview.kpis['return_rate']:.1%}")

        monthly_chart = overview.monthly.set_index("month")[["net_sales", "realized_sales"]]
        monthly_chart = monthly_chart.rename(
            columns={"net_sales": "折后销售额", "realized_sales": "回款销售额"}
        )
        st.markdown("**月度销售趋势**")
        st.line_chart(monthly_chart, use_container_width=True)

        region_column, category_column = st.columns(2)
        with region_column:
            st.markdown("**地区回款销售额**")
            region_chart = overview.regions.set_index("region")[["realized_sales"]]
            st.bar_chart(region_chart.rename(columns={"realized_sales": "回款销售额"}))
        with category_column:
            st.markdown("**品类回款销售额**")
            category_chart = overview.categories.set_index("category")[["realized_sales"]]
            st.bar_chart(category_chart.rename(columns={"realized_sales": "回款销售额"}))

        st.markdown("**自动生成的业务观察**")
        for insight in overview.insights:
            st.markdown(f"- {insight}")
else:
    preview_tab, quality_tab, distribution_tab = tabs
with preview_tab:
    st.dataframe(df.head(20), use_container_width=True)
with quality_tab:
    st.caption(f"估算内存占用：{profile.overview['memory_mb']} MB")
    st.dataframe(profile.columns, use_container_width=True, hide_index=True)
with distribution_tab:
    if not profile.numeric.empty:
        st.markdown("**数值字段**")
        st.dataframe(profile.numeric, use_container_width=True, hide_index=True)
    if not profile.categorical.empty:
        st.markdown("**分类/文本字段**")
        st.dataframe(profile.categorical, use_container_width=True, hide_index=True)

question = st.text_area("你想分析什么？", placeholder="例如：按月份统计销售额，并画出趋势图。")
if st.button("开始分析", type="primary", disabled=not question.strip()):
    try:
        started_at = perf_counter()
        use_python = engine_mode == "受控 Python" or (
            engine_mode == "自动选择" and should_use_python(question)
        )
        if use_python:
            with st.spinner("Agent 正在生成分析代码..."):
                trace = generate_code_with_trace(question, df, model)
            st.subheader("生成的受控 Python")
            st.code(trace.code, language="python")
            audit_columns = st.columns(4)
            audit_columns[0].metric("引擎", "Python")
            audit_columns[1].metric("生成尝试", trace.attempts)
            audit_columns[2].metric("自动修复", "是" if trace.repaired else "否")
            audit_columns[3].metric("可信回退", "是" if trace.used_fallback else "否")
            with st.spinner("正在受限环境中执行..."):
                output = execute_code(trace.code, df)
            result = output.result
            figure = output.figure
        else:
            with st.spinner("Agent 正在生成只读 SQL..."):
                trace = generate_sql(question, df, model)
                output = execute_sql(trace.sql, df)
            st.subheader("生成的只读 SQL")
            st.code(output.sql, language="sql")
            audit_columns = st.columns(4)
            audit_columns[0].metric("引擎", "DuckDB")
            audit_columns[1].metric("生成尝试", trace.attempts)
            audit_columns[2].metric("自动修复", "是" if trace.repaired else "否")
            audit_columns[3].metric("查询耗时", f"{output.latency_seconds:.3f}s")
            result = output.result
            figure = None

        st.subheader("分析结果")
        if isinstance(result, (pd.DataFrame, pd.Series)):
            st.dataframe(result, use_container_width=True)
        else:
            st.write(result)
        if figure:
            st.pyplot(figure, clear_figure=True)
        st.caption(f"本次分析耗时：{perf_counter() - started_at:.2f} 秒")
    except Exception as error:
        st.error(f"分析未完成：{error}")
