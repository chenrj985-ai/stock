# -*- coding: utf-8 -*-
"""
A股实时盯盘与低吸分级工具
------------------------------------------------
功能：
1. 使用通达信行情服务器获取A股日线数据；
2. 根据候选股票池、名称、安全等级、板块逻辑进行分类；
3. 自动输出：
   - 强买
   - 尾盘低吸
   - 有回撤就进
   - 观察可进
   - 观察
   - 今天不进
4. 重点强调安全性：不追连续大涨、不买跌破趋势、不买巨量冲高回落。

安装依赖：
    pip install pytdx pandas numpy

运行方式：
    python tdx_ai_watchlist.py

输出文件：
    tdx_watchlist_result.csv
"""

import time
import pandas as pd
import numpy as np

try:
    from pytdx.hq import TdxHq_API
except ImportError:
    raise ImportError("请先安装 pytdx：pip install pytdx pandas numpy")


# ============================================================
# 1. 候选股票池
# ============================================================

CANDIDATES = [

    "002916", "002463", "688012", "002371", "688120",
    "300308", "300502", "603986", "688041", "601138",

    "603228", "603920", "002384", "002938", "300476",
    "688072", "300604", "688008", "603893", "688521",

    "301308", "300475", "688525", "300857", "603019",
    "002281", "603083", "300620", "300913", "688498",

    "688200", "688019", "688037", "300567", "002156",
    "688099", "688608", "300496", "300458", "002241",

    "300223", "603160", "300408", "002475", "300433",
    "300548", "300570", "300394", "002436", "300739",

    "300782", "002859", "002815", "603328", "688256",
    "603881", "300383", "300738", "688111", "688018",

]

STOCK_NAME_OVERRIDES = {

    "002916": "深南电路",
    "002463": "沪电股份",
    "688012": "中微公司",
    "002371": "北方华创",
    "688120": "华海清科",

    "300308": "中际旭创",
    "300502": "新易盛",
    "603986": "兆易创新",
    "688041": "海光信息",
    "601138": "工业富联",

    "603228": "景旺电子",
    "603920": "世运电路",
    "002384": "东山精密",
    "002938": "鹏鼎控股",
    "300476": "胜宏科技",

    "688072": "拓荆科技",
    "300604": "长川科技",
    "688008": "澜起科技",
    "603893": "瑞芯微",
    "688521": "芯原股份",

    "301308": "江波龙",
    "300475": "香农芯创",
    "688525": "佰维存储",
    "300857": "协创数据",
    "603019": "中科曙光",

    "002281": "光迅科技",
    "603083": "剑桥科技",
    "300620": "光库科技",
    "300913": "兆龙互连",
    "688498": "源杰科技",

    "688200": "华峰测控",
    "688019": "安集科技",
    "688037": "芯源微",
    "300567": "精测电子",
    "002156": "通富微电",

    "688099": "晶晨股份",
    "688608": "恒玄科技",
    "300496": "中科创达",
    "300458": "全志科技",
    "002241": "歌尔股份",

    "300223": "北京君正",
    "603160": "汇顶科技",
    "300408": "三环集团",
    "002475": "立讯精密",
    "300433": "蓝思科技",

    "300548": "博创科技",
    "300570": "太辰光",
    "300394": "天孚通信",
    "002436": "兴森科技",
    "300739": "明阳电路",

    "300782": "卓胜微",
    "002859": "洁美科技",
    "002815": "崇达技术",
    "603328": "依顿电子",
    "688256": "寒武纪",

    "603881": "数据港",
    "300383": "光环新网",
    "300738": "奥飞数据",
    "688111": "金山办公",
    "688018": "乐鑫科技",
}

SAFETY_LEVEL = {

    "002916": "S",
    "002463": "S",
    "688012": "S",
    "002371": "S",
    "688120": "S",

    "300308": "S",
    "300502": "S",
    "603986": "S",
    "688041": "S",
    "601138": "S",

    "603228": "A+",
    "603920": "A+",
    "002384": "A+",
    "002938": "A+",
    "688072": "A+",

    "300604": "A+",
    "688008": "A+",
    "603893": "A+",
    "688200": "S",
    "688019": "S",

    "688037": "A+",
    "688099": "A+",
    "688608": "A+",
    "300496": "A+",

    "300476": "A",
    "688521": "A",
    "301308": "A",
    "300475": "A",
    "688525": "A",

    "300857": "A",
    "603019": "A",
    "002281": "A",
    "603083": "A",
    "300620": "A",

    "300913": "A",
    "300567": "A",
    "002156": "A",
    "300458": "A",
    "002241": "A",

    "300223": "A",
    "603160": "A",
    "300408": "A",
    "002475": "A",
    "300433": "A",

    "300548": "A",
    "300570": "A",
    "300394": "A",
    "002436": "A",

    "688498": "B+",
    "300739": "B+",
    "300782": "B+",
    "002859": "B+",
    "002815": "B+",

    "603328": "B+",
    "688256": "B+",
    "603881": "A",
    "300383": "B+",
    "300738": "B+",

    "688111": "B+",
    "688018": "A+",
}

SECTOR_TAG = {

    "002916": "PCB",
    "002463": "PCB",
    "603228": "PCB",
    "603920": "PCB",
    "002384": "PCB",

    "002938": "PCB",
    "300476": "PCB",
    "002436": "PCB",
    "300739": "PCB",
    "002815": "PCB",

    "603328": "PCB",

    "688012": "半导体设备",
    "002371": "半导体设备",
    "688120": "半导体设备",
    "688072": "半导体设备",
    "300604": "半导体设备",

    "688200": "半导体设备",
    "688037": "半导体设备",
    "300567": "半导体设备",

    "688019": "半导体材料",
    "002859": "半导体材料",

    "300308": "CPO",
    "300502": "CPO",
    "300394": "CPO",
    "300570": "CPO",
    "300548": "CPO",

    "603083": "CPO",
    "300620": "CPO",
    "002281": "光模块",
    "688498": "光芯片",
    "300913": "高速连接",

    "603986": "存储/MCU",
    "688008": "内存接口",
    "301308": "存储",
    "300475": "存储",
    "688525": "存储",

    "300223": "存储/芯片",
    "603160": "芯片",
    "300782": "射频芯片",
    "300408": "电子材料",

    "688041": "国产GPU",
    "601138": "AI服务器",
    "300857": "AI服务器",
    "603019": "国产算力",
    "688521": "芯片设计",

    "688629": "高速连接",
    "688256": "AI芯片",
    "603881": "数据中心",
    "300383": "数据中心",
    "300738": "数据中心",

    "603893": "AI端侧",
    "688099": "AI端侧",
    "688608": "AI端侧",
    "300496": "AI端侧",
    "300458": "AI端侧",

    "002241": "AI端侧",
    "688018": "AI端侧",
    "002475": "消费电子",
    "300433": "消费电子",
    "688111": "办公AI",
}


# ============================================================
# 2. 通达信服务器
# ============================================================

TDX_SERVERS = [
     ("119.147.212.81", 7709),
     ("14.215.128.18", 7709), 
     ("59.173.18.140", 7709), 
     ("218.75.126.9", 7709),  
     ("115.238.90.165", 7709),
     ("180.153.18.170", 7709),
]


def get_market(code):
    """
    通达信市场：
    0 = 深圳 / 创业板
    1 = 上海 / 科创板
    """
    return 1 if str(code).startswith("6") else 0


def connect_tdx():
    api = TdxHq_API()
    for host, port in TDX_SERVERS:
        try:
            if api.connect(host, port, time_out=1.5):
                print(f"已连接通达信服务器: {host}:{port}")
                return api
        except Exception:
            continue
    raise RuntimeError("通达信服务器连接失败，请稍后重试，或替换 TDX_SERVERS。")


# ============================================================
# 3. 数据获取
# ============================================================

def get_daily_bars(api, code, n=160):
    market = get_market(code)
    data = api.get_security_bars(9, market, code, 0, n)  # 9 = 日线
    if not data:
        return None
    df = api.to_df(data)
    if df is None or len(df) == 0:
        return None
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


# ============================================================
# 4. 指标计算
# ============================================================

def calc_indicators(df):
    df = df.copy()

    df["ma5"] = df["close"].rolling(5).mean()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()

    df["vol5"] = df["vol"].rolling(5).mean()
    df["vol20"] = df["vol"].rolling(20).mean()

    df["pct"] = df["close"].pct_change() * 100
    df["amp"] = (df["high"] - df["low"]) / df["close"].shift(1) * 100

    df["high20"] = df["high"].rolling(20).max()
    df["low20"] = df["low"].rolling(20).min()

    return df


def safety_score(level):
    if level == "S":
        return 30
    if level == "A+":
        return 24
    if level == "A":
        return 18
    if level == "B+":
        return 10
    return 5


def sector_bonus(sector):
    """
    当前主线倾向：
    PCB、半导体设备、CPO、存储、AI服务器、国产算力优先。
    """
    hot = {
        "PCB": 10,
        "半导体设备": 10,
        "CPO": 9,
        "光模块": 8,
        "内存接口": 8,
        "存储": 8,
        "存储/MCU": 8,
        "国产GPU": 8,
        "AI服务器": 8,
        "国产算力": 8,
        "AI端侧": 6,
        "芯片设计": 6,
        "高速连接": 6,
        "光芯片": 5,
    }
    return hot.get(sector, 3)


# ============================================================
# 5. 安全过滤器
# ============================================================

def risk_filter(code, df):
    """
    安全过滤器：
    目标不是预测天天涨，而是避免追高、避开趋势破坏、避开放量出货。
    """
    df = calc_indicators(df)

    if len(df) < 70:
        return False, "数据不足，无法判断安全性"

    last = df.iloc[-1]
    prev = df.iloc[-2]

    close = last["close"]
    high = last["high"]
    ma5 = last["ma5"]
    ma10 = last["ma10"]
    ma20 = last["ma20"]
    ma60 = last["ma60"]
    vol = last["vol"]
    vol20 = last["vol20"]

    pct = (close / prev["close"] - 1) * 100
    pullback_from_high = (high - close) / high * 100 if high > 0 else 0
    last3_pct = df["close"].pct_change().tail(3).sum() * 100
    last5_pct = df["close"].pct_change().tail(5).sum() * 100

    # 1. 跌破20日线，趋势明显变弱
    if close < ma20:
        return False, "跌破20日线，短线趋势走弱"

    # 2. 跌破10日线且当天弱势下跌
    if close < ma10 and pct < -2:
        return False, "跌破10日线且弱势下跌"

    # 3. 距离5日线太远，容易回踩
    if close > ma5 * 1.08:
        return False, "偏离5日线超过8%，追高风险高"

    # 4. 当天涨幅太大，次日震荡概率大
    if pct > 7:
        return False, "当天涨幅超过7%，不追高潮"

    # 5. 连续短期暴涨，降低安全性
    if last3_pct > 15:
        return False, "近3日涨幅过大，容易高位震荡"

    if last5_pct > 25:
        return False, "近5日涨幅过大，短线获利盘重"

    # 6. 放巨量且冲高回落，疑似短线出货
    if vol > vol20 * 2.5 and pullback_from_high > 4:
        return False, "放巨量冲高回落，短线风险偏高"

    # 7. 60日线之下不做强趋势
    if close < ma60:
        return False, "仍在60日线下方，中期趋势不强"

    return True, "风险可控"


# ============================================================
# 6. 核心分类逻辑
# ============================================================

def classify_stock(code, df):
    name = STOCK_NAME_OVERRIDES.get(code, code)
    level = SAFETY_LEVEL.get(code, "B+")
    sector = SECTOR_TAG.get(code, "其他")

    if df is None or len(df) < 70:
        return {
            "code": code,
            "name": name,
            "level": level,
            "sector": sector,
            "signal": "数据不足",
            "score": 0,
            "pct": np.nan,
            "pullback": np.nan,
            "close": np.nan,
            "ma5": np.nan,
            "ma10": np.nan,
            "reason": "K线数据不足",
        }

    df = calc_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(last["close"])
    high = float(last["high"])
    low = float(last["low"])
    ma5 = float(last["ma5"])
    ma10 = float(last["ma10"])
    ma20 = float(last["ma20"])
    ma60 = float(last["ma60"])
    vol = float(last["vol"])
    vol5 = float(last["vol5"])
    vol20 = float(last["vol20"])

    pct = (close / float(prev["close"]) - 1) * 100
    pullback = (high - close) / high * 100 if high > 0 else 0
    low_rebound = (close - low) / low * 100 if low > 0 else 0

    trend_good = close > ma10 > ma20 > ma60
    trend_ok = close > ma20 and ma20 > ma60
    near_ma5 = abs(close / ma5 - 1) * 100 <= 2.2
    near_ma10 = abs(close / ma10 - 1) * 100 <= 3.5
    volume_ok = vol >= vol5 * 0.80
    no_huge_volume = vol <= vol20 * 2.5
    pullback_good = pullback >= 1.2 and close >= ma5 * 0.985
    intraday_supported = low_rebound >= 1.0 or close >= ma5

    score = 0
    score += safety_score(level)
    score += sector_bonus(sector)

    if trend_good:
        score += 25
    elif trend_ok:
        score += 16

    if near_ma5:
        score += 12
    if near_ma10:
        score += 8
    if volume_ok:
        score += 8
    if no_huge_volume:
        score += 8

    if -3.5 <= pct <= 1.5:
        score += 15
    elif 1.5 < pct <= 4.5:
        score += 9
    elif 4.5 < pct <= 6.5:
        score += 3
    elif pct > 6.5:
        score -= 15

    if pullback_good:
        score += 10
    if intraday_supported:
        score += 8

    safe, risk_reason = risk_filter(code, df)

    if not safe:
        signal = "今天不进"
        reason = risk_reason

    elif level == "S" and trend_good and near_ma5 and -3.5 <= pct <= 1.5 and volume_ok:
        signal = "强买"
        reason = "S级核心，回踩5日线附近，趋势未坏，风险收益比最好"

    elif level in ["S", "A+"] and trend_good and near_ma5 and -4 <= pct <= 2.5 and volume_ok:
        signal = "尾盘低吸"
        reason = "机构核心，趋势未坏，回撤到均线附近，适合拿先手"

    elif level in ["S", "A+"] and trend_good and 0 < pct <= 4.5 and pullback >= 1.2:
        signal = "有回撤就进"
        reason = "强趋势票，涨幅不极端，盘中回撤后仍有承接"

    elif level in ["A", "A+"] and trend_ok and -3.5 <= pct <= 5.5 and no_huge_volume:
        signal = "观察可进"
        reason = "主线趋势仍在，但波动偏大，适合小仓低吸"

    else:
        signal = "观察"
        reason = "趋势未坏，但买点不够舒服"

    return {
        "code": code,
        "name": name,
        "level": level,
        "sector": sector,
        "signal": signal,
        "score": round(score, 1),
        "pct": round(pct, 2),
        "pullback": round(pullback, 2),
        "close": round(close, 2),
        "ma5": round(ma5, 2),
        "ma10": round(ma10, 2),
        "ma20": round(ma20, 2),
        "reason": reason,
    }


# ============================================================
# 7. 主程序
# ============================================================

def run_watchlist():
    api = connect_tdx()
    results = []

    try:
        for i, code in enumerate(CANDIDATES, 1):
            try:
                df = get_daily_bars(api, code, n=160)
                result = classify_stock(code, df)
                results.append(result)
                time.sleep(0.03)
            except Exception as e:
                results.append({
                    "code": code,
                    "name": STOCK_NAME_OVERRIDES.get(code, code),
                    "level": SAFETY_LEVEL.get(code, "B+"),
                    "sector": SECTOR_TAG.get(code, "其他"),
                    "signal": "错误",
                    "score": 0,
                    "pct": np.nan,
                    "pullback": np.nan,
                    "close": np.nan,
                    "ma5": np.nan,
                    "ma10": np.nan,
                    "ma20": np.nan,
                    "reason": str(e),
                })
    finally:
        try:
            api.disconnect()
        except Exception:
            pass

    out = pd.DataFrame(results)

    signal_order = {
        "强买": 0,
        "尾盘低吸": 1,
        "有回撤就进": 2,
        "观察可进": 3,
        "观察": 4,
        "今天不进": 5,
        "数据不足": 6,
        "错误": 7,
    }

    out["signal_order"] = out["signal"].map(signal_order).fillna(9)
    out = out.sort_values(["signal_order", "score"], ascending=[True, False])
    out = out.drop(columns=["signal_order"])

    print("\n================= 今日盯盘结果 =================\n")

    for sig in ["强买", "尾盘低吸", "有回撤就进", "观察可进", "观察", "今天不进", "数据不足", "错误"]:
        sub = out[out["signal"] == sig].copy()
        if len(sub) == 0:
            continue

        print(f"\n【{sig}】")
        cols = ["code", "name", "level", "sector", "score", "pct", "pullback", "close", "ma5", "ma10", "reason"]
        print(sub[cols].to_string(index=False))

    out.to_csv("tdx_watchlist_result.csv", index=False, encoding="utf-8-sig")
    print("\n结果已保存：tdx_watchlist_result.csv")
    print("\n使用建议：优先看【强买】【尾盘低吸】【有回撤就进】；【今天不进】不要硬追。")

    return out


if __name__ == "__main__":
    run_watchlist()

