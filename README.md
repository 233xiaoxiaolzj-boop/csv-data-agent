# CSV 智能数据分析 Agent

一个面向 CSV 文件的轻量数据分析 Agent：用户用自然语言提问，模型生成 pandas 分析代码，在受限环境中执行并展示表格和图表。

## 功能

- CSV 上传、预览与字段类型展示
- LLM 自动生成 pandas / numpy / matplotlib 分析代码
- 代码安全校验：阻止导入、文件读写、网络访问和危险内置函数
- 展示可审计的生成代码、分析结果与图表
- 内含样例销售数据和执行器单元测试

## 快速开始

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
$env:OPENAI_API_KEY = "你的_API_Key"
streamlit run app.py
```

上传 `sample_data/sales.csv`，然后尝试：`按月份统计总销售额（units × unit_price），并画出趋势图。`

## 架构

```text
CSV + 用户问题 → LLM 生成代码 → AST 安全校验 → 受限执行 → 表格 / 图表
```

## 测试

```bash
pip install -r requirements-dev.txt
pytest
```

## 限制与安全说明

这不是严格隔离的沙箱。当前版本通过 AST 拦截明显危险语法，仅适合作为本地教学和作品集项目。生产场景应将代码放进 Docker/微虚拟机中执行，并补充超时、内存和网络隔离。

## 后续可迭代

1. 加入“执行报错后自动修复一次”的循环。
2. 建立 20 条数据分析任务集，记录成功率、平均时延与成本。
3. 使用 Docker 沙箱和结构化输出，进一步强化可靠性。
