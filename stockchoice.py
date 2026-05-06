# -*- coding: utf-8 -*-
import pandas as pd
from pytdx.hq import TdxHq_API


CANDIDATES = [
    "301308", "688525", "300475", "603986", "300223",
    "603893", "688608", "688120", "300604", "688200",
    "002916", "002384", "603228", "002938", "002463",
    "300476", "300308", "300502", "300394", "300570",
    "688037", "688019", "688018", "688012", "688072",
    "002371", "300661", "603501", "688008", "688256",
    "300458", "688099", "300496", "300857", "300913",
    "002281", "603118", "300567", "002156", "603019",
    "002230", "002241", "300408", "300433", "603160",
    "688521", "688629", "688498", "601138", "300442",
]

STOCK_NAME_OVERRIDES = {
    "301308": "江波龙", "688525": "佰维存储", "300475": "香农芯创",
    "603986": "兆易创新", "300223": "北京君正", "603893": "瑞芯微",
    "688608": "恒玄科技", "688120": "华海清科", "300604": "长川科技",
    "688200": "华峰测控", "002916": "深南电路", "002384": "东山精密",
    "603228": "景旺电子", "002938": "鹏鼎控股", "002463": "沪电股份",
    "300476": "胜宏科技", "300308": "中际旭创", "300502": "新易盛",
    "300394": "天孚通信", "300570": "太辰光", "688037": "芯源微",
    "688019": "安集科技", "688018": "乐鑫科技", "688012": "中微公司",
    "688072": "拓荆科技", "002371": "北方华创", "300661": "圣邦股份",
    "603501": "韦尔股份", "688008": "澜起科技", "688256": "寒武纪",
    "300458": "全志科技", "688099": "晶晨股份", "300496": "中科创达",
    "300857": "协创数据", "300913": "兆龙互连", "002281": "光迅科技",
    "603118": "共进股份", "300567": "精测电子", "002156": "通富微电",
    "603019": "中科曙光", "002230": "科大讯飞", "002241": "歌尔股份",
    "300408": "三环集团", "300433": "蓝思科技", "603160": "汇顶科技",
    "688521": "芯原股份", "688629": "华丰科技", "688498": "源杰科技",
    "601138": "工业富联", "300442": "润泽科技",
}

SAFETY_LEVEL = {
    "688200": "S", "002916": "S", "300661": "S", "688120": "S",
    "002384": "A+", "603893": "A+", "603228": "A+", "688019": "A+",
    "688037": "A+", "603501": "A+", "688018": "A+",
    "301308": "A", "688525": "A", "300223": "A", "300604": "A",
    "688608": "A", "688099": "A", "300496": "A",
    "300458": "B+", "300857": "B+", "300913": "B+",
    "002281": "B+", "603118": "B+", "300567": "B+",
}

SECTOR_TAG = {
    "688200": "半导体设备", "688120": "半导体设备", "300604": "半导体设备",
    "688037": "半导体设备", "688019": "半导体材料", "688018": "AI端侧",
    "002916": "PCB", "002384": "PCB", "603228": "PCB", "002938": "PCB",
    "603893": "AI端侧", "688099": "AI端侧", "300223": "存储/芯片",
    "300661": "模拟芯片", "603501": "半导体权重",
    "301308": "存储", "688525": "存储", "300475": "存储",
}


def get_market(code):
    return 1 if code.startswith("6") else 0


def connect_tdx():
    servers = [
        ("119.147.212.81", 7709),
        ("14.215.128.18", 7709),
        ("59.173.18.140", 7709),
        ("218.75.126.9", 7709),
        ("115.238.90.165", 7709),
        ("180.153.18.170", 7709),
    ]

    api = TdxHq_API()

    for ip, port in servers:
        try:
            if api.connect(ip, port, time_out=5):
                print(f"通达信行情连接成功：{ip}:{port}")
                return api
        except Exception:
            pass

    raise RuntimeError("通达信行情服务器连接失败")


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


def judge_tail_buy(code, pct, price, last_close, high, low, amount):
    safety = SAFETY_LEVEL.get(code, "B")
    sector = SECTOR_TAG.get(code, "AI硬件/半导体")

    score = 100
    reason = []

    if pct is None:
        return "无行情", safety, sector, score, "无有效行情"

    if -2.8 <= pct <= -0.8:
        score -= 35
        reason.append("跌幅舒服")
    elif -0.8 < pct <= 0.8:
        score -= 28
        reason.append("小跌/微涨")
    elif 0.8 < pct <= 1.8:
        score -= 18
        reason.append("微涨可看")
    elif -4.5 <= pct < -2.8:
        score -= 12
        reason.append("跌幅较大需确认")
    elif pct > 2.5:
        score += 30
        reason.append("涨幅偏大不追")
    elif pct < -5:
        score += 25
        reason.append("跌太深防破位")

    if safety == "S":
        score -= 22
        reason.append("S级安全")
    elif safety == "A+":
        score -= 16
        reason.append("A+安全")
    elif safety == "A":
        score -= 10
        reason.append("A级")
    elif safety == "B+":
        score -= 3
        reason.append("弹性股")

    if high and low and high > low and price:
        intraday_pos = (price - low) / (high - low)
        if 0.20 <= intraday_pos <= 0.55:
            score -= 14
            reason.append("日内位置适中偏低")
        elif intraday_pos < 0.20:
            score -= 5
            reason.append("接近日低")
        elif intraday_pos > 0.75:
            score += 15
            reason.append("靠近日高不追")

    if amount:
        if amount >= 500000000:
            score -= 8
            reason.append("成交活跃")
        elif amount < 100000000:
            score += 8
            reason.append("成交偏冷")

    if score <= 25 and pct <= 1.8:
        action = "尾盘优先低吸"
    elif score <= 40 and pct <= 2:
        action = "可买入"
    elif score <= 55 and pct <= 2.5:
        action = "观察小仓"
    elif pct > 2.5:
        action = "不追"
    elif pct < -5:
        action = "暂缓防破位"
    else:
        action = "观察"

    return action, safety, sector, round(score, 2), "；".join(reason)


def get_realtime_result():
    api = connect_tdx()

    try:
        query_list = [(get_market(code), code) for code in CANDIDATES]
        quotes = api.get_security_quotes(query_list)
    finally:
        api.disconnect()

    rows = []

    for q in quotes:
        code = q.get("code")
        name = STOCK_NAME_OVERRIDES.get(code, code)

        price = safe_float(q.get("price"))
        last_close = safe_float(q.get("last_close"))
        open_price = safe_float(q.get("open"))
        high = safe_float(q.get("high"))
        low = safe_float(q.get("low"))
        vol = safe_float(q.get("vol"))
        amount = safe_float(q.get("amount"))

        pct = None
        if price is not None and last_close not in (None, 0):
            pct = (price - last_close) / last_close * 100

        action, safety, sector, score, reason = judge_tail_buy(
            code, pct, price, last_close, high, low, amount
        )

        rows.append({
            "代码": code,
            "名称": name,
            "板块": sector,
            "安全级别": safety,
            "现价": price,
            "昨收": last_close,
            "涨跌幅%": round(pct, 2) if pct is not None else "",
            "开盘": open_price,
            "最高": high,
            "最低": low,
            "成交量": vol,
            "成交额": amount,
            "尾盘建议": action,
            "尾盘优先分": score,
            "理由": reason,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values(
        by=["尾盘优先分", "涨跌幅%"],
        ascending=[True, True],
        na_position="last"
    )

    return df


def main():
    df = get_realtime_result()

    df.to_csv("tdx_tail_buy_signal.csv", index=False, encoding="utf-8-sig")
    df.to_excel("tdx_tail_buy_signal.xlsx", index=False)

    show_cols = ["代码", "名称", "涨跌幅%", "尾盘建议", "尾盘优先分"]

    print("\n今日尾盘低吸前15：")
    print(df[show_cols].head(15).to_string(index=False))

    print("\n已生成：tdx_tail_buy_signal.csv")
    print("已生成：tdx_tail_buy_signal.xlsx")


if __name__ == "__main__":
    main()
