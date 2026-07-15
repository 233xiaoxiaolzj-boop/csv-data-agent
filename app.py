import os

import pandas as pd
import streamlit as st

from agent import generate_code
from executor import execute_code

st.set_page_config(page_title="CSV Data Agent", page_icon="📊", layout="wide")
st.title("📊 CSV 智能数据分析 Agent")
st.caption("上传 CSV，用自然语言提出分析问题。模型生成受限 pandas 代码后在本地执行。")

with st.sidebar:
    st.header("设置")
    model = st.text_input("本地 Ollama 模型", value="deepseek-r1:7b")
    st.caption("免费、本地运行。请先启动 Ollama 和下载所选模型。")

uploaded = st.file_uploader("上传 CSV 文件", type=["csv"])
if not uploaded:
    st.info("请先上传一个 CSV 文件；仓库 sample_data/ 中有可试用的数据。")
    st.stop()

try:
    df = pd.read_csv(uploaded)
except UnicodeDecodeError:
    df = pd.read_csv(uploaded, encoding="gbk")
except Exception as error:
    st.error(f"无法读取 CSV：{error}")
    st.stop()

st.success(f"已读取 {len(df):,} 行 × {len(df.columns)} 列")
with st.expander("预览数据", expanded=True):
    st.dataframe(df.head(20), use_container_width=True)
    st.write(df.dtypes.astype(str).rename("类型"))

question = st.text_area("你想分析什么？", placeholder="例如：按月份统计销售额，并画出趋势图。")
if st.button("开始分析", type="primary", disabled=not question.strip()):
    try:
        with st.spinner("Agent 正在生成分析代码..."):
            code = generate_code(question, df, model)
        st.subheader("生成的分析代码")
        st.code(code, language="python")
        with st.spinner("正在受限环境中执行..."):
            output = execute_code(code, df)
        st.subheader("分析结果")
        if isinstance(output.result, (pd.DataFrame, pd.Series)):
            st.dataframe(output.result, use_container_width=True)
        else:
            st.write(output.result)
        if output.figure:
            st.pyplot(output.figure, clear_figure=True)
    except Exception as error:
        st.error(f"分析未完成：{error}")
