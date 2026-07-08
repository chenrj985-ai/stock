# -*- coding: utf-8 -*-
"""
A股自选股监控网页生成程序（增强版）

输出位置：
1. docs/index.html
2. docs/history/时间戳.html
3. docs/latest_url.txt
4. docs/latest_manifest.json

增强内容：
1. 保留原有59只自选股观察表
2. 新增大盘指数观察：上证、深成指、创业板、科创50、中证1000
3. 新增板块ETF观察：半导体、芯片、科创、通信、AI、云计算、电子等
4. 新增市场环境摘要：指数强弱、ETF强弱、股票池涨跌数量
5. 新增个股所属板块、距离最高价%、风险评分、尾盘提示
6. 主接口：腾讯行情接口
7. 备用接口：新浪行情接口，仅用于股票池；指数和ETF优先腾讯
8. 每次运行生成唯一历史网页，避免缓存

使用方法：
- 本地运行：python stock_watch.py
- GitHub Actions 运行：见 stock-watch.yml
"""

import os
import time
import json
import random
import traceback
import datetime
from typing import Dict, List, Tuple

import requests
import pandas as pd


# =========================
# 0. 基础配置
# =========================

OUTPUT_DIR = "docs"
HISTORY_DIR = os.path.join(OUTPUT_DIR, "history")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

# 可选：如果你希望 latest_url.txt 直接输出完整网址，可以在 GitHub Actions 中设置环境变量 BASE_URL
# 例如：https://chenrj985-ai.github.io/stock
BASE_URL = os.getenv("BASE_URL", "").rstrip("/")


# =========================
# 1. 股票池：最新候选池，已去重
# =========================

STOCK_LIST = [
    ("002371", "北方华创"),
    ("688012", "中微公司"),
    ("688072", "拓荆科技"),
    ("688120", "华海清科"),
    ("688037", "芯源微"),
    ("002916", "深南电路"),
    ("300476", "胜宏科技"),
    ("002463", "沪电股份"),
    ("600584", "长电科技"),
    ("688041", "海光信息"),
    ("603019", "中科曙光"),
    ("001309", "德明利"),
    ("600183", "生益科技"),
    ("688981", "中芯国际"),
    ("688008", "澜起科技"),
    ("603986", "兆易创新"),
    ("300661", "圣邦股份"),
    ("688052", "纳芯微"),
    ("603893", "瑞芯微"),
    ("688300", "联瑞新材"),
    ("300308", "中际旭创"),
    ("300502", "新易盛"),
    ("300394", "天孚通信"),
    ("002281", "光迅科技"),
    ("601138", "工业富联"),
    ("000977", "浪潮信息"),
    ("688047", "龙芯中科"),
    ("688256", "寒武纪"),
    ("300496", "中科创达"),
    ("002049", "紫光国微"),
    ("002384", "东山精密"),
    ("603228", "景旺电子"),
    ("002436", "兴森科技"),
    ("688126", "沪硅产业"),
    ("688141", "杰华特"),
    ("688082", "盛美上海"),
    ("688627", "精智达"),
    ("688668", "鼎通科技"),
    ("002130", "沃尔核材"),
    ("300604", "长川科技"),
    ("688200", "华峰测控"),
    ("688361", "中科飞测"),
    ("300666", "江丰电子"),
    ("688396", "华润微"),
    ("603290", "斯达半导"),
    ("300373", "扬杰科技"),
    ("688099", "晶晨股份"),
    ("688525", "佰维存储"),
    ("688347", "华虹公司"),
    ("002156", "通富微电"),
    ("002409", "雅克科技"),
    ("603005", "晶方科技"),
    ("300567", "精测电子"),
    ("688249", "晶合集成"),
    ("688498", "源杰科技"),
    ("688213", "思特威"),
    ("688220", "翱捷科技"),
    ("688018", "乐鑫科技"),
    ("688019", "安集科技"),
]

INDEX_LIST = [
    ("000001", "上证指数", "sh"),
    ("399001", "深证成指", "sz"),
    ("399006", "创业板指", "sz"),
    ("000688", "科创50", "sh"),
    ("399852", "中证1000", "sz"),
]

ETF_LIST = [
    ("512480", "半导体ETF", "sh"),
    ("159995", "芯片ETF", "sz"),
    ("588000", "科创50ETF", "sh"),
    ("515880", "通信ETF", "sh"),
    ("515070", "人工智能ETF", "sh"),
    ("516510", "云计算ETF", "sh"),
    ("515260", "电子ETF", "sh"),
    ("159819", "人工智能AIETF", "sz"),
    ("159915", "创业板ETF", "sz"),
]

STOCK_SECTOR_MAP = {
    "002371": "半导体设备", "688012": "半导体设备", "688072": "半导体设备", "688120": "半导体设备",
    "688037": "半导体设备", "300604": "半导体设备", "688082": "半导体设备",
    "688200": "半导体检测", "688361": "半导体检测", "300567": "半导体检测",
    "688019": "半导体材料", "300666": "半导体材料", "002409": "半导体材料", "688300": "半导体材料", "688126": "半导体材料",
    "688981": "晶圆制造", "688347": "晶圆制造", "688249": "晶圆制造",
    "600584": "封测", "002156": "封测", "603005": "封测",
    "603986": "存储芯片", "688525": "存储芯片", "001309": "存储芯片", "688008": "存储/接口芯片",
    "002049": "芯片设计", "603893": "芯片设计", "688099": "芯片设计", "688018": "芯片设计",
    "688213": "芯片设计", "688220": "芯片设计", "300661": "模拟芯片", "688052": "模拟芯片",
    "688396": "功率半导体", "603290": "功率半导体", "300373": "功率半导体", "688141": "电源芯片", "688627": "检测设备/显示",
    "300308": "光模块/CPO", "300502": "光模块/CPO", "300394": "光模块/CPO", "002281": "光模块/CPO", "688498": "光模块/CPO",
    "688668": "光通信", "002130": "高速铜缆",
    "601138": "AI服务器", "000977": "AI服务器", "603019": "国产算力", "688256": "国产AI芯片", "688041": "国产算力", "688047": "国产CPU", "300496": "软件/智能驾驶",
    "002916": "PCB", "300476": "PCB", "002463": "PCB", "600183": "覆铜板", "002384": "PCB/消费电子", "603228": "PCB", "002436": "PCB",
}


def now_dt() -> datetime.datetime:
    return datetime.datetime.now()


def now_str() -> str:
    return now_dt().strftime("%Y-%m-%d %H:%M:%S")


def timestamp_str() -> str:
    return now_dt().strftime("%Y%m%d_%H%M_%S")


def safe_float(x, default=0.0) -> float:
    try:
        if x is None:
            return default
        if isinstance(x, str):
            x = x.strip().replace("%", "")
            if x in ["", "--", "-", "None", "nan", "NaN"]:
                return default
        return float(x)
    except Exception:
        return default


def safe_text(x) -> str:
    if x is None:
        return ""
    x = str(x).strip()
    if x in ["", "None", "nan", "NaN"]:
        return ""
    return x


def get_market_prefix(code: str, market: str = "") -> str:
    market = safe_text(market).lower()
    if market in ["sh", "sz", "bj"]:
        return market
    if code.startswith("6"):
        return "sh"
    return "sz"


def format_amount(x) -> str:
    value = safe_float(x, 0)
    if value >= 100000000:
        return f"{value / 100000000:.2f}亿"
    if value >= 10000:
        return f"{value / 10000:.2f}万"
    return f"{value:.0f}"


def request_text(url: str, headers: Dict[str, str], encoding: str = "gbk", timeout: int = 15) -> str:
    last_error = None
    for i in range(5):
        try:
            print(f"请求第 {i + 1} 次：{url[:120]}...")
            time.sleep(random.uniform(1.2, 3.5))
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            resp.encoding = encoding
            text = resp.text
            if not text or len(text.strip()) < 20:
                raise RuntimeError("接口返回内容过短或为空")
            return text
        except Exception as e:
            last_error = e
            print(f"请求失败：{repr(e)}")
            time.sleep(6 + i * 6)
    raise RuntimeError(f"连续 5 次请求失败：{repr(last_error)}")


def parse_tencent_text(text: str, name_map: Dict[str, str], data_type: str) -> pd.DataFrame:
    rows = []
    for raw_line in text.split(";"):
        line = raw_line.strip()
        if not line or '="' not in line:
            continue
        try:
            left, right = line.split('="', 1)
            symbol = left.split("_")[-1]
            code = symbol[-6:]
            fields = right.rstrip('"').split("~")
            if len(fields) < 40:
                print(f"腾讯字段不足，跳过：{line[:100]}")
                continue
            name = safe_text(fields[1])
            price = safe_float(fields[3])
            pre_close = safe_float(fields[4])
            open_price = safe_float(fields[5])
            change = safe_float(fields[31]) if len(fields) > 31 else price - pre_close
            pct = safe_float(fields[32]) if len(fields) > 32 else (change / pre_close * 100 if pre_close > 0 else 0)
            high = safe_float(fields[33]) if len(fields) > 33 else 0
            low = safe_float(fields[34]) if len(fields) > 34 else 0
            amount_wan = safe_float(fields[37]) if len(fields) > 37 else 0
            amount = amount_wan * 10000
            turnover = safe_text(fields[38]) if len(fields) > 38 else ""
            volume_ratio = ""
            for idx in [49, 48, 50, 51, 52]:
                if len(fields) > idx:
                    candidate = safe_text(fields[idx])
                    val = safe_float(candidate, -1)
                    if 0 <= val <= 50:
                        volume_ratio = candidate
                        break
            quote_time = safe_text(fields[30]) if len(fields) > 30 else ""
            if price <= 0 and pre_close > 0:
                price = pre_close
            distance_high_pct = round((price - high) / high * 100, 2) if high > 0 else 0
            rows.append({
                "代码": code, "名称": name_map.get(code, name), "类型": data_type,
                "最新价": round(price, 2), "涨跌幅": round(pct, 2), "涨跌额": round(change, 2),
                "今开": round(open_price, 2), "最高": round(high, 2), "最低": round(low, 2), "昨收": round(pre_close, 2),
                "距离高点%": distance_high_pct, "量比": volume_ratio, "换手率": turnover, "成交额": amount,
                "行情时间": quote_time, "数据源": "腾讯",
            })
        except Exception as e:
            print(f"解析腾讯行情失败：{repr(e)}")
            print(line[:160])
    return pd.DataFrame(rows)


def get_data_from_tencent(stock_list: List[Tuple[str, str]]) -> pd.DataFrame:
    symbols = [get_market_prefix(code) + code for code, _ in stock_list]
    url = "https://qt.gtimg.cn/q=" + ",".join(symbols)
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/", "Accept": "*/*", "Connection": "close"}
    text = request_text(url, headers=headers, encoding="gbk", timeout=20)
    name_map = {code: name for code, name in stock_list}
    df = parse_tencent_text(text, name_map, "股票")
    if df.empty:
        raise RuntimeError("腾讯接口没有解析到有效股票数据")
    return df


def get_data_from_tencent_items(items: List[Tuple[str, str, str]], data_type: str) -> pd.DataFrame:
    symbols = [get_market_prefix(code, market) + code for code, _, market in items]
    url = "https://qt.gtimg.cn/q=" + ",".join(symbols)
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/", "Accept": "*/*", "Connection": "close"}
    text = request_text(url, headers=headers, encoding="gbk", timeout=20)
    name_map = {code: name for code, name, _ in items}
    return parse_tencent_text(text, name_map, data_type)


def get_data_from_sina(stock_list: List[Tuple[str, str]]) -> pd.DataFrame:
    symbols = [get_market_prefix(code) + code for code, _ in stock_list]
    url = "https://hq.sinajs.cn/list=" + ",".join(symbols)
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/", "Accept": "*/*", "Connection": "close"}
    text = request_text(url, headers=headers, encoding="gbk", timeout=20)
    rows = []
    name_map = {code: name for code, name in stock_list}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or '="' not in line:
            continue
        try:
            left, right = line.split('="', 1)
            symbol = left.split("_")[-1]
            code = symbol[-6:]
            fields = right.rstrip('";').split(",")
            if len(fields) < 32:
                print(f"新浪字段不足，跳过：{line[:100]}")
                continue
            name = fields[0]
            open_price = safe_float(fields[1])
            pre_close = safe_float(fields[2])
            price = safe_float(fields[3])
            high = safe_float(fields[4])
            low = safe_float(fields[5])
            amount = safe_float(fields[9])
            date = fields[30]
            quote_time = fields[31]
            if price <= 0 and pre_close > 0:
                price = pre_close
            change = price - pre_close if pre_close > 0 else 0
            pct = change / pre_close * 100 if pre_close > 0 else 0
            distance_high_pct = round((price - high) / high * 100, 2) if high > 0 else 0
            rows.append({
                "代码": code, "名称": name_map.get(code, name), "类型": "股票",
                "最新价": round(price, 2), "涨跌幅": round(pct, 2), "涨跌额": round(change, 2),
                "今开": round(open_price, 2), "最高": round(high, 2), "最低": round(low, 2), "昨收": round(pre_close, 2),
                "距离高点%": distance_high_pct, "量比": "", "换手率": "", "成交额": amount,
                "行情时间": f"{date} {quote_time}", "数据源": "新浪备用",
            })
        except Exception as e:
            print(f"解析新浪行情失败：{repr(e)}")
            print(line[:160])
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("新浪接口没有解析到有效股票数据")
    return df


def get_market_data() -> pd.DataFrame:
    errors = []
    try:
        print("开始使用腾讯接口获取股票行情...")
        df = get_data_from_tencent(STOCK_LIST)
        print(f"腾讯接口成功，获取 {len(df)} 只股票。")
        return df
    except Exception as e:
        errors.append("腾讯接口失败：" + repr(e))
        print(errors[-1])
        print(traceback.format_exc())
    try:
        print("开始使用新浪备用接口获取股票行情...")
        df = get_data_from_sina(STOCK_LIST)
        print(f"新浪备用接口成功，获取 {len(df)} 只股票。")
        return df
    except Exception as e:
        errors.append("新浪备用接口失败：" + repr(e))
        print(errors[-1])
        print(traceback.format_exc())
    raise RuntimeError("\n".join(errors))


def get_index_data() -> pd.DataFrame:
    try:
        print("开始获取指数数据...")
        return get_data_from_tencent_items(INDEX_LIST, "指数")
    except Exception as e:
        print("指数数据获取失败：", repr(e))
        print(traceback.format_exc())
        return pd.DataFrame()


def get_etf_data() -> pd.DataFrame:
    try:
        print("开始获取ETF数据...")
        return get_data_from_tencent_items(ETF_LIST, "ETF")
    except Exception as e:
        print("ETF数据获取失败：", repr(e))
        print(traceback.format_exc())
        return pd.DataFrame()


def make_signal(row) -> str:
    pct = safe_float(row.get("涨跌幅", 0))
    volume_ratio = safe_float(row.get("量比", 0))
    turnover = safe_float(row.get("换手率", 0))
    distance_high = safe_float(row.get("距离高点%", 0))
    if pct >= 7:
        return "涨幅过大，谨慎追高"
    elif 4 <= pct < 7:
        if distance_high < -3:
            return "涨幅较大但冲高回落，谨慎"
        if volume_ratio >= 1.2 or turnover >= 3:
            return "强势明显，只适合小仓观察"
        return "涨幅较大，谨慎观察"
    elif 2 <= pct < 4:
        if distance_high < -3:
            return "冲高回落，先观察"
        if volume_ratio >= 1.2:
            return "量价偏强，重点观察"
        return "涨幅较好，继续观察"
    elif 0 <= pct < 2:
        if distance_high < -3:
            return "冲高回落，不急买"
        if volume_ratio >= 1.2:
            return "温和放量，可继续盯"
        return "走势温和，可继续盯"
    elif -2 <= pct < 0:
        return "小幅回调，等企稳"
    elif -4 <= pct < -2:
        return "调整偏弱，暂缓"
    else:
        return "跌幅较大，先不急接"


def make_level(row) -> str:
    pct = safe_float(row.get("涨跌幅", 0))
    volume_ratio = safe_float(row.get("量比", 0))
    turnover = safe_float(row.get("换手率", 0))
    distance_high = safe_float(row.get("距离高点%", 0))
    if distance_high < -3:
        return "B" if pct >= 0 else "C"
    if 1.5 <= pct <= 5.5 and (volume_ratio >= 1.2 or turnover >= 3):
        return "A"
    elif 0 <= pct < 1.5 and volume_ratio >= 1.2:
        return "B"
    elif -2 <= pct < 1.5:
        return "B"
    else:
        return "C"


def add_stock_extra_columns(watch_df: pd.DataFrame) -> pd.DataFrame:
    df = watch_df.copy()
    if "距离高点%" not in df.columns:
        def calc_high_gap(row):
            price = safe_float(row.get("最新价", 0))
            high = safe_float(row.get("最高", 0))
            return round((price - high) / high * 100, 2) if high > 0 else 0
        df["距离高点%"] = df.apply(calc_high_gap, axis=1)
    df["所属板块"] = df["代码"].map(STOCK_SECTOR_MAP).fillna("其他")
    def calc_risk_score(row):
        pct = safe_float(row.get("涨跌幅", 0))
        gap = safe_float(row.get("距离高点%", 0))
        volume_ratio = safe_float(row.get("量比", 0))
        turnover = safe_float(row.get("换手率", 0))
        score = 0
        if gap >= -1.5:
            score += 2
        elif gap >= -3:
            score += 1
        else:
            score -= 2
        if 1 <= pct <= 5:
            score += 2
        elif 5 < pct <= 7:
            score += 1
        elif pct > 7:
            score -= 1
        elif pct < -2:
            score -= 2
        if 1.1 <= volume_ratio <= 2.5:
            score += 1
        elif volume_ratio > 3:
            score -= 1
        if turnover >= 8:
            score -= 1
        elif 2 <= turnover <= 6:
            score += 1
        return int(score)
    df["风险评分"] = df.apply(calc_risk_score, axis=1)
    def make_tail_signal(row):
        score = safe_float(row.get("风险评分", 0))
        pct = safe_float(row.get("涨跌幅", 0))
        gap = safe_float(row.get("距离高点%", 0))
        if pct >= 7:
            return "涨幅过大，不追"
        if pct <= -4:
            return "风险释放，不接"
        if gap < -4:
            return "冲高回落，不买"
        if score >= 4:
            return "尾盘可小仓观察"
        if score >= 2:
            return "只观察，等确认"
        return "暂不操作"
    df["尾盘提示"] = df.apply(make_tail_signal, axis=1)
    return df


def make_market_summary(index_df: pd.DataFrame, etf_df: pd.DataFrame, watch_df: pd.DataFrame) -> Dict[str, str]:
    summary: Dict[str, str] = {}
    if index_df is not None and not index_df.empty:
        index_pct = index_df["涨跌幅"].apply(safe_float)
        summary["指数平均涨跌幅"] = f"{index_pct.mean():.2f}%"
        summary["指数转弱数量"] = str(int((index_pct < 0).sum()))
        summary["指数偏强数量"] = str(int((index_pct > 0.5).sum()))
    else:
        summary["指数平均涨跌幅"] = "无数据"
        summary["指数转弱数量"] = "无数据"
        summary["指数偏强数量"] = "无数据"
    if etf_df is not None and not etf_df.empty:
        top_etf = etf_df.sort_values("涨跌幅", ascending=False).head(3)
        weak_etf = etf_df.sort_values("涨跌幅", ascending=True).head(3)
        summary["最强ETF"] = "；".join([f'{r["名称"]}{r["涨跌幅"]}%' for _, r in top_etf.iterrows()])
        summary["最弱ETF"] = "；".join([f'{r["名称"]}{r["涨跌幅"]}%' for _, r in weak_etf.iterrows()])
    else:
        summary["最强ETF"] = "无数据"
        summary["最弱ETF"] = "无数据"
    if watch_df is not None and not watch_df.empty:
        pct_series = watch_df["涨跌幅"].apply(safe_float)
        up_count = int((pct_series > 0).sum())
        down_count = int((pct_series < 0).sum())
        big_up_count = int((pct_series >= 5).sum())
        big_down_count = int((pct_series <= -5).sum())
        summary["股票池上涨数量"] = str(up_count)
        summary["股票池下跌数量"] = str(down_count)
        summary["涨超5%数量"] = str(big_up_count)
        summary["跌超5%数量"] = str(big_down_count)
        if big_down_count >= 5 or down_count > up_count * 1.2:
            market_state = "防守优先"
        elif big_up_count >= 5 and up_count > down_count:
            market_state = "结构性进攻"
        elif up_count > down_count:
            market_state = "温和偏强"
        else:
            market_state = "分化震荡"
        summary["市场状态"] = market_state
    else:
        summary["股票池上涨数量"] = "无数据"
        summary["股票池下跌数量"] = "无数据"
        summary["涨超5%数量"] = "无数据"
        summary["跌超5%数量"] = "无数据"
        summary["市场状态"] = "无数据"
    return summary


def css_style() -> str:
    return """
    <style>
        body {font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", Arial, sans-serif; margin: 24px; background: #f6f8fa; color: #24292f;}
        h1 {margin-bottom: 6px;}
        .time {color: #666; margin-bottom: 20px; line-height: 1.7;}
        .note {background: #fff8c5; border: 1px solid #eac54f; padding: 12px 16px; border-radius: 8px; margin-bottom: 20px; line-height: 1.7;}
        .section-title {margin-top: 26px; margin-bottom: 10px; font-size: 20px; font-weight: bold;}
        .summary-grid {display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 18px;}
        .summary-card {background: white; border-radius: 8px; padding: 12px 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); line-height: 1.6;}
        .summary-card .label {color: #57606a; font-size: 13px;}
        .summary-card .value {font-size: 18px; font-weight: bold;}
        .table-wrap {overflow-x: auto; margin-bottom: 18px;}
        table {width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08);}
        th, td {border-bottom: 1px solid #eaeef2; padding: 9px 8px; text-align: center; font-size: 14px; white-space: nowrap;}
        th {background: #0969da; color: white; position: sticky; top: 0;}
        tr:hover {background: #f1f8ff;}
        .red {color: #d1242f; font-weight: bold;}
        .green {color: #1a7f37; font-weight: bold;}
        .level-a {background: #ffecec; color: #cf222e; font-weight: bold; border-radius: 4px; padding: 3px 7px;}
        .level-b {background: #fff8c5; color: #7d4e00; font-weight: bold; border-radius: 4px; padding: 3px 7px;}
        .level-c {background: #eaeef2; color: #57606a; font-weight: bold; border-radius: 4px; padding: 3px 7px;}
        .footer {margin-top: 18px; color: #666; font-size: 13px; line-height: 1.6;}
    </style>
    """


def dataframe_to_simple_table(df: pd.DataFrame, columns: List[str]) -> str:
    if df is None or df.empty:
        return "<p style='color:#666;'>暂无数据</p>"
    html = """
    <div class="table-wrap"><table><thead><tr>
    """
    for col in columns:
        html += f"<th>{col}</th>"
    html += "</tr></thead><tbody>"
    for _, row in df.iterrows():
        html += "<tr>"
        for col in columns:
            value = row.get(col, "")
            cls = ""
            if col == "涨跌幅":
                cls = "red" if safe_float(value) >= 0 else "green"
                value = f"{value}%"
            elif col == "距离高点%":
                cls = "green" if safe_float(value) < -3 else ""
                value = f"{value}%"
            elif col == "成交额":
                value = format_amount(value)
            html += f'<td class="{cls}">{value}</td>'
        html += "</tr>"
    html += "</tbody></table></div>"
    return html


def generate_html(df: pd.DataFrame, version_name: str, index_df: pd.DataFrame = None, etf_df: pd.DataFrame = None, market_summary: Dict[str, str] = None) -> str:
    update_time = now_str()
    if index_df is None:
        index_df = pd.DataFrame()
    if etf_df is None:
        etf_df = pd.DataFrame()
    if market_summary is None:
        market_summary = {}
    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>A股短线观察表增强版</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    {css_style()}
</head>
<body>
    <h1>A股短线观察表增强版</h1>
    <div class="time">
        页面生成时间：{update_time}<br>
        唯一版本号：{version_name}<br>
        股票池数量：{len(STOCK_LIST)} 只<br>
        指数数量：{len(INDEX_LIST)} 个；ETF数量：{len(ETF_LIST)} 个
    </div>
    <div class="note">
        本页面由 GitHub Actions 自动生成。<br>
        为避免缓存，每次运行都会生成唯一历史页面：<strong>docs/history/{version_name}.html</strong>。<br>
        增强版已加入：大盘指数、板块ETF、市场摘要、所属板块、距离高点、风险评分、尾盘提示。
    </div>
    <div class="section-title">一、市场环境摘要</div>
    <div class="summary-grid">
    """
    for k, v in market_summary.items():
        html += f"""
        <div class="summary-card"><div class="label">{k}</div><div class="value">{v}</div></div>
        """
    html += "</div>"
    html += "<div class='section-title'>二、大盘指数</div>"
    html += dataframe_to_simple_table(index_df, ["名称", "最新价", "涨跌幅", "今开", "最高", "最低", "距离高点%", "成交额", "行情时间"])
    html += "<div class='section-title'>三、板块ETF/方向强弱</div>"
    html += dataframe_to_simple_table(etf_df, ["名称", "最新价", "涨跌幅", "今开", "最高", "最低", "距离高点%", "成交额", "行情时间"])
    html += """
    <div class="section-title">四、自选股观察表</div>
    <div class="table-wrap"><table><thead><tr>
        <th>级别</th><th>代码</th><th>名称</th><th>所属板块</th><th>最新价</th><th>涨跌幅</th><th>涨跌额</th>
        <th>今开</th><th>最高</th><th>最低</th><th>昨收</th><th>距离高点%</th><th>量比</th><th>换手率</th>
        <th>成交额</th><th>数据源</th><th>行情时间</th><th>操作提示</th><th>风险评分</th><th>尾盘提示</th>
    </tr></thead><tbody>
    """
    for _, row in df.iterrows():
        pct_float = safe_float(row.get("涨跌幅", 0))
        pct_class = "red" if pct_float >= 0 else "green"
        level = row.get("级别", "C")
        level_class = "level-a" if level == "A" else ("level-b" if level == "B" else "level-c")
        amount_text = format_amount(row.get("成交额", ""))
        html += f"""
        <tr>
            <td><span class="{level_class}">{level}</span></td>
            <td>{row.get("代码", "")}</td>
            <td>{row.get("名称", "")}</td>
            <td>{row.get("所属板块", "")}</td>
            <td>{row.get("最新价", "")}</td>
            <td class="{pct_class}">{row.get("涨跌幅", "")}%</td>
            <td>{row.get("涨跌额", "")}</td>
            <td>{row.get("今开", "")}</td>
            <td>{row.get("最高", "")}</td>
            <td>{row.get("最低", "")}</td>
            <td>{row.get("昨收", "")}</td>
            <td>{row.get("距离高点%", "")}%</td>
            <td>{row.get("量比", "")}</td>
            <td>{row.get("换手率", "")}</td>
            <td>{amount_text}</td>
            <td>{row.get("数据源", "")}</td>
            <td>{row.get("行情时间", "")}</td>
            <td>{row.get("操作提示", "")}</td>
            <td>{row.get("风险评分", "")}</td>
            <td>{row.get("尾盘提示", "")}</td>
        </tr>
        """
    html += """
    </tbody></table></div>
    <div class="footer">
        说明：本表为自选股快速观察表。腾讯接口返回的量比、换手率用于横向比较强弱；不同交易软件的统计口径可能有细微差异。
        实际操作仍需结合交易软件、指数环境、板块强弱、分时承接和自身仓位判断。
    </div>
</body></html>
    """
    return html


def generate_error_html(error_message: str, version_name: str) -> str:
    update_time = now_str()
    return f"""
<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>A股短线观察表增强版</title></head>
<body style="font-family: Microsoft YaHei, Arial; padding: 30px; line-height: 1.8;">
<h1>A股短线观察表增强版</h1><p>页面生成时间：{update_time}</p><p>唯一版本号：{version_name}</p><p>股票池数量：{len(STOCK_LIST)} 只</p>
<h2 style="color:#d1242f;">本次行情获取失败</h2>
<p>程序已经成功运行到生成网页步骤，但行情接口没有返回有效数据。你可以稍后在 GitHub 里手动重新运行：<strong>Actions → stock-watch → Run workflow</strong></p>
<h3>错误信息</h3><pre style="background:#f6f8fa; padding:15px; white-space:pre-wrap; border:1px solid #d0d7de;">{error_message}</pre>
</body></html>
"""


def write_latest_files(version_name: str):
    latest_history_path = f"history/{version_name}.html"
    latest_full_url = f"{BASE_URL}/{latest_history_path}" if BASE_URL else latest_history_path
    with open(os.path.join(OUTPUT_DIR, "latest_url.txt"), "w", encoding="utf-8") as f:
        f.write(latest_full_url + "\n")
        f.write(f"version={version_name}\n")
        f.write(f"time={now_str()}\n")
    manifest = {
        "latest_url": latest_full_url,
        "relative_url": latest_history_path,
        "version": version_name,
        "beijing_time": now_str(),
        "note": "Use this file with cache-busting query parameter, for example latest_manifest.json?t=timestamp"
    }
    with open(os.path.join(OUTPUT_DIR, "latest_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    version_name = timestamp_str()
    history_file = os.path.join(HISTORY_DIR, f"{version_name}.html")
    try:
        market_df = get_market_data()
        index_df = get_index_data()
        etf_df = get_etf_data()
        stock_codes = [code for code, _ in STOCK_LIST]
        name_map = {code: name for code, name in STOCK_LIST}
        order_map = {code: i for i, (code, _) in enumerate(STOCK_LIST)}
        watch_df = market_df[market_df["代码"].isin(stock_codes)].copy()
        if watch_df.empty:
            raise RuntimeError("没有匹配到股票池中的股票，可能是行情接口字段变化或数据为空。")
        watch_df["排序"] = watch_df["代码"].map(order_map)
        watch_df = watch_df.sort_values("排序").drop(columns=["排序"])
        watch_df["名称"] = watch_df["代码"].map(name_map).fillna(watch_df["名称"])
        watch_df = add_stock_extra_columns(watch_df)
        watch_df["操作提示"] = watch_df.apply(make_signal, axis=1)
        watch_df["级别"] = watch_df.apply(make_level, axis=1)
        market_summary = make_market_summary(index_df, etf_df, watch_df)
        html = generate_html(watch_df, version_name, index_df, etf_df, market_summary)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)
        with open(history_file, "w", encoding="utf-8") as f:
            f.write(html)
        write_latest_files(version_name)
        print(f"最新网页已生成：{OUTPUT_FILE}")
        print(f"唯一历史网页已生成：{history_file}")
        print("latest_url.txt 已生成")
        print("latest_manifest.json 已生成")
        print(f"股票池数量：{len(STOCK_LIST)}")
        print(f"实际生成股票数量：{len(watch_df)}")
        print("使用数据源：")
        print(watch_df["数据源"].value_counts())
    except Exception as e:
        error_message = repr(e) + "\n\n" + traceback.format_exc()
        html = generate_error_html(error_message, version_name)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)
        with open(history_file, "w", encoding="utf-8") as f:
            f.write(html)
        write_latest_files(version_name)
        print(f"行情获取失败，但已生成错误说明页：{OUTPUT_FILE}")
        print(f"唯一错误说明页已生成：{history_file}")
        print(error_message)


if __name__ == "__main__":
    main()
