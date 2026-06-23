# -*- coding: utf-8 -*-
"""
A股自选股监控网页生成程序
输出位置：docs/index.html
适用于 GitHub Actions + GitHub Pages
"""

import os
import time
import random
import traceback
import datetime

import pandas as pd
import akshare as ak


# =========================
# 1. 股票池
# =========================

STOCK_LIST = [
    ("688008", "澜起科技"),
    ("688300", "联瑞新材"),
    ("688981", "中芯国际"),
    ("688041", "海光信息"),
    ("688347", "华虹公司"),
    ("002463", "沪电股份"),
    ("002916", "深南电路"),
    ("300308", "中际旭创"),
    ("300502", "新易盛"),
    ("300394", "天孚通信"),
    ("601138", "工业富联"),
    ("603986", "兆易创新"),
    ("600584", "长电科技"),
    ("688012", "中微公司"),
    ("688072", "拓荆科技"),
    ("002371", "北方华创"),
    ("688120", "华海清科"),
    ("000977", "浪潮信息"),
    ("603019", "中科曙光"),
    ("300476", "胜宏科技"),
    ("002938", "鹏鼎控股"),
    ("600183", "生益科技"),
    ("688183", "生益电子"),
    ("002384", "东山精密"),
    ("300604", "长川科技"),
    ("688256", "寒武纪"),
    ("688126", "沪硅产业"),
    ("688525", "佰维存储"),
    ("688111", "金山办公"),
    ("600536", "中国软件"),
]


# =========================
# 2. 输出目录
# =========================

OUTPUT_DIR = "docs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")


# =========================
# 3. 工具函数
# =========================

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(x, default=0.0):
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


def format_amount(x):
    try:
        x = float(x)
        if x >= 100000000:
            return f"{x / 100000000:.2f}亿"
        elif x >= 10000:
            return f"{x / 10000:.2f}万"
        else:
            return f"{x:.0f}"
    except Exception:
        return x


# =========================
# 4. 获取行情，带重试
# =========================

def get_market_data():
    """
    使用 AKShare 获取 A 股实时行情。
    加入重试，避免 GitHub Actions 偶发网络断开导致失败。
    """

    need_cols = [
        "代码", "名称", "最新价", "涨跌幅", "涨跌额",
        "成交额", "振幅", "最高", "最低", "今开", "昨收",
        "量比", "换手率"
    ]

    last_error = None

    for i in range(5):
        try:
            print(f"第 {i + 1} 次尝试获取 A 股实时行情...")

            # 随机等待，降低被接口拒绝概率
            time.sleep(random.uniform(3, 8))

            df = ak.stock_zh_a_spot_em()

            if df is None or df.empty:
                raise RuntimeError("AKShare 返回空数据")

            exist_cols = [c for c in need_cols if c in df.columns]
            df = df[exist_cols].copy()

            if "代码" not in df.columns:
                raise RuntimeError(f"行情数据缺少代码字段，当前字段为：{list(df.columns)}")

            print(f"行情获取成功，共 {len(df)} 条。")
            return df

        except Exception as e:
            last_error = e
            print(f"第 {i + 1} 次获取失败：{repr(e)}")
            print(traceback.format_exc())

            # 每次失败后等待更久
            time.sleep(20 + i * 20)

    raise RuntimeError(f"连续 5 次获取行情失败：{repr(last_error)}")


# =========================
# 5. 判断级别和提示
# =========================

def make_signal(row):
    pct = safe_float(row.get("涨跌幅", 0))
    volume_ratio = safe_float(row.get("量比", 0))

    if pct >= 7:
        return "涨幅过大，谨慎追高"
    elif 4 <= pct < 7:
        return "强势明显，只适合小仓观察"
    elif 2 <= pct < 4 and volume_ratio >= 1.2:
        return "量价较好，重点观察"
    elif 0 <= pct < 2:
        return "走势温和，可继续盯"
    elif -2 <= pct < 0:
        return "小幅回调，等企稳"
    elif -4 <= pct < -2:
        return "调整偏弱，暂缓"
    else:
        return "跌幅较大，先不急接"


def make_level(row):
    pct = safe_float(row.get("涨跌幅", 0))
    volume_ratio = safe_float(row.get("量比", 0))
    turnover = safe_float(row.get("换手率", 0))

    if 1.5 <= pct <= 5.5 and volume_ratio >= 1.2:
        return "A"
    elif -2 <= pct < 1.5:
        return "B"
    elif 1.5 <= pct <= 6 and turnover >= 2:
        return "B"
    else:
        return "C"


# =========================
# 6. 生成正常网页
# =========================

def generate_html(df):
    update_time = now_str()

    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>A股短线观察表</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", Arial, sans-serif;
            margin: 24px;
            background: #f6f8fa;
            color: #24292f;
        }}
        h1 {{
            margin-bottom: 6px;
        }}
        .time {{
            color: #666;
            margin-bottom: 20px;
        }}
        .note {{
            background: #fff8c5;
            border: 1px solid #eac54f;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            line-height: 1.7;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        th, td {{
            border-bottom: 1px solid #eaeef2;
            padding: 9px 8px;
            text-align: center;
            font-size: 14px;
            white-space: nowrap;
        }}
        th {{
            background: #0969da;
            color: white;
            position: sticky;
            top: 0;
        }}
        tr:hover {{
            background: #f1f8ff;
        }}
        .red {{
            color: #d1242f;
            font-weight: bold;
        }}
        .green {{
            color: #1a7f37;
            font-weight: bold;
        }}
        .level-a {{
            background: #ffecec;
            color: #cf222e;
            font-weight: bold;
            border-radius: 4px;
            padding: 3px 7px;
        }}
        .level-b {{
            background: #fff8c5;
            color: #7d4e00;
            font-weight: bold;
            border-radius: 4px;
            padding: 3px 7px;
        }}
        .level-c {{
            background: #eaeef2;
            color: #57606a;
            font-weight: bold;
            border-radius: 4px;
            padding: 3px 7px;
        }}
        .footer {{
            margin-top: 18px;
            color: #666;
            font-size: 13px;
            line-height: 1.6;
        }}
        .table-wrap {{
            overflow-x: auto;
        }}
    </style>
</head>
<body>
    <h1>A股短线观察表</h1>
    <div class="time">更新时间：{update_time}</div>

    <div class="note">
        本页面由 GitHub Actions 自动生成，结果仅用于盘面观察，不构成投资建议。<br>
        简单理解：A = 重点观察，B = 等待机会，C = 谨慎处理。
    </div>

    <div class="table-wrap">
    <table>
        <thead>
            <tr>
                <th>级别</th>
                <th>代码</th>
                <th>名称</th>
                <th>最新价</th>
                <th>涨跌幅</th>
                <th>涨跌额</th>
                <th>今开</th>
                <th>最高</th>
                <th>最低</th>
                <th>昨收</th>
                <th>量比</th>
                <th>换手率</th>
                <th>成交额</th>
                <th>操作提示</th>
            </tr>
        </thead>
        <tbody>
"""

    for _, row in df.iterrows():
        pct_float = safe_float(row.get("涨跌幅", 0))
        pct_class = "red" if pct_float >= 0 else "green"

        level = row.get("级别", "C")
        if level == "A":
            level_class = "level-a"
        elif level == "B":
            level_class = "level-b"
        else:
            level_class = "level-c"

        html += f"""
            <tr>
                <td><span class="{level_class}">{level}</span></td>
                <td>{row.get("代码", "")}</td>
                <td>{row.get("名称", "")}</td>
                <td>{row.get("最新价", "")}</td>
                <td class="{pct_class}">{row.get("涨跌幅", "")}%</td>
                <td>{row.get("涨跌额", "")}</td>
                <td>{row.get("今开", "")}</td>
                <td>{row.get("最高", "")}</td>
                <td>{row.get("最低", "")}</td>
                <td>{row.get("昨收", "")}</td>
                <td>{row.get("量比", "")}</td>
                <td>{row.get("换手率", "")}%</td>
                <td>{row.get("成交额", "")}</td>
                <td>{row.get("操作提示", "")}</td>
            </tr>
"""

    html += """
        </tbody>
    </table>
    </div>

    <div class="footer">
        说明：本表按预设股票池生成，判断规则较简单，主要用于快速筛选盘面强弱。实际操作仍需结合指数、板块、成交量、分时走势和自身仓位。
    </div>
</body>
</html>
"""
    return html


# =========================
# 7. 生成错误说明网页
# =========================

def generate_error_html(error_message):
    update_time = now_str()

    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>A股短线观察表</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="font-family: Microsoft YaHei, Arial; padding: 30px; line-height: 1.8;">
    <h1>A股短线观察表</h1>
    <p>更新时间：{update_time}</p>

    <h2 style="color:#d1242f;">本次行情获取失败</h2>

    <p>
        这通常不是 GitHub Pages 或 docs 路径错误，而是 AKShare / 东方财富实时行情接口
        在 GitHub Actions 服务器上临时断开或访问不稳定。
    </p>

    <p>
        你可以稍后在 Actions 里手动重新运行一次：
        <strong>Actions → stock-watch → Run workflow</strong>
    </p>

    <h3>错误信息</h3>
    <pre style="background:#f6f8fa; padding:15px; white-space:pre-wrap; border:1px solid #d0d7de;">
{error_message}
    </pre>
</body>
</html>
"""
    return html


# =========================
# 8. 主程序
# =========================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    try:
        market_df = get_market_data()

        stock_codes = [code for code, _ in STOCK_LIST]
        name_map = {code: name for code, name in STOCK_LIST}
        order_map = {code: i for i, (code, _) in enumerate(STOCK_LIST)}

        watch_df = market_df[market_df["代码"].isin(stock_codes)].copy()

        if watch_df.empty:
            raise RuntimeError("没有匹配到股票池中的股票，可能是行情接口字段变化或数据为空。")

        watch_df["排序"] = watch_df["代码"].map(order_map)
        watch_df = watch_df.sort_values("排序").drop(columns=["排序"])

        watch_df["名称"] = watch_df["代码"].map(name_map).fillna(watch_df["名称"])

        watch_df["操作提示"] = watch_df.apply(make_signal, axis=1)
        watch_df["级别"] = watch_df.apply(make_level, axis=1)

        if "成交额" in watch_df.columns:
            watch_df["成交额"] = watch_df["成交额"].apply(format_amount)

        html = generate_html(watch_df)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"网页已生成：{OUTPUT_FILE}")
        print(f"共生成股票数量：{len(watch_df)}")

    except Exception as e:
        error_message = repr(e) + "\n\n" + traceback.format_exc()

        html = generate_error_html(error_message)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"行情获取失败，但已生成错误说明页：{OUTPUT_FILE}")
        print(error_message)

        # 不再 raise，避免 GitHub Actions 直接红叉
        return


if __name__ == "__main__":
    main()
