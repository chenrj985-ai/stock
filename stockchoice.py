# -*- coding: utf-8 -*-
"""
A股自选股监控网页生成程序
输出位置：docs/index.html

特点：
1. 不再使用 AKShare，避免东方财富接口在 GitHub Actions 上频繁断开
2. 主数据源：新浪行情接口
3. 备用数据源：腾讯行情接口
4. 自动输出 docs/index.html，供 GitHub Pages 显示
"""

import os
import time
import random
import traceback
import datetime
from typing import Dict, List, Tuple

import requests
import pandas as pd


# =========================
# 1. 股票池
# =========================

STOCK_LIST = [
    ("002371", "北方华创"),
    ("688012", "中微公司"),
    ("688072", "拓荆科技"),
    ("688120", "华海清科"),
    ("688037", "芯源微"),
    ("002916", "深南电路"),
    ("300476", "胜宏科技"),
    ("002463", "沪电股份"),
    ("600584", "长电科技"),
    ("688041", "海光信息"),
    ("603019", "中科曙光"),
    ("001309", "德明利"),
    ("600183", "生益科技"),
    ("688981", "中芯国际"),
    ("688008", "澜起科技"),
    ("603986", "兆易创新"),
    ("300661", "圣邦股份"),
    ("688052", "纳芯微"),
    ("603893", "瑞芯微"),
    ("688300", "联瑞新材"),
    ("300308", "中际旭创"),
    ("300502", "新易盛"),
    ("300394", "天孚通信"),
    ("002281", "光迅科技"),
    ("601138", "工业富联"),
    ("000977", "浪潮信息"),
    ("688047", "龙芯中科"),
    ("688256", "寒武纪"),
    ("300496", "中科创达"),
    ("002049", "紫光国微"),
    ("002384", "东山精密"),
    ("603228", "景旺电子"),
    ("002436", "兴森科技"),
    ("688126", "沪硅产业"),
    ("688141", "杰华特"),
    ("688082", "盛美上海"),
    ("688627", "精智达"),
    ("688668", "鼎通科技"),
    ("002130", "沃尔核材"),
]


# =========================
# 2. 输出目录
# =========================

OUTPUT_DIR = "docs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")


# =========================
# 3. 工具函数
# =========================

def now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_market_prefix(code: str) -> str:
    """
    A股市场前缀：
    6、688、689 开头一般为上海 sh
    0、2、3 开头一般为深圳 sz
    """
    if code.startswith("6"):
        return "sh"
    return "sz"


def safe_float(x, default=0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return float(x)
    except Exception:
        return default


def format_amount(x) -> str:
    value = safe_float(x, 0)
    if value >= 100000000:
        return f"{value / 100000000:.2f}亿"
    if value >= 10000:
        return f"{value / 10000:.2f}万"
    return f"{value:.0f}"


def request_text(url: str, headers: Dict[str, str], encoding: str = "gbk", timeout: int = 15) -> str:
    """
    带重试的网页文本请求。
    """
    last_error = None

    for i in range(5):
        try:
            print(f"请求第 {i + 1} 次：{url[:100]}...")
            time.sleep(random.uniform(1.5, 4.0))

            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            resp.encoding = encoding

            text = resp.text
            if not text or len(text.strip()) < 20:
                raise RuntimeError("接口返回内容过短或为空")

            return text

        except Exception as e:
            last_error = e
            print(f"请求失败：{repr(e)}")
            time.sleep(8 + i * 8)

    raise RuntimeError(f"连续 5 次请求失败：{repr(last_error)}")


# =========================
# 4. 新浪行情接口
# =========================

def get_data_from_sina(stock_list: List[Tuple[str, str]]) -> pd.DataFrame:
    """
    新浪行情接口。
    返回字段较稳定：
    name, open, pre_close, price, high, low, volume, amount, date, time
    """

    symbols = []
    for code, _ in stock_list:
        prefix = get_market_prefix(code)
        symbols.append(prefix + code)

    url = "https://hq.sinajs.cn/list=" + ",".join(symbols)

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn/",
        "Accept": "*/*",
        "Connection": "close",
    }

    text = request_text(url, headers=headers, encoding="gbk", timeout=20)

    rows = []
    name_map = {code: name for code, name in stock_list}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or '="' not in line:
            continue

        try:
            left, right = line.split('="', 1)
            symbol = left.split("_")[-1]
            code = symbol[-6:]
            content = right.rstrip('";')
            fields = content.split(",")

            if len(fields) < 32:
                print(f"新浪字段不足，跳过：{line[:80]}")
                continue

            name = fields[0] or name_map.get(code, "")
            open_price = safe_float(fields[1])
            pre_close = safe_float(fields[2])
            price = safe_float(fields[3])
            high = safe_float(fields[4])
            low = safe_float(fields[5])
            volume = safe_float(fields[8])
            amount = safe_float(fields[9])
            date = fields[30]
            quote_time = fields[31]

            if price <= 0 and pre_close > 0:
                price = pre_close

            change = price - pre_close if pre_close > 0 else 0
            pct = change / pre_close * 100 if pre_close > 0 else 0

            rows.append({
                "代码": code,
                "名称": name_map.get(code, name),
                "最新价": round(price, 2),
                "涨跌幅": round(pct, 2),
                "涨跌额": round(change, 2),
                "今开": round(open_price, 2),
                "最高": round(high, 2),
                "最低": round(low, 2),
                "昨收": round(pre_close, 2),
                "成交量": volume,
                "成交额": amount,
                "量比": "",
                "换手率": "",
                "行情时间": f"{date} {quote_time}",
                "数据源": "新浪",
            })

        except Exception as e:
            print(f"解析新浪行情失败：{repr(e)}")
            print(line[:120])

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError("新浪接口没有解析到有效股票数据")

    return df


# =========================
# 5. 腾讯行情接口，备用
# =========================

def get_data_from_tencent(stock_list: List[Tuple[str, str]]) -> pd.DataFrame:
    """
    腾讯行情接口，作为备用。
    腾讯接口返回纯文本，字段用 ~ 分隔。
    """

    symbols = []
    for code, _ in stock_list:
        prefix = get_market_prefix(code)
        symbols.append(prefix + code)

    url = "https://qt.gtimg.cn/q=" + ",".join(symbols)

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://gu.qq.com/",
        "Accept": "*/*",
        "Connection": "close",
    }

    text = request_text(url, headers=headers, encoding="gbk", timeout=20)

    rows = []
    name_map = {code: name for code, name in stock_list}

    for raw_line in text.split(";"):
        line = raw_line.strip()
        if not line or '="' not in line:
            continue

        try:
            left, right = line.split('="', 1)
            symbol = left.split("_")[-1]
            code = symbol[-6:]
            content = right.rstrip('"')
            fields = content.split("~")

            if len(fields) < 40:
                print(f"腾讯字段不足，跳过：{line[:80]}")
                continue

            name = fields[1]
            price = safe_float(fields[3])
            pre_close = safe_float(fields[4])
            open_price = safe_float(fields[5])
            high = safe_float(fields[33])
            low = safe_float(fields[34])
            change = safe_float(fields[31])
            pct = safe_float(fields[32])
            amount = safe_float(fields[37]) * 10000 if safe_float(fields[37]) > 0 else 0
            turnover = fields[38] if len(fields) > 38 else ""

            if price <= 0 and pre_close > 0:
                price = pre_close

            rows.append({
                "代码": code,
                "名称": name_map.get(code, name),
                "最新价": round(price, 2),
                "涨跌幅": round(pct, 2),
                "涨跌额": round(change, 2),
                "今开": round(open_price, 2),
                "最高": round(high, 2),
                "最低": round(low, 2),
                "昨收": round(pre_close, 2),
                "成交量": "",
                "成交额": amount,
                "量比": "",
                "换手率": turnover,
                "行情时间": "",
                "数据源": "腾讯",
            })

        except Exception as e:
            print(f"解析腾讯行情失败：{repr(e)}")
            print(line[:120])

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError("腾讯接口没有解析到有效股票数据")

    return df


# =========================
# 6. 统一获取行情
# =========================

def get_market_data() -> pd.DataFrame:
    """
    先用新浪。
    新浪失败后，自动切换腾讯。
    """

    errors = []

    try:
        print("开始使用新浪接口获取行情...")
        df = get_data_from_sina(STOCK_LIST)
        print(f"新浪接口成功，获取 {len(df)} 只股票。")
        return df
    except Exception as e:
        errors.append("新浪接口失败：" + repr(e))
        print(errors[-1])
        print(traceback.format_exc())

    try:
        print("开始使用腾讯接口获取行情...")
        df = get_data_from_tencent(STOCK_LIST)
        print(f"腾讯接口成功，获取 {len(df)} 只股票。")
        return df
    except Exception as e:
        errors.append("腾讯接口失败：" + repr(e))
        print(errors[-1])
        print(traceback.format_exc())

    raise RuntimeError("\n".join(errors))


# =========================
# 7. 判断级别和提示
# =========================

def make_signal(row) -> str:
    pct = safe_float(row.get("涨跌幅", 0))

    if pct >= 7:
        return "涨幅过大，谨慎追高"
    elif 4 <= pct < 7:
        return "强势明显，只适合小仓观察"
    elif 2 <= pct < 4:
        return "量价偏强，重点观察"
    elif 0 <= pct < 2:
        return "走势温和，可继续盯"
    elif -2 <= pct < 0:
        return "小幅回调，等企稳"
    elif -4 <= pct < -2:
        return "调整偏弱，暂缓"
    else:
        return "跌幅较大，先不急接"


def make_level(row) -> str:
    pct = safe_float(row.get("涨跌幅", 0))

    if 1.5 <= pct <= 5.5:
        return "A"
    elif -2 <= pct < 1.5:
        return "B"
    else:
        return "C"


# =========================
# 8. 生成正常网页
# =========================

def generate_html(df: pd.DataFrame) -> str:
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
        .table-wrap {{
            overflow-x: auto;
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
    </style>
</head>
<body>
    <h1>A股短线观察表</h1>
    <div class="time">页面生成时间：{update_time}</div>

    <div class="note">
        本页面由 GitHub Actions 自动生成，输出文件为 <strong>docs/index.html</strong>。<br>
        数据源优先使用新浪行情接口，失败时自动切换腾讯行情接口。<br>
        A = 重点观察，B = 等待机会，C = 谨慎处理。结果仅用于盘面观察，不构成投资建议。
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
                <th>成交额</th>
                <th>换手率</th>
                <th>数据源</th>
                <th>行情时间</th>
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
                <td>{row.get("成交额", "")}</td>
                <td>{row.get("换手率", "")}</td>
                <td>{row.get("数据源", "")}</td>
                <td>{row.get("行情时间", "")}</td>
                <td>{row.get("操作提示", "")}</td>
            </tr>
"""

    html += """
        </tbody>
    </table>
    </div>

    <div class="footer">
        说明：本表为自选股快速观察表。由于免费行情接口可能存在延迟、字段变化或临时不可用，实际操作仍需结合交易软件、指数环境、板块强弱、成交量和自身仓位判断。
    </div>
</body>
</html>
"""
    return html


# =========================
# 9. 生成错误网页
# =========================

def generate_error_html(error_message: str) -> str:
    update_time = now_str()

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>A股短线观察表</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="font-family: Microsoft YaHei, Arial; padding: 30px; line-height: 1.8;">
    <h1>A股短线观察表</h1>
    <p>页面生成时间：{update_time}</p>

    <h2 style="color:#d1242f;">本次行情获取失败</h2>

    <p>
        程序已经成功运行到生成网页步骤，但新浪和腾讯行情接口都没有返回有效数据。
        这通常是免费行情接口临时不可用、GitHub Actions 网络访问受限，或接口字段临时变化造成的。
    </p>

    <p>
        你可以稍后在 GitHub 里手动重新运行：
        <strong>Actions → stock-watch → Run workflow</strong>
    </p>

    <h3>错误信息</h3>
    <pre style="background:#f6f8fa; padding:15px; white-space:pre-wrap; border:1px solid #d0d7de;">
{error_message}
    </pre>
</body>
</html>
"""


# =========================
# 10. 主程序
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
        print("使用数据源：")
        print(watch_df["数据源"].value_counts())

    except Exception as e:
        error_message = repr(e) + "\n\n" + traceback.format_exc()

        html = generate_error_html(error_message)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"行情获取失败，但已生成错误说明页：{OUTPUT_FILE}")
        print(error_message)

        # 不再 raise，避免 GitHub Actions 红叉
        return


if __name__ == "__main__":
    main()
