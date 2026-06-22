# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
import html
import time

from pytdx.hq import TdxHq_API

TDX_SERVERS = [
    ("119.147.212.81", 7709),
    ("14.215.128.18", 7709),
    ("59.173.18.140", 7709),
    ("218.75.126.9", 7709),
    ("115.238.90.165", 7709),
    ("180.153.18.170", 7709),
]

WATCH_CODES_7 = [
    "0002371","1688012","1688072","1688120","1688037",
    "0002916","0300476","0002463","1600584","1688041",
    "1603019","0001309","1600183","1688981","1688008",
    "1603986","0300661","1688052","1603893","1688300",
    "0300308","0300502","0300394","0002281","1601138",
    "0000977","1688047","1688256","0300496","0002049",
]

NAME_MAP = {
    "002371":"北方华创","688012":"中微公司","688072":"拓荆科技","688120":"华海清科","688037":"芯源微",
    "002916":"深南电路","300476":"胜宏科技","002463":"沪电股份","600584":"长电科技","688041":"海光信息",
    "603019":"中科曙光","001309":"德明利","600183":"生益科技","688981":"中芯国际","688008":"澜起科技",
    "603986":"兆易创新","300661":"圣邦股份","688052":"纳芯微","603893":"瑞芯微","688300":"联瑞新材",
    "300308":"中际旭创","300502":"新易盛","300394":"天孚通信","002281":"光迅科技","601138":"工业富联",
    "000977":"浪潮信息","688047":"龙芯中科","688256":"寒武纪","300496":"中科创达","002049":"紫光国微",
}

OUT_DIR = Path("stock_output")
OUT_DIR.mkdir(exist_ok=True)


def now_cn():
    return datetime.now(ZoneInfo("Asia/Shanghai"))


def code7_to_tdx(code7):
    code7 = str(code7).zfill(7)
    return int(code7[0]), code7[1:]


def fnum(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def trading_minutes_now():
    n = now_cn()
    h, m = n.hour, n.minute
    if h < 9 or (h == 9 and m < 30):
        return 1
    if h < 11 or (h == 11 and m <= 30):
        total = (h - 9) * 60 + m - 30
    elif h < 13:
        total = 120
    elif h < 15:
        total = 120 + (h - 13) * 60 + m
    else:
        total = 240
    return max(1, min(total, 240))


def connect_best_server():
    for ip, port in TDX_SERVERS:
        api = TdxHq_API(heartbeat=True, auto_retry=True)
        try:
            ok = api.connect(ip, port, time_out=2.5)
            if ok:
                test = api.get_security_quotes([(0, "000001")])
                if test:
                    print(f"连接成功：{ip}:{port}")
                    return api, ip
        except Exception as e:
            print(f"连接失败：{ip}:{port} {e}")
    raise RuntimeError("所有通达信服务器连接失败")


def get_avg_5day_amount(api, market, code):
    try:
        bars = api.get_security_bars(9, market, code, 0, 6)
        if not bars or len(bars) < 6:
            return 0.0
        prev5 = bars[-6:-1]
        amounts = [fnum(x.get("amount")) for x in prev5]
        amounts = [a for a in amounts if a > 0]
        return sum(amounts) / len(amounts) if amounts else 0.0
    except Exception:
        return 0.0


def fetch_quotes(api):
    query_list = [code7_to_tdx(x) for x in WATCH_CODES_7]
    quotes = api.get_security_quotes(query_list)

    if not quotes:
        raise RuntimeError("没有取到行情数据")

    minutes = trading_minutes_now()
    rows = []

    for q in quotes:
        code = str(q.get("code", "")).zfill(6)
        market = 1 if code.startswith("6") else 0

        last_close = fnum(q.get("last_close"))
        price = fnum(q.get("price"))
        open_ = fnum(q.get("open"))
        high = fnum(q.get("high"))
        low = fnum(q.get("low"))
        amount = fnum(q.get("amount"))
        vol = fnum(q.get("vol"))
        cur_vol = fnum(q.get("cur_vol"))

        pct = (price - last_close) / last_close * 100 if last_close else 0
        change = price - last_close if last_close else 0

        avg5_amount = get_avg_5day_amount(api, market, code)
        amount_ratio_day = amount / avg5_amount * 100 if avg5_amount else 0
        amount_strength = amount / (avg5_amount * minutes / 240) if avg5_amount else 0

        if high > low:
            pos_pct = (price - low) / (high - low) * 100
        else:
            pos_pct = 0

        rows.append({
            "代码": code,
            "名称": NAME_MAP.get(code, code),
            "涨幅%": round(pct, 2),
            "现价": round(price, 2),
            "涨跌": round(change, 2),
            "买价": round(fnum(q.get("bid1")), 2),
            "卖价": round(fnum(q.get("ask1")), 2),
            "总量(万手)": round((vol / 100) / 10000, 2),
            "现量": int(cur_vol),
            "今开": round(open_, 2),
            "最高": round(high, 2),
            "最低": round(low, 2),
            "昨收": round(last_close, 2),
            "总金额(亿)": round(amount / 1e8, 2),
            "5日额比%": round(amount_ratio_day, 1),
            "额强度": round(amount_strength, 2),
            "日内位置%": round(pos_pct, 1),
        })

    rows.sort(key=lambda x: x["涨幅%"], reverse=True)
    return rows


def save_csv(rows):
    path = OUT_DIR / "stock_watch.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def save_txt(rows, server_ip):
    path = OUT_DIR / "stock_watch.txt"
    n = now_cn().strftime("%Y-%m-%d %H:%M:%S")
    cols = list(rows[0].keys())

    widths = {c: max(len(c), max(len(str(r[c])) for r in rows)) for c in cols}

    with open(path, "w", encoding="utf-8") as f:
        f.write("30只核心股实时行情\n")
        f.write(f"生成时间：{n} 北京时间\n")
        f.write(f"数据源：TDX {server_ip}\n")
        f.write("说明：5日额比%=今日成交额/近5日平均全天成交额；额强度=按当前交易时间折算的成交额活跃度。\n")
        f.write("=" * 160 + "\n")
        f.write(" ".join(c.ljust(widths[c]) for c in cols) + "\n")
        for r in rows:
            f.write(" ".join(str(r[c]).ljust(widths[c]) for c in cols) + "\n")
    return path


def save_html(rows, server_ip):
    path = OUT_DIR / "stock_watch.html"
    n = now_cn().strftime("%Y-%m-%d %H:%M:%S")
    cols = list(rows[0].keys())

    def color(v, col):
        if col in ["涨幅%", "涨跌"]:
            try:
                x = float(v)
                if x > 0:
                    return "red"
                if x < 0:
                    return "green"
            except Exception:
                pass
        return "#111"

    html_rows = []
    for r in rows:
        tds = []
        for c in cols:
            tds.append(f'<td style="color:{color(r[c], c)}">{html.escape(str(r[c]))}</td>')
        html_rows.append("<tr>" + "".join(tds) + "</tr>")

    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>30只核心股实时行情</title>
<style>
body {{ font-family: "Microsoft YaHei", "SimHei", Arial, sans-serif; padding: 16px; }}
h2 {{ margin: 0 0 8px 0; }}
p {{ margin: 4px 0; color: #555; }}
table {{ border-collapse: collapse; font-size: 13px; }}
th, td {{ border: 1px solid #999; padding: 5px 8px; text-align: center; white-space: nowrap; }}
th {{ background: #eee; }}
tr:nth-child(even) {{ background: #fafafa; }}
</style>
</head>
<body>
<h2>30只核心股实时行情</h2>
<p>生成时间：{n} 北京时间</p>
<p>数据源：TDX {server_ip}</p>
<p>说明：5日额比%=今日成交额/近5日平均全天成交额；额强度=按当前交易时间折算的成交额活跃度。</p>
<table>
<thead><tr>{''.join(f'<th>{html.escape(c)}</th>' for c in cols)}</tr></thead>
<tbody>
{''.join(html_rows)}
</tbody>
</table>
</body>
</html>"""
    path.write_text(content, encoding="utf-8")
    return path


def save_svg(rows, server_ip):
    path = OUT_DIR / "stock_watch.svg"
    n = now_cn().strftime("%Y-%m-%d %H:%M:%S")
    cols = list(rows[0].keys())

    col_widths = {
        "代码": 82, "名称": 92, "涨幅%": 70, "现价": 78, "涨跌": 72,
        "买价": 78, "卖价": 78, "总量(万手)": 100, "现量": 70,
        "今开": 78, "最高": 78, "最低": 78, "昨收": 78,
        "总金额(亿)": 98, "5日额比%": 88, "额强度": 76, "日内位置%": 92,
    }

    widths = [col_widths.get(c, 80) for c in cols]
    row_h = 28
    left = 8
    top = 72
    width = sum(widths) + left * 2
    height = top + row_h * (len(rows) + 2)

    def esc(x):
        return html.escape(str(x))

    def color(v, col):
        if col in ["涨幅%", "涨跌"]:
            try:
                x = float(v)
                if x > 0:
                    return "#d40000"
                if x < 0:
                    return "#008000"
            except Exception:
                pass
        return "#111111"

    parts = []
    parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<style>
text {{ font-family: "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", Arial, sans-serif; font-size: 13px; }}
.title {{ font-size: 20px; font-weight: bold; }}
.note {{ font-size: 12px; fill: #555; }}
.head {{ font-weight: bold; }}
</style>
<rect width="100%" height="100%" fill="white"/>
<text x="{left}" y="25" class="title">30只核心股实时行情  {n} 北京时间</text>
<text x="{left}" y="48" class="note">数据源：TDX {server_ip}；5日额比%=今日成交额/近5日平均全天成交额；额强度=按当前交易时间折算的成交额活跃度。</text>
''')

    y = top
    x = left
    for c, w in zip(cols, widths):
        parts.append(f'<rect x="{x}" y="{y-row_h+6}" width="{w}" height="{row_h}" fill="#eeeeee" stroke="#999"/>')
        parts.append(f'<text x="{x+w/2}" y="{y}" text-anchor="middle" class="head">{esc(c)}</text>')
        x += w

    for i, r in enumerate(rows):
        y = top + row_h * (i + 1)
        bg = "#ffffff" if i % 2 == 0 else "#f8f8f8"
        x = left
        for c, w in zip(cols, widths):
            val = r[c]
            parts.append(f'<rect x="{x}" y="{y-row_h+6}" width="{w}" height="{row_h}" fill="{bg}" stroke="#cccccc"/>')
            parts.append(f'<text x="{x+w/2}" y="{y}" text-anchor="middle" fill="{color(val, c)}">{esc(val)}</text>')
            x += w

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def main():
    api, server_ip = connect_best_server()
    try:
        rows = fetch_quotes(api)
        csv_path = save_csv(rows)
        txt_path = save_txt(rows, server_ip)
        html_path = save_html(rows, server_ip)
        svg_path = save_svg(rows, server_ip)
        print("生成完成：")
        print(csv_path)
        print(txt_path)
        print(html_path)
        print(svg_path)
    finally:
        try:
            api.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
