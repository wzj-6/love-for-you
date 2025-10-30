# -*- coding: utf-8 -*-
"""
嘉亿医药客户与商品价值四象限分析系统（2025年H1） - 优化专业版
- 新增 A类 vs C类对比分析
- 报告内嵌超链接至Excel明细
- 图表与报告同目录，图片正常显示
"""

import pandas as pd
import os
import matplotlib.pyplot as plt
import seaborn as sns

# 设置中文字体
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

# ==============================
# 1. 配置路径
# ==============================
INVENTORY_FILE = r"D:\Users\工作资料\资料\数据分析\明源\嘉亿存进销202501-06.csv"
SALES_FILE = r"D:\Users\工作资料\资料\数据分析\明源\嘉亿销售流向202501-06.csv"

for f in [INVENTORY_FILE, SALES_FILE]:
    if not os.path.exists(f):
        raise FileNotFoundError(f"❌ 文件不存在: {f}")

OUTPUT_DIR = r"D:\Users\wzj\analyze\scripts\Data analysis"
os.makedirs(OUTPUT_DIR, exist_ok=True)
FIG_DIR = OUTPUT_DIR  # 图表与报告同目录

# ==============================
# 2. 数据加载与清洗
# ==============================
print("📥 加载并清洗数据...")

sales = pd.read_csv(SALES_FILE)
inventory = pd.read_csv(INVENTORY_FILE)

# 日期处理（可选）
date_col = next((c for c in ["日期", "销售日期"] if c in sales.columns), None)
if date_col:
    sales[date_col] = pd.to_datetime(sales[date_col], errors="coerce")
    sales = sales.dropna(subset=[date_col])

# 数值转换
for col in ["数量", "含税价", "含税金额"]:
    if col in sales.columns:
        sales[col] = pd.to_numeric(sales[col], errors="coerce")
if "最后含税进价" in inventory.columns:
    inventory["最后含税进价"] = pd.to_numeric(
        inventory["最后含税进价"], errors="coerce"
    )

sales = sales[(sales["数量"] > 0) & (sales["含税金额"] >= 0)].copy()
inventory = inventory.dropna(subset=["商品编号"]).copy()

# 成本匹配
cost_map = inventory[["商品编号", "最后含税进价"]].drop_duplicates("商品编号")
sales = sales.merge(cost_map, on="商品编号", how="left")
sales["最后含税进价"] = sales["最后含税进价"].fillna(sales["含税价"] * 0.7)
sales["毛利"] = sales["含税金额"] - (sales["数量"] * sales["最后含税进价"])

# ==============================
# 3. 聚合
# ==============================
if "生产企业" in sales.columns:
    sales = sales.drop("生产企业", axis=1)

upstream = sales.merge(
    inventory[["商品编号", "生产企业"]].drop_duplicates(), on="商品编号", how="left"
)

upstream_agg = (
    upstream.groupby("生产企业", dropna=False)
    .agg(总销售额=("含税金额", "sum"), 总毛利=("毛利", "sum"))
    .reset_index()
    .fillna({"生产企业": "未知"})
)

downstream_agg = (
    sales.groupby("单位名称", dropna=False)
    .agg(总销售额=("含税金额", "sum"), 总毛利=("毛利", "sum"))
    .reset_index()
    .fillna({"单位名称": "未知"})
)

product_agg = (
    sales.groupby(["商品编号", "商品名称"], dropna=False)
    .agg(总销售额=("含税金额", "sum"), 总毛利=("毛利", "sum"))
    .reset_index()
)


# ==============================
# 4. 分类函数：ABC + 四象限
# ==============================
def classify_entities(df, total_sales):
    df = df.copy()
    df["毛利率"] = df["总毛利"] / (df["总销售额"] + 1e-8)
    df = df.sort_values("总销售额", ascending=False).reset_index(drop=True)
    df["累计占比"] = df["总销售额"].cumsum() / total_sales
    df["ABC分类"] = df["累计占比"].apply(
        lambda x: "A类" if x <= 0.8 else ("B类" if x <= 0.95 else "C类")
    )

    sales_med = df["总销售额"].median()
    margin_med = df["毛利率"].median()

    def quad(row):
        hs = row["总销售额"] >= sales_med
        hm = row["毛利率"] >= margin_med
        if hs and hm:
            return "明星"
        elif not hs and hm:
            return "潜力"
        elif hs and not hm:
            return "现金牛"
        else:
            return "淘汰"

    df["四象限分类"] = df.apply(quad, axis=1)
    return df, sales_med, margin_med


# 应用分类
total_up = upstream_agg["总销售额"].sum()
upstream_res, up_sales_med, up_margin_med = classify_entities(upstream_agg, total_up)

total_down = downstream_agg["总销售额"].sum()
downstream_res, down_sales_med, down_margin_med = classify_entities(
    downstream_agg, total_down
)

total_prod = product_agg["总销售额"].sum()
product_res, prod_sales_med, prod_margin_med = classify_entities(
    product_agg, total_prod
)

# 添加排名
for df in [upstream_res, downstream_res, product_res]:
    df["排名"] = range(1, len(df) + 1)


# ==============================
# 5. 绘图函数
# ==============================
def plot_quadrant(df, title, filename, sales_med, margin_med):
    plt.figure(figsize=(8, 6))
    colors = {
        "明星": "#2E8B57",
        "潜力": "#4682B4",
        "现金牛": "#DAA520",
        "淘汰": "#CD5C5C",
    }
    sns.scatterplot(
        data=df,
        x="总销售额",
        y="毛利率",
        hue="四象限分类",
        palette=colors,
        s=60,
        alpha=0.8,
    )
    plt.axvline(x=sales_med, color="gray", linestyle="--", linewidth=1)
    plt.axhline(y=margin_med, color="gray", linestyle="--", linewidth=1)
    plt.title(title, fontsize=14, weight="bold")
    plt.xlabel("总销售额（元）")
    plt.ylabel("毛利率")
    plt.legend(title="四象限")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, filename), dpi=200, bbox_inches="tight")
    plt.close()


def plot_abc_pie(df, title, filename):
    abc_counts = df["ABC分类"].value_counts()
    plt.figure(figsize=(6, 6))
    colors = {"A类": "#FF6347", "B类": "#4682B4", "C类": "#32CD32"}
    plt.pie(
        abc_counts,
        labels=abc_counts.index,
        autopct="%1.1f%%",
        colors=[colors.get(k, "#808080") for k in abc_counts.index],
        startangle=90,
    )
    plt.title(title, fontsize=14, weight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, filename), dpi=200, bbox_inches="tight")
    plt.close()


# 绘图
plot_quadrant(
    downstream_res,
    "下游客户四象限分布",
    "客户_四象限.png",
    down_sales_med,
    down_margin_med,
)
plot_quadrant(
    product_res, "商品四象限分布", "商品_四象限.png", prod_sales_med, prod_margin_med
)
plot_quadrant(
    upstream_res, "上游厂家四象限分布", "厂家_四象限.png", up_sales_med, up_margin_med
)

plot_abc_pie(downstream_res, "下游客户ABC分类占比", "客户_ABC.png")
plot_abc_pie(product_res, "商品ABC分类占比", "商品_ABC.png")
plot_abc_pie(upstream_res, "上游厂家ABC分类占比", "厂家_ABC.png")


# ==============================
# 6. A类 vs C类对比分析
# ==============================
def calc_a_vs_c(df):
    a_df = df[df["ABC分类"] == "A类"]
    c_df = df[df["ABC分类"] == "C类"]
    total_sales = df["总销售额"].sum()
    return {
        "a_count": len(a_df),
        "c_count": len(c_df),
        "a_avg_sales": a_df["总销售额"].mean() if not a_df.empty else 0,
        "c_avg_sales": c_df["总销售额"].mean() if not c_df.empty else 0,
        "a_avg_margin": a_df["毛利率"].mean() if not a_df.empty else 0,
        "c_avg_margin": c_df["毛利率"].mean() if not c_df.empty else 0,
        "a_sales_share": a_df["总销售额"].sum() / total_sales if total_sales > 0 else 0,
        "c_sales_share": c_df["总销售额"].sum() / total_sales if total_sales > 0 else 0,
    }


cust_a_c = calc_a_vs_c(downstream_res)
prod_a_c = calc_a_vs_c(product_res)
up_a_c = calc_a_vs_c(upstream_res)

# ==============================
# 7. 生成Excel明细（供报告超链接）
# ==============================
excel_path = os.path.join(OUTPUT_DIR, "ABC定级明细.xlsx")
with pd.ExcelWriter(excel_path, engine="openpyxl") as w:
    for name, df in [
        ("上游厂家", upstream_res),
        ("下游客户", downstream_res),
        ("商品", product_res),
    ]:
        for cls in ["A类", "B类", "C类"]:
            sheet_name = f"{cls}_{name}"
            df[df["ABC分类"] == cls].to_excel(w, sheet_name=sheet_name, index=False)


# ==============================
# 8. 格式化表格函数
# ==============================
def format_table(df, cols=None):
    if df.empty:
        return "（无数据）"
    df_show = df.copy()
    for col in ["总销售额", "总毛利"]:
        if col in df_show.columns:
            df_show[col] = df_show[col].apply(lambda x: f"¥{x:,.0f}")
    if "毛利率" in df_show.columns:
        df_show["毛利率"] = df_show["毛利率"].apply(lambda x: f"{x:.1%}")
    if cols:
        df_show = df_show[cols]
    return df_show.to_string(index=False)


# ==============================
# 9. 生成Markdown报告
# ==============================
report = f"""# 📊 嘉亿医药2025年H1客户与商品价值四象限分析报告（优化专业版）

> **分析周期**：2025年1月 - 2025年6月  
> **数据来源**：嘉亿销售流向 + 进销存系统  
> **核心方法**：四象限模型 + ABC分类  
> 📥 **明细数据**：[点击查看ABC定级明细表（Excel）](ABC定级明细.xlsx)

---

## 一、A类 vs C类对比分析

### 1. 下游客户对比
| 指标 | A类客户 | C类客户 | 差距倍数 |
|------|--------|--------|----------|
| 客户数量 | {cust_a_c['a_count']:,} | {cust_a_c['c_count']:,} | — |
| 平均销售额 | ¥{cust_a_c['a_avg_sales']:,.0f} | ¥{cust_a_c['c_avg_sales']:,.0f} | **{(cust_a_c['a_avg_sales'] / (cust_a_c['c_avg_sales'] + 1e-6)):.0f}×** |
| 平均毛利率 | {cust_a_c['a_avg_margin']:.1%} | {cust_a_c['c_avg_margin']:.1%} | **+{(cust_a_c['a_avg_margin'] - cust_a_c['c_avg_margin']):.1%}** |
| 销售额占比 | {cust_a_c['a_sales_share']:.1%} | {cust_a_c['c_sales_share']:.1%} | — |

### 2. 商品对比
| 指标 | A类商品 | C类商品 | 差距倍数 |
|------|--------|--------|----------|
| 商品数量 | {prod_a_c['a_count']:,} | {prod_a_c['c_count']:,} | — |
| 平均销售额 | ¥{prod_a_c['a_avg_sales']:,.0f} | ¥{prod_a_c['c_avg_sales']:,.0f} | **{(prod_a_c['a_avg_sales'] / (prod_a_c['c_avg_sales'] + 1e-6)):.0f}×** |
| 平均毛利率 | {prod_a_c['a_avg_margin']:.1%} | {prod_a_c['c_avg_margin']:.1%} | **+{(prod_a_c['a_avg_margin'] - prod_a_c['c_avg_margin']):.1%}** |

### 3. 上游厂家对比
| 指标 | A类厂家 | C类厂家 | 差距倍数 |
|------|--------|--------|----------|
| 厂家数量 | {up_a_c['a_count']:,} | {up_a_c['c_count']:,} | — |
| 平均销售额 | ¥{up_a_c['a_avg_sales']:,.0f} | ¥{up_a_c['c_avg_sales']:,.0f} | **{(up_a_c['a_avg_sales'] / (up_a_c['c_avg_sales'] + 1e-6)):.0f}×** |
| 平均毛利率 | {up_a_c['a_avg_margin']:.1%} | {up_a_c['c_avg_margin']:.1%} | **+{(up_a_c['a_avg_margin'] - up_a_c['c_avg_margin']):.1%}** |

---

## 二、可视化图表

### 下游客户
[客户四象限](客户_四象限.png)  
[客户ABC](客户_ABC.png)

### 商品
[商品四象限](商品_四象限.png)  
[商品ABC](商品_ABC.png)

### 上游厂家
[厂家四象限](厂家_四象限.png)  
[厂家ABC](厂家_ABC.png)

---

## 三、A类实体TOP3

### 🔹 上游厂家（A类）
{format_table(upstream_res[upstream_res["ABC分类"] == "A类"].head(3), ["生产企业", "总销售额", "毛利率", "排名"])}

### 🔸 下游客户（A类）
{format_table(downstream_res[downstream_res["ABC分类"] == "A类"].head(3), ["单位名称", "总销售额", "毛利率", "排名"])}

### 🔻 商品（A类）
{format_table(product_res[product_res["ABC分类"] == "A类"].head(3), ["商品名称", "总销售额", "毛利率", "排名"])}

> **报告生成时间**：{pd.Timestamp.now().strftime('%Y年%m月%d日 %H:%M')}
"""

# 保存报告
report_path = os.path.join(OUTPUT_DIR, "嘉亿医药2025H1四象限分析报告.md")
with open(report_path, "w", encoding="utf-8") as f:
    f.write(report)

print("\n✅ 报告与图表生成成功！")
print("📄 报告路径：", report_path)
print("📁 Excel路径：", excel_path)
print("🖼 图表路径：", FIG_DIR)
