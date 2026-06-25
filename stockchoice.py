# -*- coding: utf-8 -*-
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import csv
import html
import requests

OUT_DIR = Path("stock_output")
OUT_DIR.mkdir(exist_ok=True)

DOCS_DIR = Path("docs")
DOCS_DIR.mkdir(exist_ok=True)

# =========================
# 50只短线吃肉股票池
# =========================
STOCK_POOL = [
    # 第一梯队：半导体设备/制造
    ("688012", "中微公司", "半导体设备"),
    ("002371", "北方华创", "半导体设备"),
    ("688120", "华海清科", "半导体设备"),
    ("688082", "盛美上海", "半导体设备"),
    ("688072", "拓荆科技", "半导体设备"),
    ("688037", "芯源微", "半导体设备"),
    ("688981", "中芯国际", "晶圆制造"),
    ("688041", "海光信息", "国产算力"),
    ("688256", "寒武纪", "国产算力"),
    ("688047", "龙芯中科", "国产算力"),

    # PCB / AI硬件
    ("002463", "沪电股份", "AI PCB"),
    ("600183", "生益科技", "AI PCB"),
    ("002916", "深南电路", "AI PCB"),
    ("300476", "胜宏科技", "AI PCB"),
    ("002384", "东山精密", "AI PCB"),
    ("603228", "景旺电子", "AI PCB"),
    ("002436", "兴森科技", "IC载板"),
    ("002130", "沃尔核材", "高速互联"),
    ("601138", "工业富联", "AI服务器"),
    ("000977", "浪潮信息", "AI服务器"),

    # 光模块
    ("300308", "中际旭创", "光模块"),
    ("300502", "新易盛", "光模块"),
    ("300394", "天孚通信", "光模块"),
    ("002281", "光迅科技", "光模块"),
    ("300442", "润泽科技", "算力中心"),

    # 存储/芯片设计
    ("001309", "德明利", "存储"),
    ("603986", "兆易创新", "存储"),
    ("603893", "瑞芯微", "芯片设计"),
    ("688008", "澜起科技", "芯片设计"),
    ("300661", "圣邦股份", "模拟芯片"),
    ("688052", "纳芯微", "模拟芯片"),
    ("002049", "紫光国微", "特种芯片"),

    # 半导体材料/零部件
    ("688300", "联瑞新材", "半导体材料"),
    ("688126", "沪硅产业", "半导体材料"),
    ("300666", "江丰电子", "半导体材料"),
    ("688396", "华润微", "功率半导体"),
    ("300373", "扬杰科技", "功率半导体"),
    ("603290", "斯达半导", "功率半导体"),

    # 弹性设备/检测
    ("688627", "精智达", "检测设备"),
    ("688668", "鼎通科技", "连接器"),
    ("688141", "杰华特", "电源芯片"),
    ("300604", "长川科技", "检测设备"),
    ("688200", "华峰测控", "检测设备"),
    ("688361", "中科飞测", "检测设备"),

    # 软件/机器人/其它观察
    ("600536", "中国软件", "国产软件"),
    ("688251", "井松智能", "机器人"),
    ("300496", "中科创达", "智能汽车"),
    ("300124", "汇川技术", "机器人"),
    ("688017", "绿的谐波", "机器人"),
    ("688306", "均普智能", "机器人"),
]


def now_cn():
    return datetime.now(ZoneInfo("Asia/Shanghai"))


def sina_symbol(code):
    return ("sh" if code.startswith("6") else "sz") + code


def fetch_sina_quotes():
    symbols = ",".join(sina_symbol(code) for code, _, _ in STOCK_POOL)
    url = f"https://hq.sinajs.cn/list={symbols}"
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(url, headers=headers, timeout=12)
    r.encoding = "gbk"
    text = r.text

    result = []
    stock_map = {code: (name, sector) for code, name, sector in STOCK_POOL}

    for line in text.splitlines():
        if '="' not in line:
            continue

        left, right = line.split('="', 1)
        data = right.strip('";')
        arr = data.split(",")

        if len(arr) < 32 or arr[0] == "":
            continue

        symbol = left.split("_")[-1]
        code = symbol[-6:]
        name, sector = stock_map.get(code, (arr[0], ""))

        try:
            open_p = float(arr[1])
            prev_close = float(arr[2])
            price = float(arr[3])
            high = float(arr[4])
            low = float(arr[5])
            volume = float(arr[8])
            amount = float(arr[9])
            date = arr[30]
            tm = arr[31]
        except Exception:
            continue

        if prev_close <= 0 or price <= 0:
            continue

        pct = (price - prev_close) / prev_close * 100
        change = price - prev_close
        amount_yi = amount / 1e8
        pos = (price - low) / (high - low) * 100 if high > low else 0

        result.append({
            "代码": code,
            "名称": name,
            "板块": sector,
            "最新价": round(price, 2),
            "涨跌幅": round(pct, 2),
            "涨跌额": round(change, 2),
            "今开": round(open_p, 2),
            "最高": round(high, 2),
            "最低": round(low, 2),
            "昨收": round(prev_close, 2),
            "成交额": round(amount_yi, 2),
            "日内位置": round(pos, 1),
            "行情时间": f"{date} {tm}",
            "数据源": "新浪",
        })

    return result


def calc_ai_score(row):
    pct = row["涨跌幅"]
    amount = row["成交额"]
    pos = row["日内位置"]
    sector = row["板块"]

    score = 0

    # 涨幅：喜欢强，但不追过热
    if 1 <= pct <= 4:
        score += 34
    elif 4 < pct <= 6:
        score += 30
    elif 6 < pct <= 8:
        score += 20
    elif pct > 8:
        score += 8
    elif 0 <= pct < 1:
        score += 18
    elif -2 <= pct < 0:
        score += 8
    else:
        score -= 10

    # 成交额：短线要有钱
    if amount >= 100:
        score += 28
    elif amount >= 50:
        score += 23
    elif amount >= 20:
        score += 16
    elif amount >= 10:
        score += 10
    else:
        score += 3

    # 日内位置：收得越靠高位越好
    if pos >= 80:
        score += 20
    elif pos >= 65:
        score += 16
    elif pos >= 50:
        score += 10
    elif pos >= 30:
        score += 3
    else:
        score -= 8

    # 主线权重
    if sector in ["半导体设备", "晶圆制造", "国产算力"]:
        score += 18
    elif sector in ["AI PCB", "IC载板", "AI服务器", "存储"]:
        score += 12
    elif sector in ["光模块", "芯片设计", "模拟芯片", "半导体材料"]:
        score += 8
    else:
        score += 3

    # 过热惩罚
    risk = []
    if pct >= 8:
        score -= 18
        risk.append("涨幅过大")
    if pct >= 10:
        score -= 12
        risk.append("高位追涨风险")
    if pos < 35 and pct > 0:
        score -= 8
        risk.append("冲高回落")
    if amount < 8:
        score -= 6
        risk.append("成交额偏小")

    score = max(0, min(100, score))

    if score >= 78:
        level = "★★★★★"
        action = "优先关注，可考虑"
    elif score >= 65:
        level = "★★★★☆"
        action = "重点观察，等回踩"
    elif score >= 50:
        level = "★★★☆☆"
        action = "观察，不急买"
    else:
        level = "★★☆☆☆"
        action = "暂缓"

    if risk:
        action += "；" + "、".join(risk)

    return score, level, action


def build_rows():
    rows = fetch_sina_quotes()

    for r in rows:
        score, level, action = calc_ai_score(r)
        r["AI分"] = score
        r["AI优先级"] = level
        r["AI建议"] = action

    rows.sort(key=lambda x: x["AI分"], reverse=True)
    return rows


def save_csv(rows):
    path = OUT_DIR / "stock_watch.csv"
    cols = list(rows[0].keys())

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)

    return path


def save_txt(rows):
    path = OUT_DIR / "stock_watch.txt"
    t = now_cn().strftime("%Y-%m-%d %H:%M:%S")

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"A股短线AI观察表\n生成时间：{t} 北京时间\n")
        f.write("=" * 120 + "\n")
        for i, r in enumerate(rows, 1):
            f.write(
                f"{i:02d}. {r['代码']} {r['名称']} "
                f"{r['AI优先级']} AI分:{r['AI分']} "
                f"涨幅:{r['涨跌幅']}% 价:{r['最新价']} "
                f"成交额:{r['成交额']}亿 日内位置:{r['日内位置']}% "
                f"建议:{r['AI建议']}\n"
            )

    return path


def color_pct(v):
    try:
        x = float(v)
        if x > 0:
            return "red"
        if x < 0:
            return "green"
    except Exception:
        pass
    return ""


def save_html(rows):
    t = now_cn().strftime("%Y-%m-%d %H:%M:%S")
    path1 = OUT_DIR / "stock_watch.html"
    path2 = DOCS_DIR / "index.html"
    path3 = DOCS_DIR / "manual_latest.html"

    cols = [
        "排名", "代码", "名称", "板块", "最新价", "涨跌幅", "涨跌额",
        "今开", "最高", "最低", "昨收", "成交额", "日内位置",
        "AI分", "AI优先级", "AI建议", "行情时间"
    ]

    trs = []
    for i, r in enumerate(rows, 1):
        rr = dict(r)
        rr["排名"] = i

        tds = []
        for c in cols:
            val = rr.get(c, "")
            cls = ""
            if c in ["涨跌幅", "涨跌额"]:
                cls = color_pct(val)
            if c == "AI优先级" and "★★★★★" in str(val):
                cls = "strong"
            tds.append(f'<td class="{cls}">{html.escape(str(val))}</td>')
        trs.append("<tr>" + "".join(tds) + "</tr>")

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>A股短线AI观察表</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", Arial, sans-serif;
    margin: 18px;
    background: #f6f8fa;
    color: #24292f;
}}
h1 {{ margin-bottom: 6px; }}
.time {{ color: #666; margin-bottom: 12px; }}
.note {{
    background: #fff8c5;
    border: 1px solid #eac54f;
    padding: 10px 14px;
    border-radius: 8px;
    margin-bottom: 14px;
    line-height: 1.6;
}}
.table-wrap {{ overflow-x: auto; }}
table {{
    border-collapse: collapse;
    width: 100%;
    background: white;
    font-size: 13px;
}}
th, td {{
    border-bottom: 1px solid #eaeef2;
    padding: 7px 8px;
    text-align: center;
    white-space: nowrap;
}}
th {{
    background: #0969da;
    color: white;
    position: sticky;
    top: 0;
}}
tr:hover {{ background: #f1f8ff; }}
.red {{ color: #d1242f; font-weight: bold; }}
.green {{ color: #1a7f37; font-weight: bold; }}
.strong {{
    color: #cf222e;
    font-weight: bold;
}}
.footer {{
    margin-top: 16px;
    color: #666;
    font-size: 13px;
    line-height: 1.6;
}}
</style>
</head>
<body>
<h1>A股短线AI观察表</h1>
<div class="time">页面生成时间：{t} 北京时间</div>
<div class="note">
本页面按你的短线风格自动排序：安全优先、1～5天吃肉、主线优先、避免追过热。<br>
AI分越高越值得优先盯；但不等于无脑买，仍需结合当天大盘、板块和仓位。
</div>
<div class="table-wrap">
<table>
<thead>
<tr>{''.join(f'<th>{c}</th>' for c in cols)}</tr>
</thead>
<tbody>
{''.join(trs)}
</tbody>
</table>
</div>
<div class="footer">
说明：数据来自免费行情接口，可能存在延迟或字段异常。结果仅用于盘面观察，不构成投资建议。
</div>
</body>
</html>"""

    for p in [path1, path2, path3]:
        p.write_text(html_text, encoding="utf-8")

    return path1


def main():
    rows = build_rows()
    save_csv(rows)
    save_txt(rows)
    save_html(rows)

    print("生成完成：")
    print(OUT_DIR / "stock_watch.html")
    print(OUT_DIR / "stock_watch.csv")
    print(OUT_DIR / "stock_watch.txt")
    print(DOCS_DIR / "index.html")
    print(DOCS_DIR / "manual_latest.html")


if __name__ == "__main__":
    main()
