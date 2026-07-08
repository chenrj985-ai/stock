# -*- coding: utf-8 -*-
"""
A股市场温度计 + 自选股尾盘决策程序

建议文件名：stockchoice.py

设计思路：
1. 不再强依赖东方财富“全A大列表/行业板块排行”，避免 GitHub Actions 超时、502。
2. 核心数据全部使用已经验证较稳定的腾讯行情接口。
3. 用“四层市场温度计”替代真实全A：
   - 宽基指数：判断大盘环境
   - ETF矩阵：判断资金方向
   - 代表性股票池：近似观察全市场主要板块
   - 自选股池：判断你的持仓和候选股
4. 保留与上次运行比较，适合 14:20、14:30、14:40、14:50、14:55 尾盘观察。
5. 输出 docs/index.html、docs/history/时间戳.html、docs/latest_url.txt、docs/latest_manifest.json、docs/latest_snapshot.csv。

依赖：
pip install pandas requests
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
SNAPSHOT_FILE = os.path.join(OUTPUT_DIR, "latest_snapshot.csv")

BASE_URL = os.getenv("BASE_URL", os.getenv("SITE_BASE_URL", "")).rstrip("/")


# =========================
# 1. 你的自选股池
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


# =========================
# 2. 宽基指数
# =========================

INDEX_LIST = [
    ("000001", "上证指数", "sh"),
    ("399001", "深证成指", "sz"),
    ("399006", "创业板指", "sz"),
    ("000688", "科创50", "sh"),
    ("399852", "中证1000", "sz"),
    ("000300", "沪深300", "sh"),
    ("000905", "中证500", "sh"),
]


# =========================
# 3. ETF矩阵
# =========================
# 这些ETF只是板块代理，目的是稳定观察方向，不追求完全覆盖所有行业。

ETF_LIST = [
    ("510300", "沪深300ETF", "sh"),
    ("510500", "中证500ETF", "sh"),
    ("512100", "中证1000ETF", "sh"),
    ("159915", "创业板ETF", "sz"),
    ("588000", "科创50ETF", "sh"),

    ("512480", "半导体ETF", "sh"),
    ("159995", "芯片ETF", "sz"),
    ("588200", "科创芯片ETF", "sh"),
    ("515260", "电子ETF", "sh"),
    ("159732", "消费电子ETF", "sz"),

    ("515880", "通信ETF", "sh"),
    ("515050", "5GETF", "sh"),
    ("515070", "人工智能ETF", "sh"),
    ("159819", "人工智能AIETF", "sz"),
    ("516510", "云计算ETF", "sh"),
    ("512720", "计算机ETF", "sh"),
    ("515400", "大数据ETF", "sh"),

    ("512880", "证券ETF", "sh"),
    ("512800", "银行ETF", "sh"),
    ("510880", "红利ETF", "sh"),

    ("515030", "新能源车ETF", "sh"),
    ("515790", "光伏ETF", "sh"),
    ("512010", "医药ETF", "sh"),
    ("512690", "酒ETF", "sh"),
    ("512400", "有色金属ETF", "sh"),
    ("515220", "煤炭ETF", "sh"),
    ("562500", "机器人ETF", "sh"),
]


# =========================
# 4. 代表性股票池
# =========================
# 这个池子不是全A，而是“全市场温度代理池”。
# 目标：覆盖科技、金融、消费、医药、新能源、周期、军工等主要方向。
# 每个方向选代表股，使用腾讯接口稳定抓取。

REPRESENTATIVE_LIST = [
    # 金融：银行/保险/券商
    ("601398", "工商银行", "银行"),
    ("601288", "农业银行", "银行"),
    ("601939", "建设银行", "银行"),
    ("600036", "招商银行", "银行"),
    ("601166", "兴业银行", "银行"),
    ("601318", "中国平安", "保险"),
    ("601601", "中国太保", "保险"),
    ("601628", "中国人寿", "保险"),
    ("600030", "中信证券", "券商"),
    ("600837", "海通证券", "券商"),
    ("601688", "华泰证券", "券商"),
    ("300059", "东方财富", "券商"),
    ("000776", "广发证券", "券商"),

    # 白酒/消费
    ("600519", "贵州茅台", "白酒消费"),
    ("000858", "五粮液", "白酒消费"),
    ("000568", "泸州老窖", "白酒消费"),
    ("600809", "山西汾酒", "白酒消费"),
    ("603288", "海天味业", "食品消费"),
    ("600887", "伊利股份", "食品消费"),
    ("000333", "美的集团", "家电消费"),
    ("000651", "格力电器", "家电消费"),
    ("600690", "海尔智家", "家电消费"),

    # 医药
    ("600276", "恒瑞医药", "医药"),
    ("300760", "迈瑞医疗", "医药"),
    ("603259", "药明康德", "医药"),
    ("300015", "爱尔眼科", "医药"),
    ("300122", "智飞生物", "医药"),
    ("000538", "云南白药", "医药"),
    ("688271", "联影医疗", "医药"),

    # 新能源/锂电/光伏
    ("300750", "宁德时代", "新能源"),
    ("002594", "比亚迪", "新能源车"),
    ("601012", "隆基绿能", "光伏"),
    ("300274", "阳光电源", "光伏储能"),
    ("002459", "晶澳科技", "光伏"),
    ("688223", "晶科能源", "光伏"),
    ("002466", "天齐锂业", "锂电"),
    ("002460", "赣锋锂业", "锂电"),
    ("300014", "亿纬锂能", "锂电"),
    ("002812", "恩捷股份", "锂电"),

    # AI服务器/算力/计算机
    ("601138", "工业富联", "AI服务器"),
    ("000977", "浪潮信息", "AI服务器"),
    ("603019", "中科曙光", "国产算力"),
    ("688041", "海光信息", "国产算力"),
    ("688256", "寒武纪", "国产AI芯片"),
    ("300496", "中科创达", "软件"),
    ("600570", "恒生电子", "软件"),
    ("002230", "科大讯飞", "AI应用"),
    ("360", "三六零", "AI应用"),
    ("300033", "同花顺", "金融科技"),
    ("300454", "深信服", "软件"),

    # 光模块/CPO/通信
    ("300308", "中际旭创", "光模块/CPO"),
    ("300502", "新易盛", "光模块/CPO"),
    ("300394", "天孚通信", "光模块/CPO"),
    ("002281", "光迅科技", "光模块/CPO"),
    ("688498", "源杰科技", "光模块/CPO"),
    ("000063", "中兴通讯", "通信"),
    ("600522", "中天科技", "通信"),
    ("600487", "亨通光电", "通信"),

    # 半导体设备/制造/设计/封测/材料
    ("002371", "北方华创", "半导体设备"),
    ("688012", "中微公司", "半导体设备"),
    ("688072", "拓荆科技", "半导体设备"),
    ("688120", "华海清科", "半导体设备"),
    ("688037", "芯源微", "半导体设备"),
    ("300604", "长川科技", "半导体设备"),
    ("688200", "华峰测控", "半导体检测"),
    ("688361", "中科飞测", "半导体检测"),
    ("688981", "中芯国际", "晶圆制造"),
    ("688347", "华虹公司", "晶圆制造"),
    ("688008", "澜起科技", "存储/接口芯片"),
    ("603986", "兆易创新", "存储芯片"),
    ("688525", "佰维存储", "存储芯片"),
    ("688126", "沪硅产业", "半导体材料"),
    ("688019", "安集科技", "半导体材料"),
    ("300666", "江丰电子", "半导体材料"),
    ("600584", "长电科技", "封测"),
    ("002156", "通富微电", "封测"),

    # PCB/电子
    ("002916", "深南电路", "PCB"),
    ("300476", "胜宏科技", "PCB"),
    ("002463", "沪电股份", "PCB"),
    ("600183", "生益科技", "覆铜板"),
    ("002384", "东山精密", "PCB/消费电子"),
    ("603228", "景旺电子", "PCB"),
    ("002436", "兴森科技", "PCB"),
    ("002475", "立讯精密", "消费电子"),
    ("000725", "京东方A", "面板"),
    ("002241", "歌尔股份", "消费电子"),
    ("300433", "蓝思科技", "消费电子"),

    # 机器人/智能制造/军工
    ("300124", "汇川技术", "工业自动化"),
    ("002747", "埃斯顿", "机器人"),
    ("002236", "大华股份", "安防AI"),
    ("002415", "海康威视", "安防AI"),
    ("600893", "航发动力", "军工"),
    ("600760", "中航沈飞", "军工"),
    ("000768", "中航西飞", "军工"),
    ("002179", "中航光电", "军工电子"),
    ("300661", "圣邦股份", "模拟芯片"),

    # 周期资源/地产/基建
    ("601899", "紫金矿业", "有色"),
    ("600547", "山东黄金", "黄金"),
    ("601600", "中国铝业", "有色"),
    ("603993", "洛阳钼业", "有色"),
    ("600028", "中国石化", "石油"),
    ("601857", "中国石油", "石油"),
    ("601088", "中国神华", "煤炭"),
    ("601225", "陕西煤业", "煤炭"),
    ("600048", "保利发展", "地产"),
    ("000002", "万科A", "地产"),
    ("601668", "中国建筑", "基建"),
    ("601390", "中国中铁", "基建"),
    ("601186", "中国铁建", "基建"),
]


# 去重代表池，保留首次出现
def dedupe_rep_list(items: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
    seen = set()
    out = []
    for code, name, sector in items:
        if code not in seen:
            out.append((code, name, sector))
            seen.add(code)
    return out


REPRESENTATIVE_LIST = dedupe_rep_list(REPRESENTATIVE_LIST)


# =========================
# 5. 自选股板块映射
# =========================

STOCK_SECTOR_MAP = {
    "002371": "半导体设备", "688012": "半导体设备", "688072": "半导体设备",
    "688120": "半导体设备", "688037": "半导体设备", "300604": "半导体设备",
    "688082": "半导体设备", "688200": "半导体检测", "688361": "半导体检测",
    "300567": "半导体检测", "688019": "半导体材料", "300666": "半导体材料",
    "002409": "半导体材料", "688300": "半导体材料", "688126": "半导体材料",
    "688981": "晶圆制造", "688347": "晶圆制造", "688249": "晶圆制造",
    "600584": "封测", "002156": "封测", "603005": "封测",
    "603986": "存储芯片", "688525": "存储芯片", "001309": "存储芯片",
    "688008": "存储/接口芯片", "002049": "芯片设计", "603893": "芯片设计",
    "688099": "芯片设计", "688018": "芯片设计", "688213": "芯片设计",
    "688220": "芯片设计", "300661": "模拟芯片", "688052": "模拟芯片",
    "688396": "功率半导体", "603290": "功率半导体", "300373": "功率半导体",
    "688141": "电源芯片", "688627": "检测设备/显示",

    "300308": "光模块/CPO", "300502": "光模块/CPO", "300394": "光模块/CPO",
    "002281": "光模块/CPO", "688498": "光模块/CPO", "688668": "光通信",
    "002130": "高速铜缆",

    "601138": "AI服务器", "000977": "AI服务器", "603019": "国产算力",
    "688256": "国产AI芯片", "688041": "国产算力", "688047": "国产CPU",
    "300496": "软件/智能驾驶",

    "002916": "PCB", "300476": "PCB", "002463": "PCB", "600183": "覆铜板",
    "002384": "PCB/消费电子", "603228": "PCB", "002436": "PCB",
}


# =========================
# 6. 工具函数
# =========================

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
            x = x.strip().replace("%", "").replace(",", "")
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
    for i in range(3):
        try:
            print(f"请求第 {i + 1} 次：{url[:120]}...")
            time.sleep(random.uniform(0.8, 1.8))
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
            time.sleep(2 + i * 2)
    raise RuntimeError(f"连续 3 次请求失败：{repr(last_error)}")


# =========================
# 7. 腾讯行情接口
# =========================

def parse_tencent_text(text: str, name_map: Dict[str, str], data_type: str, sector_map: Dict[str, str] = None) -> pd.DataFrame:
    sector_map = sector_map or {}
    rows = []

    for raw_line in text.split(";"):
        line = raw_line.strip()
        if not line or '="' not in line:
            continue

        try:
            left, right = line.split('="', 1)
            symbol = left.split("_")[-1]
            code = symbol[-6:]

            content = right.rstrip('"')
            fields = content.split("~")

            if len(fields) < 40:
                print(f"腾讯字段不足，跳过：{line[:100]}")
                continue

            name = safe_text(fields[1])
            price = safe_float(fields[3])
            pre_close = safe_float(fields[4])
            open_price = safe_float(fields[5])

            change = safe_float(fields[31]) if len(fields) > 31 else price - pre_close
            pct = safe_float(fields[32]) if len(fields) > 32 else (
                change / pre_close * 100 if pre_close > 0 else 0
            )

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
                "代码": code,
                "名称": name_map.get(code, name),
                "类型": data_type,
                "所属板块": sector_map.get(code, ""),
                "最新价": round(price, 2),
                "涨跌幅": round(pct, 2),
                "涨跌额": round(change, 2),
                "今开": round(open_price, 2),
                "最高": round(high, 2),
                "最低": round(low, 2),
                "昨收": round(pre_close, 2),
                "距离高点%": distance_high_pct,
                "量比": volume_ratio,
                "换手率": turnover,
                "成交额": amount,
                "行情时间": quote_time,
                "数据源": "腾讯",
            })

        except Exception as e:
            print(f"解析腾讯行情失败：{repr(e)}")
            print(line[:160])

    return pd.DataFrame(rows)


def fetch_tencent_by_items(items, data_type: str, has_market: bool = False, has_sector: bool = False) -> pd.DataFrame:
    """
    通用腾讯接口。
    items:
    - has_market=True: [(code, name, market)]
    - has_sector=True: [(code, name, sector)]
    - default: [(code, name)]
    """
    symbols = []
    name_map = {}
    sector_map = {}

    for item in items:
        if has_market:
            code, name, market = item
            symbols.append(get_market_prefix(code, market) + code)
        elif has_sector:
            code, name, sector = item
            symbols.append(get_market_prefix(code) + code)
            sector_map[code] = sector
        else:
            code, name = item
            symbols.append(get_market_prefix(code) + code)

        name_map[code] = name

    url = "https://qt.gtimg.cn/q=" + ",".join(symbols)

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://gu.qq.com/",
        "Accept": "*/*",
        "Connection": "close",
    }

    text = request_text(url, headers=headers, encoding="gbk", timeout=20)
    df = parse_tencent_text(text, name_map, data_type, sector_map)
    if df.empty:
        raise RuntimeError(f"腾讯接口没有解析到有效{data_type}数据")
    return df


def get_watch_data() -> pd.DataFrame:
    return fetch_tencent_by_items(STOCK_LIST, "自选股")


def get_index_data() -> pd.DataFrame:
    return fetch_tencent_by_items(INDEX_LIST, "指数", has_market=True)


def get_etf_data() -> pd.DataFrame:
    return fetch_tencent_by_items(ETF_LIST, "ETF", has_market=True)


def get_representative_data() -> pd.DataFrame:
    return fetch_tencent_by_items(REPRESENTATIVE_LIST, "代表池", has_sector=True)


# =========================
# 8. 快照对比
# =========================

def load_previous_snapshot() -> pd.DataFrame:
    if not os.path.exists(SNAPSHOT_FILE):
        return pd.DataFrame()
    try:
        return pd.read_csv(SNAPSHOT_FILE, dtype={"代码": str})
    except Exception as e:
        print("读取上次快照失败：", repr(e))
        return pd.DataFrame()


def add_previous_compare(df: pd.DataFrame, prev_df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["较上次价格变化"] = 0.0
    df["较上次涨跌幅变化"] = 0.0
    df["尾盘变化"] = "首次/无对比"

    if prev_df is None or prev_df.empty or "代码" not in prev_df.columns:
        return df

    prev_map_price = dict(zip(prev_df["代码"].astype(str), prev_df["最新价"].apply(safe_float)))
    prev_map_pct = dict(zip(prev_df["代码"].astype(str), prev_df["涨跌幅"].apply(safe_float)))

    price_changes = []
    pct_changes = []
    tail_changes = []

    for _, row in df.iterrows():
        code = str(row.get("代码", ""))
        price = safe_float(row.get("最新价", 0))
        pct = safe_float(row.get("涨跌幅", 0))
        old_price = prev_map_price.get(code, None)
        old_pct = prev_map_pct.get(code, None)

        if old_price is None or old_pct is None:
            price_changes.append(0.0)
            pct_changes.append(0.0)
            tail_changes.append("新增/无对比")
            continue

        price_delta = round(price - old_price, 2)
        pct_delta = round(pct - old_pct, 2)
        price_changes.append(price_delta)
        pct_changes.append(pct_delta)

        if pct_delta >= 0.8:
            tail_changes.append("转强")
        elif pct_delta <= -0.8:
            tail_changes.append("转弱")
        elif pct_delta > 0.2:
            tail_changes.append("小幅转强")
        elif pct_delta < -0.2:
            tail_changes.append("小幅转弱")
        else:
            tail_changes.append("变化不大")

    df["较上次价格变化"] = price_changes
    df["较上次涨跌幅变化"] = pct_changes
    df["尾盘变化"] = tail_changes
    return df


def save_snapshot(watch_df: pd.DataFrame, representative_df: pd.DataFrame):
    try:
        keep_cols = ["代码", "名称", "最新价", "涨跌幅", "最高", "最低", "成交额", "行情时间", "类型", "所属板块"]
        combined = pd.concat([watch_df, representative_df], ignore_index=True)
        tmp = combined[[c for c in keep_cols if c in combined.columns]].copy()
        tmp.to_csv(SNAPSHOT_FILE, index=False, encoding="utf-8-sig")
    except Exception as e:
        print("保存快照失败：", repr(e))


# =========================
# 9. 温度计计算
# =========================

def calc_breadth(df: pd.DataFrame, label: str) -> Dict[str, str]:
    if df is None or df.empty:
        return {
            f"{label}数量": "无数据",
            f"{label}上涨": "无数据",
            f"{label}下跌": "无数据",
            f"{label}平盘": "无数据",
            f"{label}涨超5%": "无数据",
            f"{label}跌超5%": "无数据",
            f"{label}涨停附近": "无数据",
            f"{label}跌停附近": "无数据",
            f"{label}成交额": "无数据",
        }

    pct = df["涨跌幅"].apply(safe_float)
    amount = df["成交额"].apply(safe_float).sum() if "成交额" in df.columns else 0

    return {
        f"{label}数量": str(len(df)),
        f"{label}上涨": str(int((pct > 0).sum())),
        f"{label}下跌": str(int((pct < 0).sum())),
        f"{label}平盘": str(int((pct == 0).sum())),
        f"{label}涨超5%": str(int((pct >= 5).sum())),
        f"{label}跌超5%": str(int((pct <= -5).sum())),
        f"{label}涨停附近": str(int((pct >= 9.5).sum())),
        f"{label}跌停附近": str(int((pct <= -9.5).sum())),
        f"{label}成交额": format_amount(amount),
    }


def score_from_pct_series(pct: pd.Series) -> float:
    if pct is None or len(pct) == 0:
        return 50

    avg_pct = pct.mean()
    up_ratio = (pct > 0).mean()
    up5_ratio = (pct >= 5).mean()
    down5_ratio = (pct <= -5).mean()

    score = 50
    score += avg_pct * 8
    score += (up_ratio - 0.5) * 50
    score += up5_ratio * 30
    score -= down5_ratio * 35

    return max(0, min(100, round(score, 1)))


def make_temperature(index_df: pd.DataFrame, etf_df: pd.DataFrame, representative_df: pd.DataFrame, watch_df: pd.DataFrame) -> Dict[str, str]:
    index_score = score_from_pct_series(index_df["涨跌幅"].apply(safe_float)) if not index_df.empty else 50
    etf_score = score_from_pct_series(etf_df["涨跌幅"].apply(safe_float)) if not etf_df.empty else 50
    rep_score = score_from_pct_series(representative_df["涨跌幅"].apply(safe_float)) if not representative_df.empty else 50
    watch_score = score_from_pct_series(watch_df["涨跌幅"].apply(safe_float)) if not watch_df.empty else 50

    # 尾盘变化修正：只有非首次运行时明显有效
    tail_bonus = 0
    if "较上次涨跌幅变化" in watch_df.columns:
        delta = watch_df["较上次涨跌幅变化"].apply(safe_float)
        strong = (delta >= 0.8).sum()
        weak = (delta <= -0.8).sum()
        tail_bonus = (strong - weak) * 0.8

    total_score = round(index_score * 0.30 + etf_score * 0.25 + rep_score * 0.25 + watch_score * 0.20 + tail_bonus, 1)
    total_score = max(0, min(100, total_score))

    if total_score >= 75:
        conclusion = "可小仓进攻"
    elif total_score >= 60:
        conclusion = "结构行情，只做最强方向"
    elif total_score >= 45:
        conclusion = "分化震荡，少动"
    else:
        conclusion = "防守优先，不开新仓"

    return {
        "指数温度分": str(index_score),
        "ETF温度分": str(etf_score),
        "代表池温度分": str(rep_score),
        "自选池温度分": str(watch_score),
        "综合温度分": str(total_score),
        "综合结论": conclusion,
    }


def sector_strength(df: pd.DataFrame, sector_col: str = "所属板块", top_n: int = 8):
    if df is None or df.empty or sector_col not in df.columns:
        return pd.DataFrame()

    grouped = df.groupby(sector_col).agg(
        股票数=("代码", "count"),
        平均涨跌幅=("涨跌幅", lambda x: round(pd.Series(x).apply(safe_float).mean(), 2)),
        上涨数=("涨跌幅", lambda x: int((pd.Series(x).apply(safe_float) > 0).sum())),
        涨超5数=("涨跌幅", lambda x: int((pd.Series(x).apply(safe_float) >= 5).sum())),
        跌超5数=("涨跌幅", lambda x: int((pd.Series(x).apply(safe_float) <= -5).sum())),
        成交额=("成交额", lambda x: sum(pd.Series(x).apply(safe_float))),
    ).reset_index()

    grouped["成交额"] = grouped["成交额"].round(0)
    return grouped.sort_values("平均涨跌幅", ascending=False)


def etf_matrix_summary(etf_df: pd.DataFrame) -> Dict[str, str]:
    if etf_df is None or etf_df.empty:
        return {"ETF强方向": "无数据", "ETF弱方向": "无数据"}

    top = etf_df.sort_values("涨跌幅", ascending=False).head(5)
    bottom = etf_df.sort_values("涨跌幅", ascending=True).head(5)

    return {
        "ETF强方向": "；".join([f'{r["名称"]}{r["涨跌幅"]}%' for _, r in top.iterrows()]),
        "ETF弱方向": "；".join([f'{r["名称"]}{r["涨跌幅"]}%' for _, r in bottom.iterrows()]),
    }


def add_stock_scores(watch_df: pd.DataFrame) -> pd.DataFrame:
    df = watch_df.copy()

    df["所属板块"] = df["代码"].map(STOCK_SECTOR_MAP).fillna(df.get("所属板块", "其他"))
    df["所属板块"] = df["所属板块"].replace("", "其他")

    def calc_risk_score(row):
        pct = safe_float(row.get("涨跌幅", 0))
        gap = safe_float(row.get("距离高点%", 0))
        volume_ratio = safe_float(row.get("量比", 0))
        turnover = safe_float(row.get("换手率", 0))
        pct_delta = safe_float(row.get("较上次涨跌幅变化", 0))

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

        if pct_delta >= 0.8:
            score += 1
        elif pct_delta <= -0.8:
            score -= 1

        return int(score)

    df["风险评分"] = df.apply(calc_risk_score, axis=1)

    def make_signal(row):
        pct = safe_float(row.get("涨跌幅", 0))
        gap = safe_float(row.get("距离高点%", 0))
        pct_delta = safe_float(row.get("较上次涨跌幅变化", 0))

        if pct_delta <= -1:
            return "尾盘转弱，谨慎"
        if pct >= 7:
            return "涨幅过大，谨慎追高"
        if 4 <= pct < 7:
            if gap < -3:
                return "涨幅较大但冲高回落，谨慎"
            return "强势明显，只适合小仓观察"
        if 2 <= pct < 4:
            if gap < -3:
                return "冲高回落，先观察"
            return "涨幅较好，继续观察"
        if 0 <= pct < 2:
            if gap < -3:
                return "冲高回落，不急买"
            return "走势温和，可继续盯"
        if -2 <= pct < 0:
            return "小幅回调，等企稳"
        if -4 <= pct < -2:
            return "调整偏弱，暂缓"
        return "跌幅较大，先不急接"

    def make_tail_signal(row):
        score = safe_float(row.get("风险评分", 0))
        pct = safe_float(row.get("涨跌幅", 0))
        gap = safe_float(row.get("距离高点%", 0))
        pct_delta = safe_float(row.get("较上次涨跌幅变化", 0))

        if pct >= 7:
            return "涨幅过大，不追"
        if pct <= -4:
            return "风险释放，不接"
        if gap < -4:
            return "冲高回落，不买"
        if pct_delta <= -1:
            return "尾盘转弱，不买"
        if score >= 4 and pct_delta >= 0:
            return "尾盘可小仓观察"
        if score >= 2:
            return "只观察，等确认"
        return "暂不操作"

    def make_level(row):
        pct = safe_float(row.get("涨跌幅", 0))
        gap = safe_float(row.get("距离高点%", 0))
        score = safe_float(row.get("风险评分", 0))
        pct_delta = safe_float(row.get("较上次涨跌幅变化", 0))

        if pct_delta <= -1 or gap < -4:
            return "C"
        if score >= 4:
            return "A"
        if score >= 1:
            return "B"
        if -2 <= pct < 1.5:
            return "B"
        return "C"

    df["操作提示"] = df.apply(make_signal, axis=1)
    df["尾盘提示"] = df.apply(make_tail_signal, axis=1)
    df["级别"] = df.apply(make_level, axis=1)

    return df


def make_decision_panel(
    temp: Dict[str, str],
    etf_df: pd.DataFrame,
    rep_sector_df: pd.DataFrame,
    watch_sector_df: pd.DataFrame,
    watch_df: pd.DataFrame,
) -> Dict[str, str]:
    panel = {}

    panel["今日是否适合新开仓"] = temp.get("综合结论", "无数据")
    panel["综合温度分"] = temp.get("综合温度分", "无数据")

    panel.update(etf_matrix_summary(etf_df))

    if rep_sector_df is not None and not rep_sector_df.empty:
        strong = rep_sector_df.head(5)
        weak = rep_sector_df.tail(5).sort_values("平均涨跌幅", ascending=True)
        panel["代表池强方向"] = "；".join([f'{r["所属板块"]}{r["平均涨跌幅"]}%' for _, r in strong.iterrows()])
        panel["代表池弱方向"] = "；".join([f'{r["所属板块"]}{r["平均涨跌幅"]}%' for _, r in weak.iterrows()])
    else:
        panel["代表池强方向"] = "无数据"
        panel["代表池弱方向"] = "无数据"

    if watch_sector_df is not None and not watch_sector_df.empty:
        strong_w = watch_sector_df.head(4)
        weak_w = watch_sector_df.tail(4).sort_values("平均涨跌幅", ascending=True)
        panel["自选池强方向"] = "；".join([f'{r["所属板块"]}{r["平均涨跌幅"]}%' for _, r in strong_w.iterrows()])
        panel["自选池弱方向"] = "；".join([f'{r["所属板块"]}{r["平均涨跌幅"]}%' for _, r in weak_w.iterrows()])
    else:
        panel["自选池强方向"] = "无数据"
        panel["自选池弱方向"] = "无数据"

    candidates = watch_df[
        (watch_df["风险评分"].apply(safe_float) >= 4)
        & (watch_df["涨跌幅"].apply(safe_float) < 7)
        & (watch_df["较上次涨跌幅变化"].apply(safe_float) >= -0.3)
    ].sort_values(["风险评分", "涨跌幅"], ascending=[False, False]).head(5)

    avoid = watch_df[
        (watch_df["距离高点%"].apply(safe_float) <= -4)
        | (watch_df["较上次涨跌幅变化"].apply(safe_float) <= -1)
        | (watch_df["涨跌幅"].apply(safe_float) <= -4)
    ].sort_values(["较上次涨跌幅变化", "涨跌幅"]).head(5)

    panel["候选观察"] = "；".join([f'{r["名称"]}({r["涨跌幅"]}%,评分{r["风险评分"]})' for _, r in candidates.iterrows()]) or "无"
    panel["风险回避"] = "；".join([f'{r["名称"]}({r["涨跌幅"]}%,{r["尾盘提示"]})' for _, r in avoid.iterrows()]) or "无"

    return panel


# =========================
# 10. HTML
# =========================

def css_style() -> str:
    return """
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", Arial, sans-serif;
            margin: 24px;
            background: #f6f8fa;
            color: #24292f;
        }
        h1 { margin-bottom: 6px; }
        .time { color: #666; margin-bottom: 20px; line-height: 1.7; }
        .note {
            background: #fff8c5; border: 1px solid #eac54f; padding: 12px 16px;
            border-radius: 8px; margin-bottom: 20px; line-height: 1.7;
        }
        .section-title {
            margin-top: 26px; margin-bottom: 10px; font-size: 20px; font-weight: bold;
        }
        .summary-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 12px; margin-bottom: 18px;
        }
        .summary-card {
            background: white; border-radius: 8px; padding: 12px 14px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08); line-height: 1.6;
        }
        .summary-card .label { color: #57606a; font-size: 13px; }
        .summary-card .value { font-size: 17px; font-weight: bold; }
        .table-wrap { overflow-x: auto; margin-bottom: 18px; }
        table {
            width: 100%; border-collapse: collapse; background: white; border-radius: 8px;
            overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }
        th, td {
            border-bottom: 1px solid #eaeef2; padding: 9px 8px; text-align: center;
            font-size: 14px; white-space: nowrap;
        }
        th { background: #0969da; color: white; position: sticky; top: 0; }
        tr:hover { background: #f1f8ff; }
        .red { color: #d1242f; font-weight: bold; }
        .green { color: #1a7f37; font-weight: bold; }
        .level-a {
            background: #ffecec; color: #cf222e; font-weight: bold;
            border-radius: 4px; padding: 3px 7px;
        }
        .level-b {
            background: #fff8c5; color: #7d4e00; font-weight: bold;
            border-radius: 4px; padding: 3px 7px;
        }
        .level-c {
            background: #eaeef2; color: #57606a; font-weight: bold;
            border-radius: 4px; padding: 3px 7px;
        }
        .footer { margin-top: 18px; color: #666; font-size: 13px; line-height: 1.6; }
    </style>
    """


def dict_to_cards(data: Dict[str, str]) -> str:
    html = "<div class='summary-grid'>"
    for k, v in data.items():
        html += f"""
        <div class="summary-card">
            <div class="label">{k}</div>
            <div class="value">{v}</div>
        </div>
        """
    html += "</div>"
    return html


def dataframe_to_simple_table(df: pd.DataFrame, columns: List[str]) -> str:
    if df is None or df.empty:
        return "<p style='color:#666;'>暂无数据</p>"

    html = "<div class='table-wrap'><table><thead><tr>"
    for col in columns:
        html += f"<th>{col}</th>"
    html += "</tr></thead><tbody>"

    for _, row in df.iterrows():
        html += "<tr>"
        for col in columns:
            value = row.get(col, "")
            cls = ""
            if col in ["涨跌幅", "平均涨跌幅", "较上次涨跌幅变化"]:
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


def generate_html(
    watch_df: pd.DataFrame,
    representative_df: pd.DataFrame,
    index_df: pd.DataFrame,
    etf_df: pd.DataFrame,
    temp: Dict[str, str],
    decision_panel: Dict[str, str],
    index_breadth: Dict[str, str],
    etf_breadth: Dict[str, str],
    rep_breadth: Dict[str, str],
    watch_breadth: Dict[str, str],
    rep_sector_df: pd.DataFrame,
    watch_sector_df: pd.DataFrame,
    version_name: str,
) -> str:
    update_time = now_str()

    top_rep_sector = rep_sector_df.head(12) if rep_sector_df is not None and not rep_sector_df.empty else pd.DataFrame()
    bottom_rep_sector = rep_sector_df.tail(12).sort_values("平均涨跌幅", ascending=True) if rep_sector_df is not None and not rep_sector_df.empty else pd.DataFrame()
    top_watch_sector = watch_sector_df.head(10) if watch_sector_df is not None and not watch_sector_df.empty else pd.DataFrame()
    bottom_watch_sector = watch_sector_df.tail(10).sort_values("平均涨跌幅", ascending=True) if watch_sector_df is not None and not watch_sector_df.empty else pd.DataFrame()

    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>A股市场温度计</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">

    {css_style()}
</head>
<body>
    <h1>A股市场温度计 + 自选股尾盘决策</h1>
    <div class="time">
        页面生成时间：{update_time}<br>
        唯一版本号：{version_name}<br>
        自选股数量：{len(STOCK_LIST)} 只；代表池数量：{len(REPRESENTATIVE_LIST)} 只；指数数量：{len(INDEX_LIST)} 个；ETF数量：{len(ETF_LIST)} 个
    </div>

    <div class="note">
        本页面不强依赖东方财富全A接口，而是使用腾讯接口构造“四层市场温度计”：宽基指数 + ETF矩阵 + 代表性股票池 + 自选股池。<br>
        代表池不是全A真实统计，但覆盖金融、消费、医药、新能源、AI算力、半导体、通信、PCB、军工、周期等主要方向，用来近似判断市场温度。<br>
        “较上次变化”依赖 docs/latest_snapshot.csv，首次运行时没有对比。
    </div>
"""

    html += "<div class='section-title'>一、尾盘决策区</div>"
    html += dict_to_cards(decision_panel)

    html += "<div class='section-title'>二、市场温度计</div>"
    html += dict_to_cards(temp)

    html += "<div class='section-title'>三、四层情绪摘要</div>"
    merged_breadth = {}
    merged_breadth.update(index_breadth)
    merged_breadth.update(etf_breadth)
    merged_breadth.update(rep_breadth)
    merged_breadth.update(watch_breadth)
    html += dict_to_cards(merged_breadth)

    html += "<div class='section-title'>四、宽基指数</div>"
    html += dataframe_to_simple_table(
        index_df,
        ["名称", "最新价", "涨跌幅", "今开", "最高", "最低", "距离高点%", "成交额", "行情时间"]
    )

    html += "<div class='section-title'>五、ETF矩阵</div>"
    html += dataframe_to_simple_table(
        etf_df.sort_values("涨跌幅", ascending=False),
        ["名称", "最新价", "涨跌幅", "今开", "最高", "最低", "距离高点%", "成交额", "行情时间"]
    )

    html += "<div class='section-title'>六、代表池强方向前12</div>"
    html += dataframe_to_simple_table(
        top_rep_sector,
        ["所属板块", "股票数", "平均涨跌幅", "上涨数", "涨超5数", "跌超5数", "成交额"]
    )

    html += "<div class='section-title'>七、代表池弱方向前12</div>"
    html += dataframe_to_simple_table(
        bottom_rep_sector,
        ["所属板块", "股票数", "平均涨跌幅", "上涨数", "涨超5数", "跌超5数", "成交额"]
    )

    html += "<div class='section-title'>八、自选池强方向</div>"
    html += dataframe_to_simple_table(
        top_watch_sector,
        ["所属板块", "股票数", "平均涨跌幅", "上涨数", "涨超5数", "跌超5数", "成交额"]
    )

    html += "<div class='section-title'>九、自选池弱方向</div>"
    html += dataframe_to_simple_table(
        bottom_watch_sector,
        ["所属板块", "股票数", "平均涨跌幅", "上涨数", "涨超5数", "跌超5数", "成交额"]
    )

    html += """
    <div class="section-title">十、自选股观察表</div>
    <div class="table-wrap">
    <table>
        <thead>
            <tr>
                <th>级别</th>
                <th>代码</th>
                <th>名称</th>
                <th>所属板块</th>
                <th>最新价</th>
                <th>涨跌幅</th>
                <th>较上次涨跌幅变化</th>
                <th>尾盘变化</th>
                <th>涨跌额</th>
                <th>今开</th>
                <th>最高</th>
                <th>最低</th>
                <th>昨收</th>
                <th>距离高点%</th>
                <th>量比</th>
                <th>换手率</th>
                <th>成交额</th>
                <th>行情时间</th>
                <th>操作提示</th>
                <th>风险评分</th>
                <th>尾盘提示</th>
            </tr>
        </thead>
        <tbody>
"""

    for _, row in watch_df.iterrows():
        pct_float = safe_float(row.get("涨跌幅", 0))
        pct_class = "red" if pct_float >= 0 else "green"
        delta_pct = safe_float(row.get("较上次涨跌幅变化", 0))
        delta_class = "red" if delta_pct >= 0 else "green"

        level = row.get("级别", "C")
        level_class = "level-a" if level == "A" else ("level-b" if level == "B" else "level-c")

        html += f"""
            <tr>
                <td><span class="{level_class}">{level}</span></td>
                <td>{row.get("代码", "")}</td>
                <td>{row.get("名称", "")}</td>
                <td>{row.get("所属板块", "")}</td>
                <td>{row.get("最新价", "")}</td>
                <td class="{pct_class}">{row.get("涨跌幅", "")}%</td>
                <td class="{delta_class}">{row.get("较上次涨跌幅变化", "")}%</td>
                <td>{row.get("尾盘变化", "")}</td>
                <td>{row.get("涨跌额", "")}</td>
                <td>{row.get("今开", "")}</td>
                <td>{row.get("最高", "")}</td>
                <td>{row.get("最低", "")}</td>
                <td>{row.get("昨收", "")}</td>
                <td>{row.get("距离高点%", "")}%</td>
                <td>{row.get("量比", "")}</td>
                <td>{row.get("换手率", "")}</td>
                <td>{format_amount(row.get("成交额", ""))}</td>
                <td>{row.get("行情时间", "")}</td>
                <td>{row.get("操作提示", "")}</td>
                <td>{row.get("风险评分", "")}</td>
                <td>{row.get("尾盘提示", "")}</td>
            </tr>
"""

    html += """
        </tbody>
    </table>
    </div>

    <div class="footer">
        说明：本页面为市场温度和尾盘观察辅助工具，不构成投资建议。代表池不是全A真实统计，只是稳定可获取的全局代理。
        若未来真实全A接口稳定，可再单独增加“真实全A情绪”模块。
    </div>
</body>
</html>
"""

    return html


def generate_error_html(error_message: str, version_name: str) -> str:
    update_time = now_str()
    return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>A股市场温度计</title></head>
<body style="font-family: Microsoft YaHei, Arial; padding: 30px; line-height: 1.8;">
    <h1>A股市场温度计</h1>
    <p>页面生成时间：{update_time}</p>
    <p>唯一版本号：{version_name}</p>
    <h2 style="color:#d1242f;">本次行情获取失败</h2>
    <pre style="background:#f6f8fa; padding:15px; white-space:pre-wrap; border:1px solid #d0d7de;">
{error_message}
    </pre>
</body>
</html>
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


# =========================
# 11. 主程序
# =========================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)

    version_name = timestamp_str()
    history_file = os.path.join(HISTORY_DIR, f"{version_name}.html")

    try:
        print("开始获取自选股数据...")
        watch_df = get_watch_data()

        print("开始获取指数数据...")
        index_df = get_index_data()

        print("开始获取ETF矩阵数据...")
        etf_df = get_etf_data()

        print("开始获取代表池数据...")
        representative_df = get_representative_data()

        # 恢复自选股顺序和名称
        stock_codes = [code for code, _ in STOCK_LIST]
        name_map = {code: name for code, name in STOCK_LIST}
        order_map = {code: i for i, (code, _) in enumerate(STOCK_LIST)}

        watch_df = watch_df[watch_df["代码"].isin(stock_codes)].copy()
        watch_df["排序"] = watch_df["代码"].map(order_map)
        watch_df = watch_df.sort_values("排序").drop(columns=["排序"])
        watch_df["名称"] = watch_df["代码"].map(name_map).fillna(watch_df["名称"])

        prev_df = load_previous_snapshot()
        watch_df = add_previous_compare(watch_df, prev_df)
        representative_df = add_previous_compare(representative_df, prev_df)

        watch_df = add_stock_scores(watch_df)

        index_breadth = calc_breadth(index_df, "指数")
        etf_breadth = calc_breadth(etf_df, "ETF")
        rep_breadth = calc_breadth(representative_df, "代表池")
        watch_breadth = calc_breadth(watch_df, "自选池")

        temp = make_temperature(index_df, etf_df, representative_df, watch_df)

        rep_sector_df = sector_strength(representative_df)
        watch_sector_df = sector_strength(watch_df)

        decision_panel = make_decision_panel(temp, etf_df, rep_sector_df, watch_sector_df, watch_df)

        html = generate_html(
            watch_df=watch_df,
            representative_df=representative_df,
            index_df=index_df,
            etf_df=etf_df,
            temp=temp,
            decision_panel=decision_panel,
            index_breadth=index_breadth,
            etf_breadth=etf_breadth,
            rep_breadth=rep_breadth,
            watch_breadth=watch_breadth,
            rep_sector_df=rep_sector_df,
            watch_sector_df=watch_sector_df,
            version_name=version_name,
        )

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)

        with open(history_file, "w", encoding="utf-8") as f:
            f.write(html)

        write_latest_files(version_name)
        save_snapshot(watch_df, representative_df)

        print(f"最新网页已生成：{OUTPUT_FILE}")
        print(f"唯一历史网页已生成：{history_file}")
        print("latest_url.txt 已生成")
        print("latest_manifest.json 已生成")
        print("latest_snapshot.csv 已生成")
        print(f"自选股数量：{len(watch_df)}")
        print(f"代表池数量：{len(representative_df)}")
        print(f"指数数量：{len(index_df)}")
        print(f"ETF数量：{len(etf_df)}")

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

    return


if __name__ == "__main__":
    main()
