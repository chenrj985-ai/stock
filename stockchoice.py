# -*- coding: utf-8 -*-
"""
A股主线候选股入场盯盘助手 v2.2（盘中稳定版）
------------------------------------------------
适合开盘后/盘中运行：
1. 实时行情只抓一次，避免频繁请求导致报错；
2. 每只股票的日K结构单独容错，失败不会导致整个程序退出；
3. 开盘前后接口不稳定时，会自动跳过异常股票；
4. 输出 Excel + CSV；
5. 更适合你盘中找“今天跌、但趋势还在、相对安全低吸”的股票。

安装：
    pip install akshare pandas openpyxl

运行：
    python stock_entry_watch_mainline_v22_intraday_safe.py
"""

import re
import time
import contextlib
import io
import datetime as dt
from pathlib import Path
import os
import random
import requests

import pandas as pd

try:
    import akshare as ak
except Exception:
    ak = None


# ===================== AKShare 网络稳定增强：禁代理 + 换域名 =====================
for key in [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
]:
    os.environ.pop(key, None)

os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

_old_request = requests.sessions.Session.request

def patched_request(self, method, url, **kwargs):
    """
    给 AKShare 内部所有 requests 请求加一层保护：
    1. 不读取 Windows/Clash/V2ray 的系统代理；
    2. 避开不稳定的 82.push2 节点；
    3. 设置超时，避免一直卡死。
    """
    self.trust_env = False

    # 不使用系统代理；不要写成代理地址，避免 ProxyError
    kwargs["proxies"] = {}

    if not kwargs.get("timeout"):
        kwargs["timeout"] = 20

    if isinstance(url, str) and "82.push2.eastmoney.com" in url:
        url = url.replace("82.push2.eastmoney.com", "push2.eastmoney.com")

    return _old_request(self, method, url, **kwargs)

requests.sessions.Session.request = patched_request


# ===================== 只改这里：直接粘贴候选股代码 =====================
CANDIDATES_TEXT = """
301308
300475
603986
688525
688120
688608
688256
688498
300567
300373
688041
688012
688008
688072
300308
300394
300570
300757
300548
300620
603893
603083
603920
603019
603881
603186
603228
300442
300499
002371
002463
300502
300223
300604
601138
300353
002916
002156
002837
002281
002636
002138
002429
002579
002384
002913
"""


RESULT_DIR = Path(__file__).resolve().parent / "results"


def safe_float(x, default=0.0):
    try:
        if x is None or pd.isna(x):
            return default
        s = str(x).replace("%", "").replace(",", "").strip()
        if s in ["-", "--", "", "None", "nan"]:
            return default
        return float(s)
    except Exception:
        return default


def normalize_code(code):
    return str(code).strip().zfill(6)


def parse_candidates():
    data = []
    seen = set()
    text = str(CANDIDATES_TEXT or "").strip()
    codes = re.findall(r"\b\d{1,6}\b", text)

    for code in codes:
        code = normalize_code(code)
        if code not in seen and code != "000000":
            seen.add(code)
            data.append((code, ""))

    return data


def quiet_call(func, *args, **kwargs):
    """
    AKShare稳定调用：
    1. 自动重试；
    2. 自动绕开代理；
    3. 东方财富偶尔断开时不会马上崩。
    """
    last_error = None

    for i in range(8):
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = func(*args, **kwargs)

            if result is not None:
                return result

        except Exception as e:
            last_error = e
            wait = 2 + i * 2 + random.random()
            print(f"AKShare请求失败 {i + 1}/8 次：{type(e).__name__}")
            print(f"{wait:.1f} 秒后重试...\n")
            time.sleep(wait)

    raise RuntimeError(f"AKShare连续失败：{last_error}")



def direct_request_json(url, params, retry=5):
    """AKShare 全部失败时的备用请求，仍取东方财富同源数据。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/center/gridlist.html",
        "Accept": "application/json,text/plain,*/*",
        "Connection": "close",
    }
    last_error = None

    for i in range(retry):
        try:
            session = requests.Session()
            session.trust_env = False
            r = session.get(url, params=params, headers=headers, timeout=20, proxies={})
            r.raise_for_status()
            data = r.json()
            if data:
                return data
        except Exception as e:
            last_error = e
            wait = 2 + i * 2 + random.random()
            print(f"备用直连失败 {i + 1}/{retry} 次：{type(e).__name__}，{wait:.1f} 秒后重试")
            time.sleep(wait)

    raise RuntimeError(f"备用直连也失败：{last_error}")


def get_market_data_direct():
    """备用：不用 AKShare 封装，直接按东方财富全市场接口取实时行情。"""
    urls = [
        "https://push2.eastmoney.com/api/qt/clist/get",
        "https://82.push2.eastmoney.com/api/qt/clist/get",
    ]
    params = {
        "pn": "1",
        "pz": "6000",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
        "fields": "f2,f3,f5,f6,f8,f10,f12,f14",
    }

    last_error = None
    for url in urls:
        try:
            data = direct_request_json(url, params, retry=4)
            diff = data.get("data", {}).get("diff", [])
            if not diff:
                raise RuntimeError("备用接口返回为空")

            rows = []
            for item in diff:
                rows.append({
                    "代码": str(item.get("f12", "")).zfill(6),
                    "名称": str(item.get("f14", "")),
                    "现价": safe_float(item.get("f2")),
                    "今日涨跌幅%": safe_float(item.get("f3")),
                    "成交额亿": safe_float(item.get("f6")) / 100000000,
                    "换手率%": safe_float(item.get("f8")),
                    "量比": safe_float(item.get("f10"), 1.0),
                })
            return pd.DataFrame(rows)
        except Exception as e:
            last_error = e
            print(f"备用域名失败：{url}，原因：{type(e).__name__}")

    raise RuntimeError(f"两个东方财富域名都失败：{last_error}")

def get_market_data(retry=3, sleep_seconds=2):
    """
    获取全市场实时行情。
    盘中版本只调用一次，避免每只股票重复请求。
    """
    if ak is None:
        print("没有安装 akshare，改用东方财富备用直连接口。")
        return get_market_data_direct()

    last_error = None

    for i in range(retry):
        try:
            spot = quiet_call(ak.stock_zh_a_spot_em)

            if spot is None or spot.empty:
                raise RuntimeError("实时行情返回为空，可能是接口暂时不可用。")

            required_cols = ["代码", "名称", "最新价", "涨跌幅", "成交额", "换手率"]
            missing = [c for c in required_cols if c not in spot.columns]
            if missing:
                raise RuntimeError(f"实时行情字段缺失：{missing}")

            df = pd.DataFrame()
            df["代码"] = spot["代码"].astype(str).str.zfill(6)
            df["名称"] = spot["名称"].astype(str)
            df["现价"] = spot["最新价"].map(safe_float)
            df["今日涨跌幅%"] = spot["涨跌幅"].map(safe_float)
            df["成交额亿"] = spot["成交额"].map(safe_float) / 100000000
            df["换手率%"] = spot["换手率"].map(safe_float)
            df["量比"] = spot["量比"].map(safe_float) if "量比" in spot.columns else 1.0

            return df

        except Exception as e:
            last_error = e
            print(f"实时行情获取失败，第 {i + 1}/{retry} 次重试：{e}")
            time.sleep(sleep_seconds)

    print("AKShare 实时行情连续失败，改用东方财富备用直连接口。")
    try:
        return get_market_data_direct()
    except Exception as e:
        raise RuntimeError(f"实时行情连续失败。AKShare最后错误：{last_error}；备用接口错误：{e}")


def get_recent_kline(code):
    """
    获取最近日K。
    注意：
    - 盘中接口可能不稳定；
    - 如果失败，返回默认结构，不让程序崩溃；
    - 这样盘中至少还能基于实时行情给出判断。
    """
    default_k = {
        "近3日涨跌幅": "",
        "近5日累计涨跌幅": "",
        "近10日累计涨跌幅": "",
        "前2日连续上涨": False,
        "前2日连续下跌": False,
        "站上5日线": False,
        "站上10日线": False,
        "站上20日线": False,
        "成交额相对5日均值": 1.0,
        "强趋势": False,
        "K线状态": "K线未取到",
    }

    try:
        time.sleep(0.5)  # 降低盘中被限流概率

        hist = quiet_call(ak.stock_zh_a_hist, symbol=code, period="daily", adjust="")
        if hist is None or hist.empty:
            return default_k

        hist = hist.tail(35).copy()

        for col in ["涨跌幅", "收盘", "成交额"]:
            if col not in hist.columns:
                return default_k

        pct = [safe_float(x) for x in hist["涨跌幅"].tolist()]
        close = [safe_float(x) for x in hist["收盘"].tolist()]
        amount = [safe_float(x) for x in hist["成交额"].tolist()]

        pct = [x for x in pct if x is not None]
        close = [x for x in close if x > 0]
        amount = [x for x in amount if x >= 0]

        if len(close) < 20 or len(pct) < 10:
            return default_k

        last_close = close[-1]
        ma5 = sum(close[-5:]) / 5
        ma10 = sum(close[-10:]) / 10
        ma20 = sum(close[-20:]) / 20

        prev2 = pct[-3:-1] if len(pct) >= 3 else pct[-2:]
        last3 = pct[-3:] if len(pct) >= 3 else pct

        amount_today = amount[-1] if amount else 0
        amount_ma5 = sum(amount[-6:-1]) / 5 if len(amount) >= 6 else 0
        amount_ratio_5d = amount_today / amount_ma5 if amount_ma5 > 0 else 1.0

        recent5_sum = sum(pct[-5:]) if len(pct) >= 5 else 0
        recent10_sum = sum(pct[-10:]) if len(pct) >= 10 else 0

        strong_trend = recent10_sum >= 8 and last_close >= ma10

        return {
            "近3日涨跌幅": ",".join([f"{x:.2f}" for x in last3]),
            "近5日累计涨跌幅": round(recent5_sum, 2),
            "近10日累计涨跌幅": round(recent10_sum, 2),
            "前2日连续上涨": len(prev2) >= 2 and all(x > 0 for x in prev2),
            "前2日连续下跌": len(prev2) >= 2 and all(x < 0 for x in prev2),
            "站上5日线": last_close >= ma5,
            "站上10日线": last_close >= ma10,
            "站上20日线": last_close >= ma20,
            "成交额相对5日均值": round(amount_ratio_5d, 2),
            "强趋势": strong_trend,
            "K线状态": "正常",
        }

    except Exception as e:
        default_k["K线状态"] = f"K线异常：{str(e)[:50]}"
        return default_k


def judge_volume_price(day_pct, volume_ratio, amount_ratio_5d):
    if day_pct >= 3:
        if volume_ratio >= 1 and amount_ratio_5d >= 1:
            return "上涨放量接力"
        if volume_ratio < 0.8 or amount_ratio_5d < 0.8:
            return "上涨缩量诱多"
        return "上涨量能一般"

    if 1 <= day_pct < 3:
        if volume_ratio >= 0.8 and amount_ratio_5d >= 0.8:
            return "温和上涨健康"
        return "温和上涨但量弱"

    if -1 < day_pct < 1:
        if 0.7 <= volume_ratio <= 2.5:
            return "震荡量能正常"
        if volume_ratio > 3:
            return "震荡异常放量"
        return "震荡量能偏弱"

    if -4 <= day_pct <= -1:
        if volume_ratio >= 1.3 or amount_ratio_5d >= 1.2:
            return "放量回调"
        if volume_ratio <= 0.9 and amount_ratio_5d <= 1.0:
            return "缩量回调"
        return "普通回调"

    if day_pct < -4:
        if volume_ratio >= 1.3 or amount_ratio_5d >= 1.2:
            return "大跌放量"
        return "大跌未明显放量"

    return "量价不明"


def diagnose_entry(code, note, market_row):
    name = market_row["名称"]
    price = safe_float(market_row["现价"])
    day_pct = safe_float(market_row["今日涨跌幅%"])
    amount_yi = safe_float(market_row["成交额亿"])
    turnover = safe_float(market_row["换手率%"])
    volume_ratio = safe_float(market_row["量比"], 1.0)

    k = get_recent_kline(code)

    amount_ratio_5d = safe_float(k.get("成交额相对5日均值", 1.0), 1.0)
    volume_price = judge_volume_price(day_pct, volume_ratio, amount_ratio_5d)

    above_ma5 = bool(k.get("站上5日线", False))
    above_ma10 = bool(k.get("站上10日线", False))
    above_ma20 = bool(k.get("站上20日线", False))
    strong_trend = bool(k.get("强趋势", False))
    prev2_up = bool(k.get("前2日连续上涨", False))
    prev2_down = bool(k.get("前2日连续下跌", False))
    k_status = k.get("K线状态", "")

    score = 50
    entry_reasons = []
    risk_reasons = []
    watch_reasons = []
    tactic = []

    score += 6
    watch_reasons.append("主线候选池股票，按强股回调低吸逻辑处理")

    # K线异常时，降低对均线结构的依赖
    kline_ok = (k_status == "正常")

    # 1. 今日涨跌位置
    if -5.5 <= day_pct <= -2:
        score += 25
        entry_reasons.append("今日处于较理想低吸区间")
    elif -2 < day_pct <= 1:
        score += 12
        watch_reasons.append("小跌/微涨，适合观察分时承接")
    elif day_pct < -5.5:
        score -= 8
        risk_reasons.append("跌幅过深，不能盲目接")
    elif 1 < day_pct <= 3:
        score -= 5
        watch_reasons.append("已经上涨，适合等回落，不宜追高")
    elif day_pct > 3:
        score -= 20
        risk_reasons.append("涨幅较大，不符合低吸")

    # 2. 量价状态
    if volume_price == "缩量回调":
        score += 18
        entry_reasons.append("缩量回调，更像健康洗盘")
        tactic.append("可重点观察低吸")
    elif volume_price == "普通回调":
        score += 10
        watch_reasons.append("普通回调，需看分时承接")
    elif volume_price == "放量回调":
        if kline_ok and above_ma10 and day_pct > -4:
            score += 16
            entry_reasons.append("放量回调但仍在10日线附近或之上，可能是假跌")
        elif kline_ok and above_ma20:
            score += 3
            watch_reasons.append("放量回调但主趋势尚未完全破坏")
        else:
            score -= 6
            risk_reasons.append("放量回调，需要防止真分歧")
    elif volume_price == "大跌放量":
        if kline_ok and above_ma10 and amount_yi >= 10:
            score += 8
            entry_reasons.append("大跌放量但结构尚可，主线股可能是假跌")
            tactic.append("只适合小仓试，不适合重仓")
        else:
            score -= 18
            risk_reasons.append("大跌放量，真风险概率上升")
    elif volume_price == "大跌未明显放量":
        if kline_ok and above_ma10:
            score += 8
            entry_reasons.append("大跌未明显放量且未破10日线，可能是情绪错杀")
        else:
            score -= 5
            risk_reasons.append("大跌但结构不明，谨慎")
    elif volume_price == "上涨放量接力":
        score += 3
        watch_reasons.append("上涨放量，强但不是低吸点")
        risk_reasons.append("不建议追高，等回落")
    elif volume_price == "上涨缩量诱多":
        score -= 15
        risk_reasons.append("上涨缩量，容易冲高回落")
    elif volume_price == "温和上涨健康":
        score += 2
        watch_reasons.append("温和上涨健康，更适合持有不适合新追")
    elif volume_price == "震荡量能正常":
        score += 5
        watch_reasons.append("震荡量能正常，可继续盯")
    elif volume_price == "震荡异常放量":
        score -= 5
        risk_reasons.append("震荡异常放量，方向不明")

    # 3. K线结构，只有K线正常时才强判断
    if kline_ok:
        if above_ma5:
            score += 4
            watch_reasons.append("站上5日线，短线结构尚可")
        else:
            score -= 4
            risk_reasons.append("跌破5日线，短线弱化")

        if above_ma10:
            score += 10
            entry_reasons.append("站上10日线，中短线结构仍在")
        else:
            score -= 10
            risk_reasons.append("跌破10日线，需谨慎")

        if above_ma20:
            score += 8
            watch_reasons.append("站上20日线，主趋势尚未破坏")
        else:
            score -= 15
            risk_reasons.append("跌破20日线，主线股也要防趋势转弱")

        if strong_trend and day_pct < 0 and above_ma10:
            score += 12
            entry_reasons.append("强趋势股回调未破10日线，属于较优低吸形态")
        elif strong_trend:
            score += 5
            watch_reasons.append("强趋势股，仍值得跟踪")

        if prev2_up and day_pct > 1:
            score -= 18
            risk_reasons.append("前2日连续上涨且今日继续涨，不符合低吸")
        elif prev2_up and day_pct < 0:
            score += 5
            watch_reasons.append("连续上涨后回调，若不破结构可观察")
        elif prev2_down and -5.5 <= day_pct <= -2 and above_ma10:
            score += 10
            entry_reasons.append("连续回调后进入低吸区且未破10日线")
    else:
        score -= 3
        risk_reasons.append("盘中K线数据未稳定取到，本次主要参考实时行情")

    # 4. 流动性
    if amount_yi >= 20:
        score += 14
        entry_reasons.append("成交额强，流动性好")
    elif amount_yi >= 8:
        score += 8
        watch_reasons.append("成交额尚可")
    elif amount_yi >= 3:
        score += 2
        watch_reasons.append("成交额一般")
    else:
        score -= 12
        risk_reasons.append("成交额偏低，承接不足")

    # 5. 换手
    if 2 <= turnover <= 10:
        score += 8
        watch_reasons.append("换手适中，符合活跃主线股")
    elif 10 < turnover <= 18:
        score -= 2
        risk_reasons.append("换手偏高，波动大")
    elif turnover > 18:
        score -= 12
        risk_reasons.append("换手过热，容易剧烈分歧")
    elif turnover < 0.8:
        score -= 5
        risk_reasons.append("换手偏低，资金关注不足")

    # 6. 硬风险
    hard_risk = (
        (kline_ok and (not above_ma20) and day_pct <= -4)
        or (volume_price == "大跌放量" and (not kline_ok or not above_ma10))
        or (day_pct > 3)
    )

    if hard_risk and score < 70:
        level = "回避"
        action = "暂不入场"
        detail = "结构或位置不合适，等重新站稳再看"
    elif score >= 85 and day_pct <= 1:
        level = "S级入场机会"
        action = "可小仓入场"
        detail = "主线回调形态较好，但仍建议分批，不要一把梭"
    elif score >= 72 and day_pct <= 1.5:
        level = "A级低吸观察"
        action = "重点盯盘"
        detail = "具备低吸条件，建议结合分时承接再决定"
    elif score >= 58:
        level = "继续观察"
        action = "观察"
        detail = "信号尚可，但入场确定性不足"
    elif score >= 42:
        level = "谨慎"
        action = "谨慎观察"
        detail = "有风险点，不适合急买"
    else:
        level = "回避"
        action = "暂不入场"
        detail = "不符合当前低吸条件"

    return {
        "代码": code,
        "名称": name,
        "现价": round(price, 2),
        "今日涨跌幅%": round(day_pct, 2),
        "成交额亿": round(amount_yi, 2),
        "换手率%": round(turnover, 2),
        "量比": round(volume_ratio, 2),
        "成交额相对5日均值": amount_ratio_5d,
        "量价状态": volume_price,
        "近3日涨跌幅": k.get("近3日涨跌幅", ""),
        "近5日累计涨跌幅": k.get("近5日累计涨跌幅", ""),
        "近10日累计涨跌幅": k.get("近10日累计涨跌幅", ""),
        "前2日连续上涨": "是" if prev2_up else "否",
        "前2日连续下跌": "是" if prev2_down else "否",
        "站上5日线": "是" if above_ma5 else "否",
        "站上10日线": "是" if above_ma10 else "否",
        "站上20日线": "是" if above_ma20 else "否",
        "强趋势": "是" if strong_trend else "否",
        "K线状态": k_status,
        "入场等级": level,
        "动作建议": action,
        "操作细节": detail,
        "评分": round(score, 1),
        "入场理由": "；".join(entry_reasons),
        "观察理由": "；".join(watch_reasons),
        "风险提示": "；".join(risk_reasons),
        "执行提示": "；".join(tactic),
        "备注": note,
    }


def main():
    print("正在运行：A股主线候选股入场盯盘助手 v2.2 盘中稳定版")
    print("正在获取实时行情……")

    RESULT_DIR.mkdir(exist_ok=True)

    try:
        market = get_market_data()
    except Exception as e:
        print("")
        print("实时行情获取失败，程序停止。")
        print("原因可能是：开盘前后接口拥堵、网络问题、AKShare接口变动。")
        print(f"错误信息：{e}")
        return

    candidates = parse_candidates()

    if not candidates:
        print("没有解析到候选股代码。请检查 CANDIDATES_TEXT 是否填写了6位股票代码。")
        return

    rows = []
    total = len(candidates)

    for idx, (code, note) in enumerate(candidates, start=1):
        print(f"正在分析 {idx}/{total}：{code}")

        try:
            row = market[market["代码"] == code]
            if row.empty:
                rows.append({
                    "代码": code,
                    "名称": "",
                    "现价": "",
                    "今日涨跌幅%": "",
                    "成交额亿": "",
                    "换手率%": "",
                    "量比": "",
                    "量价状态": "",
                    "K线状态": "未取到实时行情",
                    "入场等级": "未取到行情",
                    "动作建议": "检查代码",
                    "操作细节": "可能是代码错误、退市、停牌或接口未返回",
                    "评分": 0,
                    "风险提示": "未取到行情",
                    "备注": note
                })
                continue

            rows.append(diagnose_entry(code, note, row.iloc[0]))

        except Exception as e:
            rows.append({
                "代码": code,
                "名称": "",
                "现价": "",
                "今日涨跌幅%": "",
                "成交额亿": "",
                "换手率%": "",
                "量比": "",
                "量价状态": "",
                "K线状态": f"单股异常：{str(e)[:80]}",
                "入场等级": "程序异常",
                "动作建议": "跳过",
                "操作细节": "该股本次分析失败，但不影响其他股票",
                "评分": 0,
                "风险提示": str(e)[:120],
                "备注": note
            })

    result = pd.DataFrame(rows)

    rank_map = {
        "S级入场机会": 0,
        "A级低吸观察": 1,
        "继续观察": 2,
        "谨慎": 3,
        "回避": 4,
        "未取到行情": 5,
        "程序异常": 6,
    }

    if not result.empty:
        result["_rank"] = result["入场等级"].map(rank_map).fillna(9)
        result = result.sort_values(["_rank", "评分"], ascending=[True, False]).drop(columns=["_rank"])

    now_str = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = RESULT_DIR / f"主线候选入场盯盘_盘中稳定版_{now_str}.csv"
    xlsx_path = RESULT_DIR / f"主线候选入场盯盘_盘中稳定版_{now_str}.xlsx"

    result.to_csv(csv_path, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        result.to_excel(writer, index=False, sheet_name="入场盯盘")
        ws = writer.book["入场盯盘"]
        ws.freeze_panes = "A2"

        for col in ws.columns:
            max_len = 10
            letter = col[0].column_letter
            for cell in col:
                try:
                    max_len = max(max_len, min(len(str(cell.value)), 55))
                except Exception:
                    pass
            ws.column_dimensions[letter].width = max_len + 2

    print("")
    print("分析完成。")
    print(f"Excel结果：{xlsx_path}")
    print(f"CSV结果：{csv_path}")
    print("")
    print("简要结论：")

    show_cols = ["代码", "名称", "今日涨跌幅%", "量价状态", "入场等级", "动作建议", "评分", "K线状态"]
    for _, r in result.head(15).iterrows():
        print(
            f"{r.get('代码', '')} {r.get('名称', '')} | "
            f"{r.get('今日涨跌幅%', '')}% | "
            f"{r.get('量价状态', '')} | "
            f"{r.get('入场等级', '')} | "
            f"{r.get('动作建议', '')} | "
            f"评分 {r.get('评分', '')} | "
            f"{r.get('K线状态', '')}"
        )

    print("")
    print("提示：")
    print("1. 9:25-9:35 接口最容易不稳定，建议 9:35 后跑。")
    print("2. 盘中结果主要看实时涨跌幅、成交额、量比、换手率。")
    print("3. K线状态如果显示异常，不代表股票不能看，只代表接口本次没稳定取到。")
    print("4. 本程序只做盯盘筛选，不构成投资建议，实际买卖仍要小仓、分批、设止损。")


if __name__ == "__main__":
    main()
