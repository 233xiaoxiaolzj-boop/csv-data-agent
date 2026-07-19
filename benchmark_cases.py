"""Versioned golden cases for reproducible agent evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    category: str
    question: str
    reference_code: str
    require_figure: bool = False


@dataclass(frozen=True)
class SecurityCase:
    name: str
    code: str
    should_reject: bool = True


ANALYSIS_CASES = (
    # 基础统计（8）
    BenchmarkCase("row_count", "基础统计", "这份数据共有多少行？", "result = len(df)"),
    BenchmarkCase(
        "column_count", "基础统计", "这份数据共有多少个字段？", "result = len(df.columns)"
    ),
    BenchmarkCase(
        "total_units", "基础统计", "总销量 units 是多少？", "result = int(df['units'].sum())"
    ),
    BenchmarkCase(
        "average_unit_price",
        "基础统计",
        "平均单价是多少？",
        "result = float(df['unit_price'].mean())",
    ),
    BenchmarkCase(
        "median_units",
        "基础统计",
        "每笔订单销量的中位数是多少？",
        "result = float(df['units'].median())",
    ),
    BenchmarkCase(
        "max_shipping_days",
        "基础统计",
        "最长物流时效是多少天？",
        "result = int(df['shipping_days'].max())",
    ),
    BenchmarkCase(
        "unique_orders",
        "基础统计",
        "一共有多少个不重复的订单号？",
        "result = int(df['order_id'].nunique())",
    ),
    BenchmarkCase(
        "return_count", "基础统计", "退货订单一共有多少笔？", "result = int(df['returned'].sum())"
    ),
    # 分组聚合（10）
    BenchmarkCase(
        "orders_by_region",
        "分组聚合",
        "分别统计各地区的订单数。",
        "result = df.groupby('region').size()",
    ),
    BenchmarkCase(
        "units_by_category",
        "分组聚合",
        "各品类的总销量分别是多少？",
        "result = df.groupby('category')['units'].sum()",
    ),
    BenchmarkCase(
        "avg_price_by_channel",
        "分组聚合",
        "分别计算各渠道的平均单价。",
        "result = df.groupby('channel')['unit_price'].mean()",
    ),
    BenchmarkCase(
        "returns_by_channel",
        "分组聚合",
        "分别统计各渠道的退货订单数。",
        "result = df.groupby('channel')['returned'].sum()",
    ),
    BenchmarkCase(
        "return_rate_by_region",
        "分组聚合",
        "分别计算各地区的退货率。",
        "result = df.groupby('region')['returned'].mean()",
    ),
    BenchmarkCase(
        "shipping_by_category",
        "分组聚合",
        "各品类的平均物流天数是多少？",
        "result = df.groupby('category')['shipping_days'].mean()",
    ),
    BenchmarkCase(
        "orders_by_product",
        "分组聚合",
        "分别统计每个产品的订单数。",
        "result = df.groupby('product').size()",
    ),
    BenchmarkCase(
        "discount_by_channel",
        "分组聚合",
        "各渠道的平均折扣率分别是多少？",
        "result = df.groupby('channel')['discount_rate'].mean()",
    ),
    BenchmarkCase(
        "sales_by_region",
        "分组聚合",
        "各地区销售额分别是多少？销售额等于 units × unit_price。",
        "df['sales'] = df['units'] * df['unit_price']\nresult = df.groupby('region')['sales'].sum()",
    ),
    BenchmarkCase(
        "sales_by_channel",
        "分组聚合",
        "各渠道销售额分别是多少？销售额等于 units × unit_price。",
        "df['sales'] = df['units'] * df['unit_price']\nresult = df.groupby('channel')['sales'].sum()",
    ),
    # 时间分析（8）
    BenchmarkCase(
        "earliest_date",
        "时间分析",
        "数据中最早的订单日期是哪一天？",
        "result = str(pd.to_datetime(df['order_date']).min().date())",
    ),
    BenchmarkCase(
        "latest_date",
        "时间分析",
        "数据中最晚的订单日期是哪一天？",
        "result = str(pd.to_datetime(df['order_date']).max().date())",
    ),
    BenchmarkCase(
        "orders_by_year",
        "时间分析",
        "分别统计每年的订单数。",
        "df['year'] = pd.to_datetime(df['order_date']).dt.year\nresult = df.groupby('year').size()",
    ),
    BenchmarkCase(
        "units_by_year",
        "时间分析",
        "分别统计每年的总销量。",
        "df['year'] = pd.to_datetime(df['order_date']).dt.year\nresult = df.groupby('year')['units'].sum()",
    ),
    BenchmarkCase(
        "units_by_quarter",
        "时间分析",
        "按季度统计总销量。",
        "df['quarter'] = pd.to_datetime(df['order_date']).dt.to_period('Q').astype(str)\nresult = df.groupby('quarter')['units'].sum()",
    ),
    BenchmarkCase(
        "orders_by_month",
        "时间分析",
        "按月份统计订单数。",
        "df['month'] = pd.to_datetime(df['order_date']).dt.to_period('M').astype(str)\nresult = df.groupby('month').size()",
    ),
    BenchmarkCase(
        "sales_by_year",
        "时间分析",
        "按年份统计销售额，销售额等于 units × unit_price。",
        "df['sales'] = df['units'] * df['unit_price']\ndf['year'] = pd.to_datetime(df['order_date']).dt.year\nresult = df.groupby('year')['sales'].sum()",
    ),
    BenchmarkCase(
        "peak_order_month",
        "时间分析",
        "订单数最多的月份是哪一个？请返回 YYYY-MM。",
        "df['month'] = pd.to_datetime(df['order_date']).dt.to_period('M').astype(str)\nresult = str(df.groupby('month').size().idxmax())",
    ),
    # 统计分析（6）
    BenchmarkCase(
        "units_std",
        "统计分析",
        "销量 units 的样本标准差是多少？",
        "result = float(df['units'].std())",
    ),
    BenchmarkCase(
        "price_p90",
        "统计分析",
        "单价的 90% 分位数是多少？",
        "result = float(df['unit_price'].quantile(0.9))",
    ),
    BenchmarkCase(
        "return_rate", "统计分析", "整体退货率是多少？", "result = float(df['returned'].mean())"
    ),
    BenchmarkCase(
        "discounted_share",
        "统计分析",
        "有折扣的订单占比是多少？",
        "result = float((df['discount_rate'] > 0).mean())",
    ),
    BenchmarkCase(
        "shipping_return_corr",
        "统计分析",
        "物流天数与是否退货的皮尔逊相关系数是多少？",
        "result = float(df['shipping_days'].corr(df['returned']))",
    ),
    BenchmarkCase(
        "top_product_units",
        "统计分析",
        "总销量最高的产品名称是什么？",
        "result = str(df.groupby('product')['units'].sum().idxmax())",
    ),
    # 数据质量（4）
    BenchmarkCase(
        "missing_cells",
        "数据质量",
        "整张表一共有多少个缺失单元格？",
        "result = int(df.isna().sum().sum())",
    ),
    BenchmarkCase(
        "duplicate_rows",
        "数据质量",
        "整张表有多少行完全重复的数据？",
        "result = int(df.duplicated().sum())",
    ),
    BenchmarkCase(
        "negative_units",
        "数据质量",
        "units 中小于 0 的异常记录有多少条？",
        "result = int((df['units'] < 0).sum())",
    ),
    BenchmarkCase(
        "category_cardinality",
        "数据质量",
        "category 字段有多少个不同取值？",
        "result = int(df['category'].nunique())",
    ),
    # 可视化（4）
    BenchmarkCase(
        "region_units_chart",
        "可视化",
        "按地区汇总销量并画柱状图，将汇总结果赋给 result。",
        "result = df.groupby('region')['units'].sum()\nplt.figure()\nplt.bar(result.index, result.values)",
        True,
    ),
    BenchmarkCase(
        "monthly_sales_chart",
        "可视化",
        "按月份统计销售额并画趋势图，销售额等于 units × unit_price，将汇总结果赋给 result。",
        "df['sales'] = df['units'] * df['unit_price']\ndf['month'] = pd.to_datetime(df['order_date']).dt.to_period('M').astype(str)\nresult = df.groupby('month')['sales'].sum()\nplt.figure()\nplt.plot(result.index, result.values)",
        True,
    ),
    BenchmarkCase(
        "channel_return_chart",
        "可视化",
        "按渠道汇总退货订单数并画柱状图，将汇总结果赋给 result。",
        "result = df.groupby('channel')['returned'].sum()\nplt.figure()\nplt.bar(result.index, result.values)",
        True,
    ),
    BenchmarkCase(
        "price_histogram",
        "可视化",
        "画出 unit_price 的直方图，并将描述性统计结果赋给 result。",
        "result = df['unit_price'].describe()\nplt.figure()\nplt.hist(df['unit_price'])",
        True,
    ),
)


QUICK_CASES = ANALYSIS_CASES[:8] + ANALYSIS_CASES[-2:]


SECURITY_CASES = (
    SecurityCase("block_import", "import os\nresult = 1"),
    SecurityCase("block_file_read", "result = open('secret.txt').read()"),
    SecurityCase("block_network", "result = requests.get('https://example.com')"),
    SecurityCase("block_eval", "result = eval('1 + 1')"),
    SecurityCase("block_exec", "exec('result = 1')"),
    SecurityCase("block_dunder", "result = df.__class__"),
    SecurityCase("block_csv_write", "df.to_csv('output.csv')\nresult = 1"),
    SecurityCase("block_loop", "result = 0\nfor value in df['units']:\n    result += value"),
    SecurityCase("block_function", "def run():\n    return 1\nresult = run()"),
    SecurityCase("block_while", "result = 0\nwhile True:\n    result += 1"),
    SecurityCase("block_subprocess", "result = subprocess.run('whoami')"),
    SecurityCase("allow_vectorized", "result = int(df['units'].sum())", should_reject=False),
)
