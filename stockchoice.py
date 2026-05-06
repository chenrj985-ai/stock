# -*- coding: utf-8 -*-
"""
A股主线候选股入场盯盘助手 v2.1（最终便捷版）
------------------------------------------------
适合你的用法：
1. 先让 ChatGPT 给你 30~50 只主线候选股；
2. 直接把股票代码粘贴到 CANDIDATES_TEXT 里；
3. 不需要加引号，不需要逗号；
4. 程序根据当前行情 + K线结构 + 量价关系判断：
   - S级入场机会
   - A级低吸观察
   - 继续观察
   - 谨慎
   - 回避

核心逻辑：
主线活跃股不能简单认为“大跌=危险”。
更合理的是：
- 大跌但不破10日/20日线，且成交额足够：可能是假跌/洗盘，是低吸机会；
- 大跌且破10日/20日线，且放量：偏真风险；
- 小跌/微涨且量能健康：观察；
- 连续上涨后继续冲高：不追；
- 缩量回调：偏健康；
- 放量回调但结构未破：可观察低吸。

安装：
    pip install akshare pandas openpyxl

运行：
    python stock_entry_watch_mainline_v21.py

输出：
    results/主线候选入场盯盘_YYYYMMDD_HHMMSS.xlsx
    results/主线候选入场盯盘_YYYYMMDD_HHMMSS.csv
"""

import re
import contextlib
import io
import datetime as dt
from pathlib import Path

import pandas as pd

try:
    import akshare as ak
except Exception:
    ak = None


# ===================== 只改这里：直接粘贴候选股代码 =====================
# 支持这些格式：
# 1）一行一个代码：
# 301308
# 300475
#
# 2）一行多个代码：
# 301308 300475 603986
#
# 3）带逗号：
# 301308,300475,603986
#
# 4）从表格复制出来：
# 301308    江波龙
# 300475    香农芯创

CANDIDATES_TEXT = """
300308
300502
300394
002463
603083
300548
300570
300476
002938
603228
301308
688525
300475
603986
300672
688008
688256
688498
688629
603893
688120
688200
300604
688072
688037
688012
300567
002371
300661
300223
688018
688099
688521
688608
300474
002156
603501
300782
603160
688019
002281
603118
300857
300913
300433
002916
002384
300408
002241
603019
603000
300033
300496
002230
300458
688111
300442
"""


RESULT_DIR = Path(__file__).resolve().parent / "results"


def safe_float(x, default=0.0):
    try:
        if pd.isna(x):
            return default
        return float(str(x).replace("%", "").replace(",", ""))
    except Exception:
        return default


def normalize_code(code):
    return str(code).strip().zfill(6)


def parse_candidates():
    data = []
    seen = set()

    text = str(CANDIDATES_TEXT or "").strip()
    if text:
        # 支持 1~6 位数字，自动补齐6位
        codes = re.findall(r"\b\d{1,6}\b", text)

        for code in codes:
            code = normalize_code(code)
            if code not in seen and code != "000000":
                seen.add(code)
                data.append((code, ""))
        return data

    for item in CANDIDATES_LIST:
        if isinstance(item, (list, tuple)):
            code = normalize_code(item[0])
            note = str(item[1]) if len(item) > 1 else ""
        else:
            code = normalize_code(item)
            note = ""

        if code not in seen and code != "000000":
            seen.add(code)
            data.append((code, note))

    return data


def quiet_call(func, *args, **kwargs):
    """
    屏蔽 AKShare 可能出现的进度条或输出。
    """
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return func(*args, **kwargs)


def get_market_data():
    if ak is None:
        raise RuntimeError("没有安装 akshare。请先运行：pip install akshare pandas openpyxl")

    spot = quiet_call(ak.stock_zh_a_spot_em)

    df = pd.DataFrame()
    df["代码"] = spot["代码"].astype(str).str.zfill(6)
    df["名称"] = spot["名称"].astype(str)
    df["现价"] = spot["最新价"].map(safe_float)
    df["今日涨跌幅%"] = spot["涨跌幅"].map(safe_float)
    df["成交额亿"] = spot["成交额"].map(safe_float) / 100000000
    df["换手率%"] = spot["换手率"].map(safe_float)
    df["量比"] = spot["量比"].map(safe_float) if "量比" in spot.columns else 1.0
    return df


def get_recent_kline(code):
    """
    获取最近K线，判断结构：
    - 前2日是否连续上涨，避免追高；
    - 是否连续回调；
    - 是否站上5/10/20日线；
    - 成交额是否相对5日均值放大；
    - 是否处于强趋势。
    """
    try:
        hist = quiet_call(ak.stock_zh_a_hist, symbol=code, period="daily", adjust="")
        if hist is None or hist.empty:
            return {}

        hist = hist.tail(30).copy()
        pct = [safe_float(x) for x in hist["涨跌幅"].tolist()] if "涨跌幅" in hist.columns else []
        close = [safe_float(x) for x in hist["收盘"].tolist()] if "收盘" in hist.columns else []
        amount = [safe_float(x) for x in hist["成交额"].tolist()] if "成交额" in hist.columns else []

        if not pct or not close:
            return {}

        last_close = close[-1]
        ma5 = sum(close[-5:]) / 5 if len(close) >= 5 else 0
        ma10 = sum(close[-10:]) / 10 if len(close) >= 10 else 0
        ma20 = sum(close[-20:]) / 20 if len(close) >= 20 else 0

        prev2 = pct[-3:-1] if len(pct) >= 3 else pct[-2:]
        last3 = pct[-3:] if len(pct) >= 3 else pct

        amount_today = amount[-1] if amount else 0
        amount_ma5 = sum(amount[-6:-1]) / 5 if len(amount) >= 6 else 0
        amount_ratio_5d = amount_today / amount_ma5 if amount_ma5 > 0 else 1.0

        recent5_sum = sum(pct[-5:]) if len(pct) >= 5 else 0
        recent10_sum = sum(pct[-10:]) if len(pct) >= 10 else 0

        strong_trend = recent10_sum >= 8 and (last_close >= ma10 if ma10 > 0 else False)

        return {
            "近3日涨跌幅": ",".join([f"{x:.2f}" for x in last3]),
            "近5日累计涨跌幅": round(recent5_sum, 2),
            "近10日累计涨跌幅": round(recent10_sum, 2),
            "前2日连续上涨": len(prev2) >= 2 and all(x > 0 for x in prev2),
            "前2日连续下跌": len(prev2) >= 2 and all(x < 0 for x in prev2),
            "站上5日线": last_close >= ma5 if ma5 > 0 else False,
            "站上10日线": last_close >= ma10 if ma10 > 0 else False,
            "站上20日线": last_close >= ma20 if ma20 > 0 else False,
            "成交额相对5日均值": round(amount_ratio_5d, 2),
            "强趋势": strong_trend,
        }
    except Exception:
        return {}


def judge_volume_price(day_pct, volume_ratio, amount_ratio_5d):
    """
    主线活跃股专用量价状态。
    """
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
    volume_ratio = safe_float(market_row["量比"])

    k = get_recent_kline(code)
    amount_ratio_5d = safe_float(k.get("成交额相对5日均值", 1.0), 1.0)
    volume_price = judge_volume_price(day_pct, volume_ratio, amount_ratio_5d)

    above_ma5 = bool(k.get("站上5日线", False))
    above_ma10 = bool(k.get("站上10日线", False))
    above_ma20 = bool(k.get("站上20日线", False))
    strong_trend = bool(k.get("强趋势", False))
    prev2_up = bool(k.get("前2日连续上涨", False))
    prev2_down = bool(k.get("前2日连续下跌", False))

    score = 50
    entry_reasons = []
    risk_reasons = []
    watch_reasons = []
    tactic = []

    # 1. 主线候选池默认逻辑
    score += 6
    watch_reasons.append("按主线候选股处理：重点寻找强股回调后的入场点")

    # 2. 今日位置
    if -5.5 <= day_pct <= -2:
        score += 25
        entry_reasons.append("处于理想低吸区间")
    elif -2 < day_pct <= 1:
        score += 12
        watch_reasons.append("小跌/微涨，适合观察分时承接")
    elif day_pct < -5.5:
        if above_ma10 or above_ma20:
            score += 10
            entry_reasons.append("大跌但结构未完全破坏，可能是恐慌低吸点")
        else:
            score -= 15
            risk_reasons.append("跌幅过深且结构偏弱，不能盲目接")
    elif 1 < day_pct <= 3:
        score -= 5
        watch_reasons.append("已经上涨，不适合追，等回落")
    elif day_pct > 3:
        score -= 20
        risk_reasons.append("涨幅较大，不符合低吸，不追")

    # 3. 量价状态
    if volume_price == "缩量回调":
        score += 18
        entry_reasons.append("缩量回调，更像健康洗盘")
        tactic.append("可重点观察低吸")
    elif volume_price == "普通回调":
        score += 10
        watch_reasons.append("普通回调，需看分时承接")
    elif volume_price == "放量回调":
        if above_ma10 and day_pct > -4:
            score += 16
            entry_reasons.append("放量回调但站上10日线，可能是假跌/洗盘")
        elif above_ma5:
            score += 14
            entry_reasons.append("放量回调但仍站上5日线，承接尚可")
        elif above_ma20:
            score += 3
            watch_reasons.append("放量回调但未破20日线，谨慎观察")
        else:
            score -= 12
            risk_reasons.append("放量回调且破短线结构，谨慎")
    elif volume_price == "大跌放量":
        if above_ma10 and amount_yi >= 10:
            score += 10
            entry_reasons.append("大跌放量但站上10日线，主线股可能是假跌")
            tactic.append("只适合小仓试，不适合重仓")
        elif above_ma20 and strong_trend:
            score += 2
            watch_reasons.append("强趋势中大跌放量但未破20日线，可等企稳")
        else:
            score -= 25
            risk_reasons.append("大跌放量且破结构，真风险概率高")
    elif volume_price == "大跌未明显放量":
        if above_ma10:
            score += 8
            entry_reasons.append("大跌未明显放量且站上10日线，可能是情绪错杀")
        elif above_ma20:
            score += 2
            watch_reasons.append("大跌未明显放量但接近20日线，观察")
        else:
            score -= 10
            risk_reasons.append("大跌且结构偏弱，谨慎")
    elif volume_price == "上涨放量接力":
        score += 5
        watch_reasons.append("上涨放量接力，强但不是低吸点")
        risk_reasons.append("不建议追高，等回落")
    elif volume_price == "上涨缩量诱多":
        score -= 15
        risk_reasons.append("上涨缩量，容易冲高回落")
    elif volume_price == "温和上涨健康":
        score += 2
        watch_reasons.append("温和上涨健康，但更适合持有不适合新追")
    elif volume_price == "震荡量能正常":
        score += 5
        watch_reasons.append("震荡量能正常，可继续盯")
    elif volume_price == "震荡异常放量":
        score -= 5
        risk_reasons.append("震荡异常放量，方向不明")

    # 4. 趋势结构
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

    # 5. 连续上涨/连续下跌过滤
    if prev2_up and day_pct > 1:
        score -= 18
        risk_reasons.append("前2日连续上涨且今日继续涨，不符合低吸")
    elif prev2_up and day_pct < 0:
        score += 5
        watch_reasons.append("连续上涨后回调，若不破结构可观察")
    elif prev2_down and -5.5 <= day_pct <= -2 and above_ma10:
        score += 10
        entry_reasons.append("连续回调后进入低吸区且未破10日线")

    # 6. 流动性与股性
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

    # 7. 最终等级
    hard_risk = (
        (not above_ma20 and day_pct <= -4)
        or (volume_price == "大跌放量" and not above_ma10)
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
    print("正在运行：A股主线候选股入场盯盘助手 v2.1")
    print("支持直接粘贴无引号代码。")
    print("正在获取行情……")

    RESULT_DIR.mkdir(exist_ok=True)

    market = get_market_data()
    candidates = parse_candidates()

    if not candidates:
        print("没有解析到候选股代码。请检查 CANDIDATES_TEXT 是否填写了6位股票代码。")
        return

    rows = []
    for code, note in candidates:
        row = market[market["代码"] == code]
        if row.empty:
            rows.append({
                "代码": code,
                "名称": "",
                "入场等级": "未取到行情",
                "动作建议": "检查代码",
                "备注": note
            })
            continue
        rows.append(diagnose_entry(code, note, row.iloc[0]))

    result = pd.DataFrame(rows)

    rank_map = {
        "S级入场机会": 0,
        "A级低吸观察": 1,
        "继续观察": 2,
        "谨慎": 3,
        "回避": 4,
        "未取到行情": 5
    }
    if not result.empty:
        result["_rank"] = result["入场等级"].map(rank_map).fillna(9)
        result = result.sort_values(["_rank", "评分"], ascending=[True, False]).drop(columns=["_rank"])

    now_str = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = RESULT_DIR / f"主线候选入场盯盘_{now_str}.csv"
    xlsx_path = RESULT_DIR / f"主线候选入场盯盘_{now_str}.xlsx"

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

    print("分析完成。")
    print(f"Excel结果：{xlsx_path}")
    print(f"CSV结果：{csv_path}")
    print("")
    print("简要结论：")
    for _, r in result.head(15).iterrows():
        print(
            f"{r['代码']} {r['名称']} | {r['今日涨跌幅%']}% | "
            f"{r['量价状态']} | {r['入场等级']} | {r['动作建议']} | 评分 {r['评分']}"
        )


if __name__ == "__main__":
    main()
