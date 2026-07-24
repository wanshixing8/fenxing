"""
fractal_api_v2.py — 分形引擎（本地文件优先，API兜底）
=====================================================
与 auto_fractal.py 完全一致的算法 + 数据源策略：
  1. 优先读本地海王星导出文件（数据量最大）
  2. 本地文件不存在时降级到腾讯API
  3. 30min 始终从 5min 合成（与 auto_fractal.py 一致）
  4. 分形检测用 find_fractals_hl（High/Low+窗口）
  5. 生成器用严格 H/L 交替选取

用法:
    from fractal_api_v2 import compute_fractal, fetch_stock_name
    result = compute_fractal("601238")
"""
import json, math, urllib.request, os, sys
from datetime import datetime, date

# ═══════════════════════════════════════════
#  数据层（本地文件 + API 双源）
# ═══════════════════════════════════════════

# 海王星导出目录
EXPORT_ROOT = os.environ.get(
    "FRACTAL_EXPORT_ROOT",
    r"D:\海王星金融终端-中国银河证券\T0002\export"
)


def _tencent_code(code: str) -> str:
    code = code.strip()
    return "sh" + code if code.startswith("6") else "sz" + code


def _resolve_paths(code: str):
    """解析本地文件路径"""
    market = "SH" if code.startswith("6") else "SZ"
    prefix = f"{market}#{code}.txt"
    src_5min = os.path.join(EXPORT_ROOT, "5分钟", prefix)
    src_daily = os.path.join(EXPORT_ROOT, prefix)
    return src_5min, src_daily


def fetch_stock_name(code: str) -> str:
    tc = _tencent_code(code)
    try:
        url = f"http://qt.gtimg.cn/q={tc}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=8).read().decode("gbk")
        return raw.split("~")[1] if "~" in raw else code
    except:
        return code


def fetch_realtime_price(code: str) -> float | None:
    tc = _tencent_code(code)
    try:
        url = f"http://qt.gtimg.cn/q={tc}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=8).read().decode("gbk")
        parts = raw.split("~")
        if len(parts) > 3:
            return float(parts[3])
    except:
        pass
    return None


# ── 本地文件读取（与 auto_fractal.py 完全一致） ──

def load_5min_local(path: str) -> list[dict]:
    """读本地5分钟导出文件（8列：日期 时间 开 高 低 收 量 额）"""
    bars = []
    with open(path, "r", encoding="gbk") as f:
        for i, line in enumerate(f):
            if i < 2:
                continue
            parts = line.strip().split()
            if len(parts) < 8:
                continue
            dt = datetime.strptime(parts[0] + parts[1], "%Y%m%d%H%M")
            o, h, l, c = float(parts[2]), float(parts[3]), float(parts[4]), float(parts[5])
            vol = float(parts[6])
            amt = float(parts[7])
            bars.append({"dt": dt, "o": o, "h": h, "l": l, "c": round(c, 2),
                         "vol": vol, "amt": amt})
    return bars


def load_daily_local(path: str) -> list[dict]:
    """读本地日线导出文件（7列：日期 开 高 低 收 量 额）"""
    bars = []
    with open(path, "r", encoding="gbk") as f:
        for i, line in enumerate(f):
            if i < 2:
                continue
            parts = line.strip().split()
            if len(parts) < 7:
                continue
            dt = datetime.strptime(parts[0], "%Y%m%d")
            o, h, l, c = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            vol = float(parts[5])
            amt = float(parts[6])
            bars.append({"dt": dt, "o": o, "h": h, "l": l, "c": round(c, 2),
                         "vol": vol, "amt": amt})
    return bars


# ── API 降级读取 ──

def _api_fetch(url: str, timeout: int = 15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_err = None
    for attempt in range(3):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
        except Exception as e:
            last_err = e
            if attempt < 2:
                import time; time.sleep(2 * (attempt + 1))
    raise last_err


def fetch_5min_api(code: str, count: int = 640) -> list[dict]:
    """从腾讯 API 拉 5min K 线（降级用）"""
    tc = _tencent_code(code)
    url = f"http://ifzq.gtimg.cn/appstock/app/kline/mkline?param={tc},m5,,{count}"
    data = _api_fetch(url)
    rows = data["data"][tc]["m5"]
    bars = []
    for r in rows:
        dt = datetime.strptime(r[0], "%Y%m%d%H%M")
        o, c, h, l = float(r[1]), float(r[2]), float(r[3]), float(r[4])
        vol = float(r[5]) * 100
        bars.append({"dt": dt, "o": o, "h": h, "l": l, "c": round(c, 2),
                     "vol": vol, "amt": 0})
    return bars


def fetch_daily_api(code: str, count: int = 800) -> list[dict]:
    """从腾讯 API 拉日线（前复权，降级用）"""
    tc = _tencent_code(code)
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc},day,,,{count},qfq"
    data = _api_fetch(url)
    rows = data["data"][tc].get("qfqday", [])
    if not rows:
        rows = data["data"][tc].get("day", [])
    bars = []
    for r in rows:
        dt = datetime.strptime(r[0], "%Y-%m-%d")
        o, c, h, l = float(r[1]), float(r[2]), float(r[3]), float(r[4])
        vol = float(r[5])
        bars.append({"dt": dt, "o": o, "h": h, "l": l, "c": round(c, 2),
                     "vol": vol, "amt": 0})
    return bars


# ═══════════════════════════════════════════
#  分形计算（与 auto_fractal.py 完全一致）
# ═══════════════════════════════════════════

def find_fractals_hl(highs: list[float], lows: list[float], window: int = 5):
    """检测分形拐点（High/Low + 窗口），支持平底/平顶合并。
    与 auto_fractal.py 的 find_fractals_hl 完全一致。
    大数据量时自动降采样加速。

    返回: [(index, price, 'H'|'L'), ...]
    """
    n = len(highs)

    # 大数据量时降采样加速（>5000 根时采样到 5000）
    if n > 5000:
        step = n // 5000
        idx_map = list(range(0, n, step))
        highs_sampled = [highs[i] for i in idx_map]
        lows_sampled = [lows[i] for i in idx_map]
        n_s = len(highs_sampled)
        ws = max(window * 2 // step, 2) if step > 1 else window
    else:
        step = 1
        idx_map = list(range(n))
        highs_sampled = highs
        lows_sampled = lows
        n_s = n
        ws = window

    if n_s < ws * 2 + 1:
        return []
    pivots_h = []
    pivots_l = []

    for i in range(ws, n_s - ws):
        left_h = highs_sampled[i - ws:i]
        right_h = highs_sampled[i + 1:i + 1 + ws]
        left_l = lows_sampled[i - ws:i]
        right_l = lows_sampled[i + 1:i + 1 + ws]

        # 高点
        if (all(x <= highs_sampled[i] for x in left_h) and all(x <= highs_sampled[i] for x in right_h) and
                (any(x < highs_sampled[i] for x in left_h) or any(x < highs_sampled[i] for x in right_h))):
            pivots_h.append((idx_map[i], highs_sampled[i], 'H'))

        # 低点
        if (all(x >= lows_sampled[i] for x in left_l) and all(x >= lows_sampled[i] for x in right_l) and
                (any(x > lows_sampled[i] for x in left_l) or any(x > lows_sampled[i] for x in right_l))):
            pivots_l.append((idx_map[i], lows_sampled[i], 'L'))

    # 合并平底/平顶
    def merge_plateau(pivots):
        if not pivots:
            return []
        result = []
        i = 0
        while i < len(pivots):
            j = i
            while j + 1 < len(pivots) and pivots[j + 1][0] == pivots[j][0] + 1 and pivots[j + 1][2] == pivots[j][2]:
                j += 1
            mid = (i + j) // 2
            result.append(pivots[mid])
            i = j + 1
        return result

    pivots_h = merge_plateau(pivots_h)
    pivots_l = merge_plateau(pivots_l)

    # 合并排序，交替去重
    all_pivots = sorted(pivots_h + pivots_l, key=lambda p: p[0])
    result = []
    for p in all_pivots:
        if not result:
            result.append(p)
        elif result[-1][2] == p[2]:
            if p[2] == 'H' and p[1] > result[-1][1]:
                result[-1] = p
            elif p[2] == 'L' and p[1] < result[-1][1]:
                result[-1] = p
        else:
            result.append(p)
    return result


def group_30min(bars5: list[dict]) -> tuple[list[dict], list[dict]]:
    """从 5min K 线合成 30min K 线（每 6 根合 1 根）。
    与 auto_fractal.py 的 group_30min 完全一致。
    
    返回: (m30_bars, leftover_5min)
    """
    m30 = []
    i = 0
    while i + 6 <= len(bars5):
        group = bars5[i:i + 6]
        o = group[0]["o"]
        c = group[-1]["c"]
        h = max(g["h"] for g in group)
        l = min(g["l"] for g in group)
        vol = sum(g.get("vol", 0) for g in group)
        amt = sum(g.get("amt", 0) for g in group)
        m30.append({"dt": group[0]["dt"], "o": o, "h": h, "l": l, "c": round(c, 2),
                    "vol": vol, "amt": amt})
        i += 6
    leftover = bars5[i:]
    return m30, leftover


def extract_generators(fractals: list, end_idx: int = None, max_count: int = 6) -> list[float]:
    """从分形拐点提取严格 H/L 交替的生成器。
    与 auto_fractal.py 的生成器提取逻辑一致（从末点往前取交替点）。
    
    返回: [价格, ...] 从左到右（最早到最晚）
    """
    vals = [f[1] for f in fractals]
    types = [f[2] for f in fractals]

    if end_idx is None:
        end_idx = len(vals) - 1

    gen = [vals[end_idx]]
    for i in range(end_idx - 1, -1, -1):
        if types[i] != types[i + 1]:
            gen.insert(0, vals[i])
        if len(gen) >= max_count:
            break
    return gen


# ═══════════════════════════════════════════
#  核心计算入口
# ═══════════════════════════════════════════

def compute_fractal(code: str, level: str = "all"):
    """核心计算入口。

    Args:
        code: 股票代码，如 "601238"
        level: "all" | "daily" | "30min" | "5min"

    Returns:
        dict: 包含完整分形数据、信号
    """
    result = {
        "code": code,
        "name": "",
        "level": level,
        "live_price": None,
        "daily": None,
        "30min": None,
        "5min": None,
        "signal": None,
        "resonance": [],
        "error": None,
        "fetched_at": datetime.now().isoformat(),
        "data_source": "unknown",
    }

    try:
        result["name"] = fetch_stock_name(code)
    except:
        result["name"] = code

    try:
        result["live_price"] = fetch_realtime_price(code)
    except:
        pass

    # ── 判断数据源 ──
    src_5min, src_daily = _resolve_paths(code)
    has_local_5min = os.path.isfile(src_5min)
    has_local_daily = os.path.isfile(src_daily)

    if has_local_5min:
        result["data_source"] = "local"
    else:
        result["data_source"] = "api"

    # ── 加载 5min ──
    bars5 = []
    if has_local_5min:
        try:
            bars5 = load_5min_local(src_5min)
        except Exception as e:
            result["5min"] = {"error": f"本地5min加载失败: {e}"}
            bars5 = []

    # 盘中尝试合并当日 API 数据
    if bars5:
        local_last_date = bars5[-1]["dt"].date()
        if local_last_date < date.today():
            try:
                live_bars = fetch_5min_api(code, 640)
                today_bars = [b for b in live_bars if b["dt"].date() == date.today()]
                if today_bars:
                    merged = [b for b in bars5 if b["dt"].date() < date.today()]
                    merged.extend(today_bars)
                    bars5 = merged
                    result["data_source"] = "local+api_today"
            except:
                pass

    if not bars5:
        try:
            bars5 = fetch_5min_api(code, 640)
            result["data_source"] = "api"
        except Exception as e:
            result["5min"] = {"error": f"API 5min 加载失败: {e}"}
            return result

    # ── 合成 30min ──
    m30, leftover5 = group_30min(bars5)

    # ── 加载/合成日线 ──
    daily_bars = []
    if has_local_daily and level in ("daily", "all"):
        try:
            daily_bars = load_daily_local(src_daily)
        except:
            daily_bars = []

    if not daily_bars and level in ("daily", "all"):
        try:
            daily_bars = fetch_daily_api(code, 800)
        except:
            # 降级：从 5min 按日期聚合
            from collections import OrderedDict
            days = OrderedDict()
            for b in bars5:
                d = b["dt"].date()
                if d not in days:
                    days[d] = {"dt": datetime(d.year, d.month, d.day), "o": b["o"],
                               "h": b["h"], "l": b["l"], "c": b["c"], "vol": 0.0, "amt": 0.0}
                else:
                    dd = days[d]
                    dd["h"] = max(dd["h"], b["h"])
                    dd["l"] = min(dd["l"], b["l"])
                    dd["c"] = b["c"]
                days[d]["vol"] += b.get("vol", 0)
                days[d]["amt"] += b.get("amt", 0)
            daily_bars = list(days.values())
            for r in daily_bars:
                r["c"] = round(r["c"], 2)

    # ── 分形检测 ──
    # 5min
    h5 = [b["h"] for b in bars5]
    l5 = [b["l"] for b in bars5]
    fractals_5 = find_fractals_hl(h5, l5, window=5)
    gen5 = extract_generators(fractals_5, max_count=6)

    min5_result = {
        "bars_count": len(bars5),
        "fractals_raw": len(fractals_5),
        "generators": gen5,
        "last_type": fractals_5[-1][2] if fractals_5 else None,
        "last_value": fractals_5[-1][1] if fractals_5 else None,
        "pmax": None, "pmin": None,
    }
    if len(gen5) >= 2:
        min5_result["pmax"] = {"y": max(gen5), "idx": gen5.index(max(gen5))}
        min5_result["pmin"] = {"y": min(gen5), "idx": gen5.index(min(gen5))}
    result["5min"] = min5_result

    # 30min
    h30 = [b["h"] for b in m30]
    l30 = [b["l"] for b in m30]
    fractals_30 = find_fractals_hl(h30, l30, window=5)
    gen30 = extract_generators(fractals_30, max_count=6)

    min30_result = {
        "bars_count": len(m30),
        "fractals_raw": len(fractals_30),
        "generators": gen30,
        "last_type": fractals_30[-1][2] if fractals_30 else None,
        "last_value": fractals_30[-1][1] if fractals_30 else None,
        "pmax": None, "pmin": None,
    }
    if len(gen30) >= 2:
        min30_result["pmax"] = {"y": max(gen30), "idx": gen30.index(max(gen30))}
        min30_result["pmin"] = {"y": min(gen30), "idx": gen30.index(min(gen30))}
    result["30min"] = min30_result

    # 日线
    if daily_bars:
        hD = [b["h"] for b in daily_bars]
        lD = [b["l"] for b in daily_bars]
        fractals_D = find_fractals_hl(hD, lD, window=2)
        genD = extract_generators(fractals_D, max_count=4)

        daily_result = {
            "bars_count": len(daily_bars),
            "fractals_raw": len(fractals_D),
            "generators": genD,
            "last_type": fractals_D[-1][2] if fractals_D else None,
            "last_value": fractals_D[-1][1] if fractals_D else None,
            "pmax": None, "pmin": None,
        }
        if len(genD) >= 2:
            daily_result["pmax"] = {"y": max(genD), "idx": genD.index(max(genD))}
            daily_result["pmin"] = {"y": min(genD), "idx": genD.index(min(genD))}
        result["daily"] = daily_result

    # ── 共振点（三级拐点价格接近的点） ──
    resonance = []
    for d in fractals_D:
        for m in fractals_30:
            if abs(d[1] - m[1]) < 0.03:
                for f in fractals_5:
                    if abs(d[1] - f[1]) < 0.03:
                        resonance.append({"y": round(d[1], 2), "type": d[2]})
                        break
                break
    result["resonance"] = resonance[:15]

    # ── 交易信号 ──
    if gen30:
        result["signal"] = _compute_signal_v2(result)

    return result


def _compute_signal_v2(result: dict) -> dict:
    """计算交易信号（三层嵌套判断）"""
    # 优先 5min，没有则用 30min
    level = result.get("5min") or result.get("30min")
    if not level or level.get("error"):
        return {}

    last_type = level["last_type"]
    last_val = level["last_value"]
    pmax = level.get("pmax", {})
    pmin = level.get("pmin", {})

    signal = {
        "bank": last_type,
        "direction": "down" if last_type == "H" else "up",
        "entry": last_val,
    }

    # 目标
    if last_type == "H":
        signal["target"] = round(pmin.get("y", last_val), 2) if pmin else last_val
    else:
        signal["target"] = round(pmax.get("y", last_val), 2) if pmax else last_val

    # 止损
    margin = max(last_val * 0.005, 0.02)
    signal["stop"] = round(last_val + margin, 2) if last_type == "H" else round(last_val - margin, 2)

    # 盈亏比
    reward = abs(signal["target"] - last_val)
    risk = abs(signal["stop"] - last_val)
    signal["rr"] = round(reward / risk, 2) if risk > 0 else 0

    # 三层一致性
    daily_lt = (result.get("daily") or {}).get("last_type")
    min30_lt = (result.get("30min") or {}).get("last_type")
    min5_lt = (result.get("5min") or {}).get("last_type")
    if daily_lt and min30_lt and min5_lt:
        dir_d = "down" if daily_lt == "H" else "up"
        dir_30 = "down" if min30_lt == "H" else "up"
        dir_5 = "down" if min5_lt == "H" else "up"
        signal["three_consistent"] = (dir_d == dir_30 == dir_5)
    else:
        signal["three_consistent"] = False

    # 钟摆
    signal["pendulum"] = (min5_lt != min30_lt) if (min30_lt and min5_lt) else False

    # 距目标/止损
    lp = result.get("live_price") or last_val
    if last_type == "H":
        signal["dist_to_target_pct"] = round((lp - signal["target"]) / lp * 100, 2)
        signal["dist_to_stop_pct"] = round((signal["stop"] - lp) / lp * 100, 2)
    else:
        signal["dist_to_target_pct"] = round((signal["target"] - lp) / lp * 100, 2)
        signal["dist_to_stop_pct"] = round((lp - signal["stop"]) / lp * 100, 2)
    signal["live_price"] = lp

    return signal


# ═══════════════════════════════════════════
#  自检
# ═══════════════════════════════════════════

if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "601238"
    print(f"🧪 测试 fractal_api_v2.compute_fractal('{code}')")
    r = compute_fractal(code)
    print(f"📡 数据源: {r['data_source']}")
    if r["error"]:
        print(f"❌ {r['error']}")
    else:
        print(f"✅ {r['name']} | 现价={r.get('live_price')}")
        for lv in ["daily", "30min", "5min"]:
            lvd = r.get(lv, {})
            if lvd and not lvd.get("error"):
                print(f"  {lv}: {lvd.get('bars_count')}根 → {lvd.get('fractals_raw')}拐点 → {len(lvd.get('generators',[]))}生成器, 末点={lvd.get('last_value')} ({lvd.get('last_type')})")
        sig = r.get("signal", {})
        if sig:
            print(f"  信号: {sig['direction']} | 入场={sig['entry']} | 止盈={sig['target']} | 止损={sig['stop']} | RR={sig['rr']} | 三层一致={sig['three_consistent']}")
