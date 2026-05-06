# -*- coding: utf-8 -*-
import os
import re
import time
import random
import datetime as dt
from pathlib import Path

import pandas as pd
import requests


# ===================== 强制禁用代理 =====================
for key in [
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "ALL_PROXY", "all_proxy",
    "NO_PROXY", "no_proxy"
]:
    os.environ.pop(key, None)

os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"


# ===================== 股票池：只改这里 =====================
CANDIDATES_TEXT = """
301308
300475
603986
688525
688120
688608
688256
688498
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
002463
300502
300223
300604
601138
300353
688037
002916
002938
603516
605111
"""

RESULT_DIR = Path(__file__).resolve().parent / "results"


def safe_float(x, default=0.0):
    try:
        if x in ["-", None, ""]:
            return default
        return float(str(x).replace(",", "").replace("%", ""))
    except Exception:
        return default


def normalize_code(code):
    return str(code).strip().zfill(6)


def parse_candidates():
    data, seen = [], set()
    codes = re.findall(r"\b\d{1,6}\b", CANDIDATES_TEXT)
    for code in codes:
        code = normalize_code(code)
        if code not in seen and code != "000000":
            seen.add(code)
            data.append(code)
    return data


def get_market_code(code):
    """
    东方财富市场编码：
    0 = 深市
    1 = 沪市
    """
    if code.startswith(("6", "9")):
        return "1"
    return "0"


def request_json(url, params=None, retry=8):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://quote.eastmoney.com/",
        "Accept": "application/json,text/plain,*/*",
    }

    session = requests.Session()
    session.trust_env = False

    last_err = None
    for i in range(retry):
        try:
            r = session.get(
                url,
                params=params,
                headers=headers,
                timeout=15,
                proxies={"http": None, "https": None},
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            wait = 1.5 + i * 1.5 + random.random()
            print(f"网络第{i+1}次失败，{wait:.1f}秒后重试：{type(e).__name__}")
            time.sleep(wait)

    raise RuntimeError(f"多次请求失败：{last_err}")


def fetch_one_stock(code):
    """
    只取单只股票实时行情，不拉全市场，稳定很多。
    """
    market = get_market_code(code)
    secid = f"{market}.{code}"

    url = "https://push2.eastmoney.com/api/qt/stock/get"

    params = {
        "secid": secid,
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields": "f43,f44,f45,f46,f47,f48,f49,f50,f57,f58,f60,f168,f169,f170",
    }

    data = request_json(url, params=params)
    d = data.get("data") or {}

    price = safe_float(d.get("f43")) / 100
    high = safe_float(d.get("f44")) / 100
    low = safe_float(d.get("f45")) / 100
    open_price = safe_float(d.get("f46")) / 100
    volume = safe_float(d.get("f47"))
    amount = safe_float(d.get("f48"))
    volume_ratio = safe_float(d.get("f50"), 1.0)
    pre_close = safe_float(d.get("f60")) / 100
    turnover = safe_float(d.get("f168")) / 100
    pct = safe_float(d.get("f170")) / 100

    return {
        "代码": code,
        "名称": d.get("f58", ""),
        "现价": round(price, 2),
        "今开": round(open_price, 2),
        "最高": round(high, 2),
        "最低": round(low, 2),
        "昨收": round(pre_close, 2),
        "今日涨跌幅%": round(pct, 2),
        "成交额亿": round(amount / 100000000, 2),
        "成交量": volume,
        "换手率%": round(turnover, 2),
        "量比": round(volume_ratio, 2),
    }


def fetch_kline(code):
    """
    获取日K线。失败不影响主程序。
    """
    market = get_market_code(code)
    secid = f"{market}.{code}"

    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

    params = {
        "secid": secid,
        "klt": "101",
        "fqt": "0",
        "lmt": "30",
        "end": "20500101",
        "iscca": "1",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
    }

    try:
        data = request_json(url, params=params, retry=4)
        klines = data.get("data", {}).get("klines", [])
        rows = []
        for line in klines:
            arr = line.split(",")
            rows.append({
                "日期": arr[0],
                "开盘": safe_float(arr[1]),
                "收盘": safe_float(arr[2]),
                "最高": safe_float(arr[3]),
                "最低": safe_float(arr[4]),
                "成交量": safe_float(arr[5]),
                "成交额": safe_float(arr[6]),
                "振幅": safe_float(arr[7]),
                "涨跌幅": safe_float(arr[8]),
                "涨跌额": safe_float(arr[9]),
                "换手率": safe_float(arr[10]),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


def kline_info(code):
    hist = fetch_kline(code)

    if hist.empty or len(hist) < 20:
        return {
            "近3日涨跌幅": "",
            "近5日累计涨跌幅": "",
            "近10日累计涨跌幅": "",
            "站上5日线": "",
            "站上10日线": "",
            "站上20日线": "",
            "成交额相对5日均值": 1.0,
            "强趋势": "",
        }

    close = hist["收盘"].tolist()
    pct = hist["涨跌幅"].tolist()
    amount = hist["成交额"].tolist()

    last_close = close[-1]
    ma5 = sum(close[-5:]) / 5
    ma10 = sum(close[-10:]) / 10
    ma20 = sum(close[-20:]) / 20

    amount_today = amount[-1]
    amount_ma5 = sum(amount[-6:-1]) / 5 if len(amount) >= 6 else 0
    amount_ratio = amount_today / amount_ma5 if amount_ma5 > 0 else 1.0

    recent5 = sum(pct[-5:])
    recent10 = sum(pct[-10:])

    return {
        "近3日涨跌幅": ",".join([f"{x:.2f}" for x in pct[-3:]]),
        "近5日累计涨跌幅": round(recent5, 2),
        "近10日累计涨跌幅": round(recent10, 2),
        "站上5日线": "是" if last_close >= ma5 else "否",
        "站上10日线": "是" if last_close >= ma10 else "否",
        "站上20日线": "是" if last_close >= ma20 else "否",
        "成交额相对5日均值": round(amount_ratio, 2),
        "强趋势": "是" if recent10 >= 8 and last_close >= ma10 else "否",
    }


def judge_volume_price(day_pct, volume_ratio, amount_ratio_5d):
    if day_pct >= 3:
        if volume_ratio >= 1.0 and amount_ratio_5d >= 1.0:
            return "上涨放量接力"
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


def diagnose(row):
    code = row["代码"]
    k = kline_info(code)

    day_pct = safe_float(row["今日涨跌幅%"])
    amount_yi = safe_float(row["成交额亿"])
    turnover = safe_float(row["换手率%"])
    volume_ratio = safe_float(row["量比"], 1.0)
    amount_ratio = safe_float(k.get("成交额相对5日均值", 1.0), 1.0)

    volume_price = judge_volume_price(day_pct, volume_ratio, amount_ratio)

    score = 50
    reasons = []
    risks = []

    if -5.5 <= day_pct <= -2:
        score += 25
        reasons.append("处于理想低吸区间")
    elif -2 < day_pct <= 1:
        score += 12
        reasons.append("小跌或微涨，适合观察承接")
    elif 1 < day_pct <= 3:
        score -= 3
        reasons.append("已有上涨，不适合追高")
    elif day_pct > 3:
        score -= 18
        risks.append("涨幅偏大，追高风险增加")
    elif day_pct < -5.5:
        score -= 12
        risks.append("跌幅过深，需防趋势破坏")

    if volume_price == "缩量回调":
        score += 18
        reasons.append("缩量回调，更像健康洗盘")
    elif volume_price == "普通回调":
        score += 8
        reasons.append("普通回调，需看尾盘承接")
    elif volume_price == "放量回调":
        score += 3
        risks.append("放量回调，需防资金分歧")
    elif volume_price == "震荡量能正常":
        score += 8
        reasons.append("震荡量能正常")
    elif volume_price == "震荡异常放量":
        score -= 5
        risks.append("震荡异常放量，方向不明")
    elif volume_price == "大跌放量":
        score -= 20
        risks.append("大跌放量，短线风险偏高")

    if k.get("站上5日线") == "是":
        score += 4
    elif k.get("站上5日线") == "否":
        score -= 4
        risks.append("跌破5日线")

    if k.get("站上10日线") == "是":
        score += 10
        reasons.append("站上10日线，中短线结构仍在")
    elif k.get("站上10日线") == "否":
        score -= 8
        risks.append("跌破10日线")

    if k.get("站上20日线") == "是":
        score += 8
        reasons.append("站上20日线，主趋势未破")
    elif k.get("站上20日线") == "否":
        score -= 12
        risks.append("跌破20日线")

    if k.get("强趋势") == "是" and day_pct < 0:
        score += 10
        reasons.append("强趋势回调，仍有修复可能")

    if amount_yi >= 20:
        score += 14
        reasons.append("成交额强，流动性好")
    elif amount_yi >= 8:
        score += 8
        reasons.append("成交额尚可")
    elif amount_yi >= 3:
        score += 2
    else:
        score -= 10
        risks.append("成交额偏低，承接不足")

    if 2 <= turnover <= 10:
        score += 8
        reasons.append("换手适中")
    elif 10 < turnover <= 18:
        score -= 2
        risks.append("换手偏高，波动较大")
    elif turnover > 18:
        score -= 12
        risks.append("换手过热")
    elif turnover < 0.8:
        score -= 5
        risks.append("换手偏低")

    if score >= 85 and day_pct <= 1:
        level = "S级入场机会"
        action = "可小仓入场"
    elif score >= 72 and day_pct <= 1.5:
        level = "A级低吸观察"
        action = "重点盯盘"
    elif score >= 58:
        level = "继续观察"
        action = "观察"
    elif score >= 42:
        level = "谨慎"
        action = "谨慎观察"
    else:
        level = "回避"
        action = "暂不入场"

    result = dict(row)
    result.update(k)
    result.update({
        "量价状态": volume_price,
        "入场等级": level,
        "动作建议": action,
        "评分": round(score, 1),
        "理由": "；".join(reasons),
        "风险提示": "；".join(risks),
    })
    return result


def main():
    print("正在运行：无代理直连东方财富稳定版")
    print("特点：不用AKShare实时行情，只按股票池逐只获取，稳定性更高。")

    RESULT_DIR.mkdir(exist_ok=True)

    codes = parse_candidates()
    if not codes:
        print("没有解析到股票代码。")
        return

    rows = []
    for idx, code in enumerate(codes, 1):
        try:
            print(f"正在获取 {idx}/{len(codes)}：{code}")
            row = fetch_one_stock(code)
            rows.append(diagnose(row))
            time.sleep(0.25)
        except Exception as e:
            rows.append({
                "代码": code,
                "名称": "",
                "入场等级": "未取到行情",
                "动作建议": "检查网络或代码",
                "评分": 0,
                "风险提示": str(e),
            })

    result = pd.DataFrame(rows)

    rank_map = {
        "S级入场机会": 0,
        "A级低吸观察": 1,
        "继续观察": 2,
        "谨慎": 3,
        "回避": 4,
        "未取到行情": 5,
    }

    result["_rank"] = result["入场等级"].map(rank_map).fillna(9)
    result = result.sort_values(["_rank", "评分"], ascending=[True, False]).drop(columns=["_rank"])

    now_str = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = RESULT_DIR / f"主线候选入场盯盘_无代理稳定版_{now_str}.csv"
    xlsx_path = RESULT_DIR / f"主线候选入场盯盘_无代理稳定版_{now_str}.xlsx"

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

    print("\n分析完成。")
    print(f"Excel结果：{xlsx_path}")
    print(f"CSV结果：{csv_path}")

    print("\n前15只简要结论：")
    for _, r in result.head(15).iterrows():
        print(
            f"{r.get('代码','')} {r.get('名称','')} | "
            f"{r.get('今日涨跌幅%','')}% | "
            f"{r.get('量价状态','')} | "
            f"{r.get('入场等级','')} | "
            f"{r.get('动作建议','')} | "
            f"评分 {r.get('评分','')}"
        )


if __name__ == "__main__":
    main()
