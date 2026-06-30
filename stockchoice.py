# -*- coding: utf-8 -*-
"""
A股自选股监控网页生成程序
输出位置：
1. docs/index.html
2. docs/history/时间戳.html

特点：
1. 不使用 AKShare
2. 不使用东方财富
3. 主接口：腾讯行情接口
4. 备用接口：新浪行情接口
5. 每次运行生成唯一历史网页，避免缓存
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
# 1. 股票池：39只
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

    ("300604", "长川科技"),
    ("688200", "华峰测控"),
    ("688361", "中科飞测"),
    ("300666", "江丰电子"),
    ("688396", "华润微"),
    ("603290", "斯达半导"),
    ("300373", "扬杰科技"),
    ("688099", "晶晨股份"),
    ("688525", "佰维存储"),
    ("688347", "华虹公司"),
    ("002156", "通富微电"),
    ("002409", "雅克科技"),
    ("603005", "晶方科技"),
    ("300567", "精测电子"),
    ("688012", "中微公司"),
    ("688249", "晶合集成"),
    ("688498", "源杰科技"),
    ("688213", "思特威"),
    ("688220", "翱捷科技"),
    ("688018", "乐鑫科技"),
    ("688019", "安集科技"),
]

# =========================
# 2. 输出目录
# =========================

OUTPUT_DIR = "docs"
HISTORY_DIR = os.path.join(OUTPUT_DIR, "history")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")
LATEST_URL_FILE = os.path.join(OUTPUT_DIR, "latest_url.txt")


# =========================
# 3. 工具函数
# =========================

def now_dt() -> datetime.datetime:
    return datetime.datetime.now()


def now_str() -> str:
    return now_dt().strftime("%Y-%m-%d %H:%M:%S")


def timestamp_str() -> str:
    return now_dt().strftime("%Y%m%d_%H%M_%S")


def get_market_prefix(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    return "sz"


def safe_float(x, default=0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, str):
            x = x.strip()
            if x in ["", "--", "-", "None", "nan", "NaN"]:
                return default
        return float(x)
    except Exception:
        return default


def safe_text(x) -> str:
    if x is None:
        return ""
    x = str(x).strip()
    if x in ["", "None", "nan", "NaN"]:
        return ""
    return x


def format_amount(x) -> str:
    value = safe_float(x, 0)
    if value >= 100000000:
        return f"{value / 100000000:.2f}亿"
    if value >= 10000:
        return f"{value / 10000:.2f}万"
    return f"{value:.0f}"


def request_text(
    url: str,
    headers: Dict[str, str],
    encoding: str = "gbk",
    timeout: int = 15
) -> str:
    last_error = None

    for i in range(5):
        try:
            print(f"请求第 {i + 1} 次：{url[:120]}...")
            time.sleep(random.uniform(1.2, 3.5))

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
            time.sleep(6 + i * 6)

    raise RuntimeError(f"连续 5 次请求失败：{repr(last_error)}")


# =========================
# 4. 腾讯行情接口：主接口
# =========================

def get_data_from_tencent(stock_list: List[Tuple[str, str]]) -> pd.DataFrame:
    symbols = []
    for code, _ in stock_list:
        symbols.append(get_market_prefix(code) + code)

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
                print(f"腾讯字段不足，跳过：{line[:100]}")
                continue

            name = safe_text(fields[1])
            price = safe_float(fields[3])
            pre_close = safe_float(fields[4])
            open_price = safe_float(fields[5])

            change = safe_float(fields[31]) if len(fields) > 31 else price - pre_close
            pct = safe_float(fields[32]) if len(fields) > 32 else (
                change / pre_close * 100 if pre_close > 0 else 0
            )

            high = safe_float(fields[33]) if len(fields) > 33 else 0
            low = safe_float(fields[34]) if len(fields) > 34 else 0

            amount_wan = safe_float(fields[37]) if len(fields) > 37 else 0
            amount = amount_wan * 10000

            turnover = safe_text(fields[38]) if len(fields) > 38 else ""

            volume_ratio = ""
            for idx in [49, 48, 50, 51, 52]:
                if len(fields) > idx:
                    candidate = safe_text(fields[idx])
                    val = safe_float(candidate, -1)
                    if 0 <= val <= 50:
                        volume_ratio = candidate
                        break

            quote_time = safe_text(fields[30]) if len(fields) > 30 else ""

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
                "量比": volume_ratio,
                "换手率": turnover,
                "成交额": amount,
                "行情时间": quote_time,
                "数据源": "腾讯",
            })

        except Exception as e:
            print(f"解析腾讯行情失败：{repr(e)}")
            print(line[:160])

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError("腾讯接口没有解析到有效股票数据")

    return df


# =========================
# 5. 新浪行情接口：备用接口
# =========================

def get_data_from_sina(stock_list: List[Tuple[str, str]]) -> pd.DataFrame:
    symbols = []
    for code, _ in stock_list:
        symbols.append(get_market_prefix(code) + code)

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
                print(f"新浪字段不足，跳过：{line[:100]}")
                continue

            name = fields[0]
            open_price = safe_float(fields[1])
            pre_close = safe_float(fields[2])
            price = safe_float(fields[3])
            high = safe_float(fields[4])
            low = safe_float(fields[5])
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
                "量比": "",
                "换手率": "",
                "成交额": amount,
                "行情时间": f"{date} {quote_time}",
                "数据源": "新浪备用",
            })

        except Exception as e:
            print(f"解析新浪行情失败：{repr(e)}")
            print(line[:160])

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError("新浪接口没有解析到有效股票数据")

    return df


# =========================
# 6. 统一获取行情
# =========================

def get_market_data() -> pd.DataFrame:
    errors = []

    try:
        print("开始使用腾讯接口获取行情...")
        df = get_data_from_tencent(STOCK_LIST)
        print(f"腾讯接口成功，获取 {len(df)} 只股票。")
        return df
    except Exception as e:
        errors.append("腾讯接口失败：" + repr(e))
        print(errors[-1])
        print(traceback.format_exc())

    try:
        print("开始使用新浪备用接口获取行情...")
        df = get_data_from_sina(STOCK_LIST)
        print(f"新浪备用接口成功，获取 {len(df)} 只股票。")
        return df
    except Exception as e:
        errors.append("新浪备用接口失败：" + repr(e))
        print(errors[-1])
        print(traceback.format_exc())

    raise RuntimeError("\n".join(errors))


# =========================
# 7. 判断级别和提示
# =========================

def make_signal(row) -> str:
    pct = safe_float(row.get("涨跌幅", 0))
    volume_ratio = safe_float(row.get("量比", 0))
    turnover = safe_float(row.get("换手率", 0))

    if pct >= 7:
        return "涨幅过大，谨慎追高"
    elif 4 <= pct < 7:
        if volume_ratio >= 1.2 or turnover >= 3:
            return "强势明显，只适合小仓观察"
        return "涨幅较大，谨慎观察"
    elif 2 <= pct < 4:
        if volume_ratio >= 1.2:
            return "量价偏强，重点观察"
        return "涨幅较好，继续观察"
    elif 0 <= pct < 2:
        if volume_ratio >= 1.2:
            return "温和放量，可继续盯"
        return "走势温和，可继续盯"
    elif -2 <= pct < 0:
        return "小幅回调，等企稳"
    elif -4 <= pct < -2:
        return "调整偏弱，暂缓"
    else:
        return "跌幅较大，先不急接"


def make_level(row) -> str:
    pct = safe_float(row.get("涨跌幅", 0))
    volume_ratio = safe_float(row.get("量比", 0))
    turnover = safe_float(row.get("换手率", 0))

    if 1.5 <= pct <= 5.5 and (volume_ratio >= 1.2 or turnover >= 3):
        return "A"
    elif 0 <= pct < 1.5 and volume_ratio >= 1.2:
        return "B"
    elif -2 <= pct < 1.5:
        return "B"
    else:
        return "C"


# =========================
# 8. 生成网页
# =========================

def generate_html(df: pd.DataFrame, version_name: str) -> str:
    update_time = now_str()

    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>A股短线观察表</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">

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
            line-height: 1.7;
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
    <div class="time">
        页面生成时间：{update_time}<br>
        唯一版本号：{version_name}
    </div>

    <div class="note">
        本页面由 GitHub Actions 自动生成。<br>
        为避免缓存，每次运行都会生成唯一历史页面：<strong>docs/history/{version_name}.html</strong>。<br>
        你截图或发给我分析时，优先使用这个唯一历史页面链接。<br>
        主数据源为腾讯行情接口，备用数据源为新浪行情接口。腾讯接口成功时会显示量比与换手率。
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
                <td>{row.get("量比", "")}</td>
                <td>{row.get("换手率", "")}</td>
                <td>{row.get("成交额", "")}</td>
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
        说明：本表为自选股快速观察表。腾讯接口返回的量比、换手率用于横向比较强弱；不同交易软件的统计口径可能有细微差异。实际操作仍需结合交易软件、指数环境、板块强弱、分时承接和自身仓位判断。
    </div>
</body>
</html>
"""
    return html


def generate_error_html(error_message: str, version_name: str) -> str:
    update_time = now_str()

    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>A股短线观察表</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
</head>
<body style="font-family: Microsoft YaHei, Arial; padding: 30px; line-height: 1.8;">
    <h1>A股短线观察表</h1>
    <p>页面生成时间：{update_time}</p>
    <p>唯一版本号：{version_name}</p>

    <h2 style="color:#d1242f;">本次行情获取失败</h2>

    <p>
        程序已经成功运行到生成网页步骤，但腾讯和新浪行情接口都没有返回有效数据。
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
# 9. 主程序
# =========================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)

    version_name = timestamp_str()
    history_file = os.path.join(HISTORY_DIR, f"{version_name}.html")

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

        html = generate_html(watch_df, version_name)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)

        with open(history_file, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"最新网页已生成：{OUTPUT_FILE}")
        print(f"唯一历史网页已生成：{history_file}")
        print(f"共生成股票数量：{len(watch_df)}")
        print("使用数据源：")
        print(watch_df["数据源"].value_counts())

    except Exception as e:
        error_message = repr(e) + "\n\n" + traceback.format_exc()
        html = generate_error_html(error_message, version_name)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)

        with open(history_file, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"行情获取失败，但已生成错误说明页：{OUTPUT_FILE}")
        print(f"唯一错误说明页已生成：{history_file}")
        print(error_message)

    return


if __name__ == "__main__":
    main()
