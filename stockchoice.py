# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
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

FLOAT_SHARES = {
    # 如需计算换手率，在这里手工填“流通股本”，单位：股
    # "600584": 1780000000,
}

OUT_DIR = Path("stock_output")
OUT_DIR.mkdir(exist_ok=True)


def code7_to_tdx(code7):
    code7 = str(code7).zfill(7)
    return int(code7[0]), code7[1:]


def get_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def trading_minutes_now():
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    h, m = now.hour, now.minute

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
            if api.connect(ip, port, time_out=2.5):
                test = api.get_security_quotes([(0, "000001")])
                if test:
                    print(f"连接成功：{ip}:{port}")
                    return api, ip
        except Exception as e:
            print(f"连接失败：{ip}:{port} {e}")
    raise RuntimeError("所有通达信服务器连接失败")


def get_avg_5day_volume(api, market, code):
    try:
        bars = api.get_security_bars(9, market, code, 0, 6)
        if not bars or len(bars) < 6:
            return 0

        prev5 = bars[-6:-1]
        vols = [get_float(x.get("vol")) for x in prev5]
        vols = [v for v in vols if v > 0]

        return sum(vols) / len(vols) if vols else 0
    except Exception:
        return 0


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
            "总量": get_float(q.get("vol")),      # 通达信实时总量，近似股数
            "现量": get_float(q.get("cur_vol")),
            "今开": get_float(q.get("open")),
            "最高": get_float(q.get("high")),
            "最低": get_float(q.get("low")),
            "昨收": last_close,
            "总金额": get_float(q.get("amount")),
        }
    return rows


def fetch_quotes(api):
    q1 = fetch_once(api)
    time.sleep(3)
    q2 = fetch_once(api)

    minutes = trading_minutes_now()
    rows = []

    for code7 in WATCH_CODES_7:
        market, code = code7_to_tdx(code7)
        r = q2.get(code)
        if not r:
            continue

        old_price = get_float(q1.get(code, {}).get("现价"))
        now_price = get_float(r.get("现价"))
        last_close = get_float(r.get("昨收"))

        speed = (now_price - old_price) / last_close * 100 if old_price and last_close else 0

        # 修正：实时总量转为“手”
        current_vol_hand = r["总量"] / 100

        # 日K vol 通常为“手”，所以用“手”计算量比
        avg5_vol_hand = get_avg_5day_volume(api, market, code)
        expected_now_vol = avg5_vol_hand * minutes / 240 if avg5_vol_hand else 0
        volume_ratio = current_vol_hand / expected_now_vol if expected_now_vol else ""

        float_share = FLOAT_SHARES.get(code)
        turnover = (r["总量"] / float_share * 100) if float_share else ""

        rows.append({
            "代码": code,
            "名称": r["名称"],
            "涨幅%": round(r["涨幅%"], 2),
            "现价": round(r["现价"], 2),
            "涨跌": round(r["涨跌"], 2),
            "买价": round(r["买价"], 2),
            "卖价": round(r["卖价"], 2),
            "总量(万手)": round(current_vol_hand / 10000, 2),
            "现量": int(r["现量"]),
            "涨速%": round(speed, 2),
            "换手%": round(turnover, 2) if turnover != "" else "",
            "今开": round(r["今开"], 2),
            "最高": round(r["最高"], 2),
            "最低": round(r["最低"], 2),
            "昨收": round(r["昨收"], 2),
            "总金额(亿)": round(r["总金额"] / 1e8, 2),
            "量比估算": round(volume_ratio, 2) if volume_ratio != "" else "",
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("涨幅%", ascending=False)
    return df


def get_chinese_font():
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]

    for p in candidates:
        if Path(p).exists():
            return FontProperties(fname=p)

    return None


def save_outputs(df, server_ip):
    now = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")

    csv_path = OUT_DIR / "stock_watch.csv"
    txt_path = OUT_DIR / "stock_watch.txt"
    png_path = OUT_DIR / "stock_watch.png"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("30只核心股实时行情\n")
        f.write(f"生成时间：{now} 北京时间\n")
        f.write(f"数据源：TDX {server_ip}\n")
        f.write("说明：量比为估算值；换手率需手工填写流通股本后计算。\n")
        f.write("=" * 150 + "\n")
        f.write(df.to_string(index=False))

    font_prop = get_chinese_font()

    fig, ax = plt.subplots(figsize=(24, 12))
    ax.axis("off")

    title = f"30只核心股实时行情  {now} 北京时间"
    if font_prop:
        ax.set_title(title, fontproperties=font_prop, fontsize=18, pad=15)
    else:
        ax.set_title(title, fontsize=18, pad=15)

    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc="center",
        loc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(8.2)
    table.scale(1, 1.35)

    for (row, col), cell in table.get_celld().items():
        if font_prop:
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
        try:
            api.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
