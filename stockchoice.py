# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime
import time
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
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


def code7_to_tdx(code7):
    code7 = str(code7).zfill(7)
    return int(code7[0]), code7[1:]


def connect_best_server():
    for ip, port in TDX_SERVERS:
        api = TdxHq_API(heartbeat=True, auto_retry=True)
        try:
            if api.connect(ip, port, time_out=2.5):
                test = api.get_security_quotes([(0, "000001")])
                if test:
                    print(f"连接成功：{ip}:{port}")
                    return api, ip
        except Exception as e:
            print(f"连接失败：{ip}:{port} {e}")
    raise RuntimeError("所有通达信服务器连接失败")


def get_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def fetch_once(api):
    query_list = [code7_to_tdx(x) for x in WATCH_CODES_7]
    quotes = api.get_security_quotes(query_list)
    rows = {}

    for q in quotes:
        code = str(q.get("code", "")).zfill(6)
        last_close = get_float(q.get("last_close"))
        price = get_float(q.get("price"))
        pct = (price - last_close) / last_close * 100 if last_close else 0

        rows[code] = {
            "代码": code,
            "名称": NAME_MAP.get(code, code),
            "涨幅%": pct,
            "现价": price,
            "涨跌": price - last_close if last_close else 0,
            "买价": get_float(q.get("bid1")),
            "卖价": get_float(q.get("ask1")),
            "总量": get_float(q.get("vol")),
            "现量": get_float(q.get("cur_vol")),
            "今开": get_float(q.get("open")),
            "最高": get_float(q.get("high")),
            "最低": get_float(q.get("low")),
            "昨收": last_close,
            "总金额": get_float(q.get("amount")),
        }
    return rows


def fetch_quotes(api):
    # 取两次，间隔3秒，估算涨速
    q1 = fetch_once(api)
    time.sleep(3)
    q2 = fetch_once(api)

    rows = []
    for code, r in q2.items():
        old = q1.get(code, {})
        old_price = get_float(old.get("现价"))
        now_price = get_float(r.get("现价"))
        last_close = get_float(r.get("昨收"))

        speed = 0
        if old_price and last_close:
            speed = (now_price - old_price) / last_close * 100

        # pytdx原始接口没有稳定的换手率/动态市盈率字段，这里先留空，避免乱算误导
        rows.append({
            "代码": r["代码"],
            "名称": r["名称"],
            "涨幅%": round(r["涨幅%"], 2),
            "现价": round(r["现价"], 2),
            "涨跌": round(r["涨跌"], 2),
            "买价": round(r["买价"], 2),
            "卖价": round(r["卖价"], 2),
            "总量": round(r["总量"] / 10000, 2),
            "现量": int(r["现量"]),
            "涨速%": round(speed, 2),
            "换手%": "",
            "今开": round(r["今开"], 2),
            "最高": round(r["最高"], 2),
            "最低": round(r["最低"], 2),
            "昨收": round(r["昨收"], 2),
            "市盈(动)": "",
            "总金额": round(r["总金额"] / 1e8, 2),
            "量比": "",
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("涨幅%", ascending=False)
    return df


def save_outputs(df, server_ip):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    csv_path = OUT_DIR / "stock_watch.csv"
    txt_path = OUT_DIR / "stock_watch.txt"
    png_path = OUT_DIR / "stock_watch.png"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"30只核心股实时行情\n生成时间：{now}\n数据源：TDX {server_ip}\n")
        f.write("=" * 120 + "\n")
        f.write(df.to_string(index=False))

    font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    font_prop = FontProperties(fname=font_path)

    fig, ax = plt.subplots(figsize=(22, 12))
    ax.axis("off")
    ax.set_title(f"30只核心股实时行情  {now}", fontproperties=font_prop, fontsize=18, pad=15)

    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc="center",
        loc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1, 1.35)

    for (row, col), cell in table.get_celld().items():
        cell.get_text().set_fontproperties(font_prop)
        if row == 0:
            cell.set_text_props(weight="bold")
            cell.set_height(0.045)

    plt.tight_layout()
    plt.savefig(png_path, dpi=220, bbox_inches="tight")
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
        api.disconnect()


if __name__ == "__main__":
    main()
