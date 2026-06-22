# -*- coding: utf-8 -*-
"""
通达信 pytdx 版：30只核心股实时行情
生成：
1. stock_output/stock_watch.png
2. stock_output/stock_watch.csv
3. stock_output/stock_watch.txt
"""

from pathlib import Path
from datetime import datetime
import time

import pandas as pd
import matplotlib.pyplot as plt
from pytdx.hq import TdxHq_API


TDX_SERVERS = [
    ("119.147.212.81", 7709),
    ("14.215.128.18", 7709),
    ("59.173.18.140", 7709),
    ("218.75.126.9", 7709),
    ("115.238.90.165", 7709),
    ("180.153.18.170", 7709),
]

# 你的7位数代码：6开头前面加1，其它前面加0
WATCH_CODES_7 = [
    "0002371",
    "1688012",
    "1688072",
    "1688120",
    "1688037",
    "0002916",
    "0300476",
    "0002463",
    "1600584",
    "1688041",
    "1603019",
    "0001309",
    "1600183",
    "1688981",
    "1688008",
    "1603986",
    "0300661",
    "1688052",
    "1603893",
    "1688300",
    "0300308",
    "0300502",
    "0300394",
    "0002281",
    "1601138",
    "0000977",
    "1688047",
    "1688256",
    "0300496",
    "0002049",
]

NAME_MAP = {
    "002371": "北方华创",
    "688012": "中微公司",
    "688072": "拓荆科技",
    "688120": "华海清科",
    "688037": "芯源微",
    "002916": "深南电路",
    "300476": "胜宏科技",
    "002463": "沪电股份",
    "600584": "长电科技",
    "688041": "海光信息",
    "603019": "中科曙光",
    "001309": "德明利",
    "600183": "生益科技",
    "688981": "中芯国际",
    "688008": "澜起科技",
    "603986": "兆易创新",
    "300661": "圣邦股份",
    "688052": "纳芯微",
    "603893": "瑞芯微",
    "688300": "联瑞新材",
    "300308": "中际旭创",
    "300502": "新易盛",
    "300394": "天孚通信",
    "002281": "光迅科技",
    "601138": "工业富联",
    "000977": "浪潮信息",
    "688047": "龙芯中科",
    "688256": "寒武纪",
    "300496": "中科创达",
    "002049": "紫光国微",
}

OUT_DIR = Path("stock_output")
OUT_DIR.mkdir(exist_ok=True)


def code7_to_tdx(code7: str):
    code7 = str(code7).zfill(7)
    market = int(code7[0])
    code = code7[1:]
    return market, code


def connect_best_server():
    api = TdxHq_API(heartbeat=True, auto_retry=True)

    for ip, port in TDX_SERVERS:
        try:
            t0 = time.time()
            ok = api.connect(ip, port, time_out=2.5)
            if ok:
                test = api.get_security_quotes([(0, "000001")])
                if test:
                    dt = time.time() - t0
                    print(f"连接成功：{ip}:{port}，耗时 {dt:.2f}s")
                    return api, ip
        except Exception as e:
            print(f"连接失败：{ip}:{port}，{e}")

    raise RuntimeError("所有通达信服务器都连接失败，请稍后再试。")


def fetch_quotes(api):
    query_list = [code7_to_tdx(x) for x in WATCH_CODES_7]
    quotes = api.get_security_quotes(query_list)

    if not quotes:
        raise RuntimeError("没有取到行情数据。")

    rows = []

    for q in quotes:
        code = str(q.get("code", "")).zfill(6)
        last_close = float(q.get("last_close", 0) or 0)
        price = float(q.get("price", 0) or 0)
        open_ = float(q.get("open", 0) or 0)
        high = float(q.get("high", 0) or 0)
        low = float(q.get("low", 0) or 0)
        amount = float(q.get("amount", 0) or 0)
        vol = float(q.get("vol", 0) or 0)
        cur_vol = float(q.get("cur_vol", 0) or 0)

        pct = (price - last_close) / last_close * 100 if last_close else 0
        change = price - last_close if last_close else 0

        rows.append({
            "代码": code,
            "名称": NAME_MAP.get(code, code),
            "涨幅%": round(pct, 2),
            "现价": round(price, 2),
            "涨跌": round(change, 2),
            "买一": round(float(q.get("bid1", 0) or 0), 2),
            "卖一": round(float(q.get("ask1", 0) or 0), 2),
            "总量": round(vol / 10000, 2),
            "现量": round(cur_vol, 0),
            "今开": round(open_, 2),
            "最高": round(high, 2),
            "最低": round(low, 2),
            "昨收": round(last_close, 2),
            "总金额(亿)": round(amount / 1e8, 2),
        })

    df = pd.DataFrame(rows)

    order_map = {code7_to_tdx(c)[1]: i for i, c in enumerate(WATCH_CODES_7)}
    df["原排序"] = df["代码"].map(order_map)

    # 默认按涨幅排序，方便你发我时快速判断强弱
    df = df.sort_values("涨幅%", ascending=False).drop(columns=["原排序"])

    return df


def save_outputs(df, server_ip):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    csv_path = OUT_DIR / "stock_watch.csv"
    txt_path = OUT_DIR / "stock_watch.txt"
    png_path = OUT_DIR / "stock_watch.png"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"30只核心股实时行情\n")
        f.write(f"生成时间：{now}\n")
        f.write(f"数据源：通达信 {server_ip}\n")
        f.write("=" * 100 + "\n")
        f.write(df.to_string(index=False))

    plt.rcParams["font.sans-serif"] = [
        "Noto Sans CJK SC",
        "SimHei",
        "Microsoft YaHei",
        "Arial Unicode MS",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    fig_h = max(10, len(df) * 0.38)
    fig, ax = plt.subplots(figsize=(18, fig_h))
    ax.axis("off")

    title = f"30只核心股实时行情  {now}  数据源: TDX {server_ip}"
    ax.set_title(title, fontsize=16, pad=15)

    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc="center",
        loc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.45)

    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight="bold")
            cell.set_height(0.045)

    plt.tight_layout()
    plt.savefig(png_path, dpi=200, bbox_inches="tight")
    plt.close()

    print("生成完成：")
    print(png_path)
    print(csv_path)
    print(txt_path)


def main():
    api, server_ip = connect_best_server()
    try:
        df = fetch_quotes(api)
        save_outputs(df, server_ip)
    finally:
        try:
            api.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
