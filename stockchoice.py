# -*- coding: utf-8 -*-
import os
import pandas as pd
from pytdx.hq import TdxHq_API


TDX_DIR = r"D:\new_tdx"

CANDIDATES = [

    "688200", "688120", "002916", "300661", "688019",
    "688037", "002384", "603228", "603501", "688018",

    "603893", "688099", "300496", "300604", "688608",
    "301308", "688525", "300223", "300475", "603986",

    "300857", "300913", "300458", "002281", "603118",
    "300567", "002156", "603019", "002230", "300433",

    "002241", "603160", "300408", "688521", "688629",
    "300353", "300442", "300739", "002475", "300624",

    "002463", "300476", "002938", "603920", "002436",
    "603186", "300782", "002859", "002815", "603328",

    "300308", "300502", "300394", "300570", "300548",
    "603083", "300620", "300563", "300565",

    "688008", "688256", "688041",

    "601138", "603881", "300383", "300454", "300738",
    "688111",

    "688012", "688072", "002371",

    "300378", "300339", "300229", "002123", "300212",

    "688498",
]

STOCK_NAME_OVERRIDES = {

    "688200": "华峰测控",
    "688120": "华海清科",
    "002916": "深南电路",
    "300661": "圣邦股份",
    "688019": "安集科技",

    "688037": "芯源微",
    "002384": "东山精密",
    "603228": "景旺电子",
    "603501": "韦尔股份",
    "688018": "乐鑫科技",

    "603893": "瑞芯微",
    "688099": "晶晨股份",
    "300496": "中科创达",
    "300604": "长川科技",
    "688608": "恒玄科技",

    "301308": "江波龙",
    "688525": "佰维存储",
    "300223": "北京君正",
    "300475": "香农芯创",
    "603986": "兆易创新",

    "300857": "协创数据",
    "300913": "兆龙互连",
    "300458": "全志科技",
    "002281": "光迅科技",
    "603118": "共进股份",

    "300567": "精测电子",
    "002156": "通富微电",
    "603019": "中科曙光",
    "002230": "科大讯飞",
    "300433": "蓝思科技",

    "002241": "歌尔股份",
    "603160": "汇顶科技",
    "300408": "三环集团",
    "688521": "芯原股份",
    "688629": "华丰科技",

    "300353": "东土科技",
    "300442": "润泽科技",
    "300739": "明阳电路",
    "002475": "立讯精密",
    "300624": "万兴科技",

    "002463": "沪电股份",
    "300476": "胜宏科技",
    "002938": "鹏鼎控股",
    "603920": "世运电路",
    "002436": "兴森科技",

    "603186": "华正新材",
    "300782": "卓胜微",
    "002859": "洁美科技",
    "002815": "崇达技术",
    "603328": "依顿电子",

    "300308": "中际旭创",
    "300502": "新易盛",
    "300394": "天孚通信",
    "300570": "太辰光",
    "300548": "博创科技",

    "603083": "剑桥科技",
    "300620": "光库科技",
    "300563": "神宇股份",
    "300565": "科信技术",

    "688008": "澜起科技",
    "688256": "寒武纪",
    "688041": "海光信息",

    "601138": "工业富联",
    "603881": "数据港",
    "300383": "光环新网",
    "300454": "深信服",
    "300738": "奥飞数据",

    "688111": "金山办公",

    "688012": "中微公司",
    "688072": "拓荆科技",
    "002371": "北方华创",

    "300378": "鼎捷数智",
    "300339": "润和软件",
    "300229": "拓尔思",
    "002123": "梦网科技",
    "300212": "易华录",

    "688498": "源杰科技",
}

SAFETY_LEVEL = {

    "688200": "S",
    "688120": "S",
    "002916": "S",
    "300661": "S",
    "688019": "S",

    "688037": "A+",
    "002384": "A+",
    "603228": "A+",
    "603501": "A+",
    "688018": "A+",

    "603893": "A+",
    "688099": "A+",
    "300496": "A+",
    "300604": "A+",
    "688608": "A+",

    "301308": "A",
    "688525": "A",
    "300223": "A",
    "300475": "A",
    "603986": "A",

    "300857": "A",
    "300913": "A",
    "300458": "A",
    "002281": "A",
    "603118": "A",

    "300567": "A",
    "002156": "A",
    "603019": "A",
    "002230": "A",
    "300433": "A",

    "002241": "A",
    "603160": "A",
    "300408": "A",
    "688521": "A",
    "688629": "A",

    "002463": "A",
    "300476": "A",
    "002938": "A",
    "603920": "A",
    "002436": "A",

    "300308": "A",
    "300502": "A",
    "300394": "A",
    "300570": "A",
    "300548": "A",

    "603083": "A",
    "300620": "A",

    "688008": "A",
    "688041": "A",

    "601138": "A",
    "603881": "A",

    "688012": "A",
    "688072": "A",
    "002371": "A",

    "300353": "B+",
    "300442": "B+",
    "300739": "B+",
    "002475": "B+",
    "300624": "B+",

    "603186": "B+",
    "300782": "B+",
    "002859": "B+",
    "002815": "B+",
    "603328": "B+",

    "300563": "B+",
    "300565": "B+",

    "688256": "B+",
    "300383": "B+",
    "300454": "B+",
    "300738": "B+",
    "688111": "B+",

    "300378": "B+",
    "300339": "B+",
    "300229": "B+",
    "002123": "B+",
    "300212": "B+",

    "688498": "B+",
}

SECTOR_TAG = {

    "688200": "半导体设备",
    "688120": "半导体设备",
    "002916": "PCB",
    "300661": "模拟芯片",
    "688019": "半导体材料",

    "688037": "半导体设备",
    "002384": "PCB",
    "603228": "PCB",
    "603501": "半导体权重",
    "688018": "AI端侧",

    "603893": "AI端侧",
    "688099": "AI端侧",
    "300496": "AI端侧",
    "300604": "半导体设备",
    "688608": "AI端侧",

    "301308": "存储",
    "688525": "存储",
    "300223": "存储/芯片",
    "300475": "存储",
    "603986": "存储/MCU",

    "300857": "AI服务器",
    "300913": "高速连接",
    "300458": "AI端侧",
    "002281": "光模块",
    "603118": "通信设备",

    "300567": "半导体设备",
    "002156": "先进封装",
    "603019": "国产算力",
    "002230": "AI应用",
    "300433": "消费电子",

    "002241": "AI端侧",
    "603160": "芯片",
    "300408": "电子材料",
    "688521": "芯片设计",
    "688629": "高速连接",

    "300353": "工业互联网",
    "300442": "IDC",
    "300739": "PCB",
    "002475": "消费电子",
    "300624": "AI软件",

    "002463": "PCB",
    "300476": "PCB",
    "002938": "PCB",
    "603920": "PCB",
    "002436": "PCB",

    "603186": "电子材料",
    "300782": "射频芯片",
    "002859": "半导体材料",
    "002815": "PCB",
    "603328": "PCB",

    "300308": "CPO",
    "300502": "CPO",
    "300394": "CPO",
    "300570": "CPO",
    "300548": "CPO",

    "603083": "CPO",
    "300620": "CPO",
    "300563": "高速连接",
    "300565": "通信设备",

    "688008": "内存接口",
    "688256": "AI芯片",
    "688041": "国产GPU",

    "601138": "AI服务器",
    "603881": "数据中心",
    "300383": "数据中心",
    "300454": "网络安全",
    "300738": "数据中心",

    "688111": "办公AI",

    "688012": "半导体设备",
    "688072": "半导体设备",
    "002371": "半导体设备",

    "300378": "工业AI",
    "300339": "AI软件",
    "300229": "AI应用",
    "002123": "AI通信",
    "300212": "数据要素",

    "688498": "光芯片",
}


def get_market(code):
    return 1 if code.startswith("6") else 0


def read_tdx_stock_names(tdx_dir):
    name_map = {}
    files = [
        os.path.join(tdx_dir, "T0002", "hq_cache", "shm.tnf"),
        os.path.join(tdx_dir, "T0002", "hq_cache", "szm.tnf"),
    ]

    for file in files:
        if not os.path.exists(file):
            continue

        with open(file, "rb") as f:
            data = f.read()

        record_size = 314
        offset = 50

        while offset + record_size <= len(data):
            block = data[offset:offset + record_size]
            code = block[0:6].decode("gb18030", errors="ignore").strip()
            name = block[23:31].decode("gb18030", errors="ignore").strip()

            if code.isdigit() and len(code) == 6 and name:
                name_map[code] = name

            offset += record_size

    return name_map


def build_name_map():
    tdx_names = read_tdx_stock_names(TDX_DIR)
    return {
        code: tdx_names.get(code, STOCK_NAME_OVERRIDES.get(code, code))
        for code in CANDIDATES
    }


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
            if api.connect(ip, port, time_out=3):
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


def judge_tail_buy(code, pct, price, last_close, high, low, open_price, amount):
    safety = SAFETY_LEVEL.get(code, "B")
    sector = SECTOR_TAG.get(code, "AI硬件/半导体")

    score = 100
    reason = []

    if pct is None or price is None or last_close in (None, 0):
        return "无行情", safety, sector, score, "无有效行情"

    # =========================
    # 1. 涨跌幅判断
    # =========================
    if -2.8 <= pct <= -0.8:
        score -= 35
        reason.append("低吸区间舒服")
    elif -0.8 < pct <= 0.8:
        score -= 30
        reason.append("小跌/横盘强")
    elif 0.8 < pct <= 1.8:
        score -= 22
        reason.append("微涨可盯")
    elif 1.8 < pct <= 3:
        score -= 8
        reason.append("涨幅不高但需确认")
    elif -4.5 <= pct < -2.8:
        score -= 10
        reason.append("跌幅较大需看承接")
    elif pct > 3:
        score += 28
        reason.append("涨幅偏大不追")
    elif pct < -5:
        score += 30
        reason.append("跌太深防破位")

    # =========================
    # 2. 安全等级加权
    # =========================
    if safety == "S":
        score -= 24
        reason.append("S级安全")
    elif safety == "A+":
        score -= 20
        reason.append("A+核心")
    elif safety == "A":
        score -= 12
        reason.append("A级主线")
    elif safety == "B+":
        score -= 2
        reason.append("弹性股")

    # =========================
    # 3. 日内位置判断
    # =========================
    intraday_pos = None
    amplitude = None

    if high and low and high > low:
        intraday_pos = (price - low) / (high - low)
        amplitude = (high - low) / last_close * 100

        if 0.25 <= intraday_pos <= 0.60:
            score -= 16
            reason.append("日内位置健康")
        elif intraday_pos < 0.25:
            score -= 6
            reason.append("接近日低，需确认承接")
        elif intraday_pos > 0.78:
            score += 14
            reason.append("靠近日高，防回落")

        # 防大振幅诱多
        if amplitude > 8:
            score += 18
            reason.append("振幅过大，风险升高")
        elif 3 <= amplitude <= 6:
            score -= 8
            reason.append("振幅适中")
        elif amplitude < 3:
            score -= 6
            reason.append("走势稳定")

    # =========================
    # 4. 冲高回落判断
    # =========================
    if high and price and high > price:
        pullback_from_high = (high - price) / high * 100

        if pullback_from_high > 5:
            score += 18
            reason.append("冲高回落明显")
        elif 2 <= pullback_from_high <= 5:
            score += 6
            reason.append("有回落压力")
        elif 0.5 <= pullback_from_high < 2:
            score -= 4
            reason.append("正常回落")

    # =========================
    # 5. 低位拉回：判断承接
    # =========================
    if low and price and low > 0:
        rebound_from_low = (price - low) / low * 100

        if 1.5 <= rebound_from_low <= 4:
            score -= 18
            reason.append("低位拉回，承接较强")
        elif rebound_from_low > 5:
            score += 10
            reason.append("低位拉太猛，防尾盘诱多")
        elif rebound_from_low < 0.6 and pct < -1:
            score += 8
            reason.append("贴近日低，承接一般")

    # =========================
    # 6. 防尾盘硬拉诱多
    # =========================
    if open_price and price and open_price > 0:
        rise_from_open = (price - open_price) / open_price * 100

        if rise_from_open > 4 and pct > 2:
            score += 22
            reason.append("尾盘/日内拉升过快，防诱多")
        elif 1 <= rise_from_open <= 3 and pct <= 2.5:
            score -= 8
            reason.append("温和走强")

    # =========================
    # 7. 成交额过滤
    # =========================
    if amount:
        if amount >= 800000000:
            score -= 10
            reason.append("成交活跃")
        elif 300000000 <= amount < 800000000:
            score -= 6
            reason.append("成交尚可")
        elif amount < 100000000:
            score += 10
            reason.append("成交偏冷")

    # =========================
    # 8. 板块偏好加权
    # =========================
    if sector in ["PCB", "AI端侧", "半导体设备", "存储"]:
        score -= 8
        reason.append("主线板块")

    if sector in ["AI应用", "数据要素", "AI软件"]:
        score += 4
        reason.append("偏应用，弹性大但稳定性略弱")

    # =========================
    # 9. 最终建议
    # =========================
    if score <= 18 and pct <= 2.5:
        action = "重点盯盘"
    elif score <= 28 and pct <= 2:
        action = "尾盘优先低吸"
    elif score <= 42 and pct <= 2.5:
        action = "可买入"
    elif score <= 55 and pct <= 3:
        action = "观察小仓"
    elif pct > 3:
        action = "涨幅偏大，不追"
    elif pct < -5:
        action = "暂缓，防破位"
    else:
        action = "观察"

    return action, safety, sector, round(score, 2), "；".join(reason)


def get_realtime_result():
    name_map = build_name_map()

    api = connect_tdx()
    try:
        query_list = [(get_market(code), code) for code in CANDIDATES]
        quotes = api.get_security_quotes(query_list)
    finally:
        api.disconnect()

    rows = []

    for q in quotes:
        code = q.get("code")
        name = name_map.get(code, code)

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
            code, pct, price, last_close, high, low, open_price, amount
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

    show_cols = [
        "代码", "名称", "板块", "安全级别",
        "现价", "涨跌幅%", "尾盘建议", "尾盘优先分"
    ]

    print("\n今日重点盯盘前15：")
    print(df[show_cols].head(15).to_string(index=False))

    print("\n已生成：tdx_tail_buy_signal.csv")
    print("已生成：tdx_tail_buy_signal.xlsx")


if __name__ == "__main__":
    main()
