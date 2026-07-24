"""
fractal_api.py — 纯 API 分形引擎（无本地文件依赖）
==================================================
兼容 Streamlit Cloud / 任何 Python 环境。数据全部来自腾讯公开接口。

用法:
    from fractal_api import compute_fractal, fetch_stock_name
    result = compute_fractal("601238")  # 返回完整分形数据 + 信号
"""
import json, math, urllib.request, re
from datetime import datetime, date
from fractal_core import envelope_at, compute_segment_decays

# ═══════════════════════════════════════════
#  数据层
# ═══════════════════════════════════════════

def _tencent_code(code: str) -> str:
    code = code.strip()
    if code.startswith("6"):
        return "sh" + code
    else:
        return "sz" + code


def fetch_stock_name(code: str) -> str:
    """获取股票名称"""
    tc = _tencent_code(code)
    try:
        url = f"http://qt.gtimg.cn/q={tc}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=8).read().decode("gbk")
        name = raw.split("~")[1] if "~" in raw else code
        return name
    except:
        return code


def fetch_realtime_price(code: str) -> float | None:
    """实时报价"""
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


def fetch_kline(code: str, period: str, count: int = 320) -> list[dict]:
    """拉 K 线数据。
    period: 'm5' | 'm30' | 'day'
    返回: [{dt, o, h, l, c, vol, amt}, ...] 按时间升序
    """
    tc = _tencent_code(code)
    url = f"http://ifzq.gtimg.cn/appstock/app/kline/mkline?param={tc},{period},,{count}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    MAX_RETRIES = 3
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            raw = urllib.request.urlopen(req, timeout=15).read().decode()
            data = json.loads(raw)
            break
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                import time; time.sleep(2 * (attempt + 1))
    else:
        raise last_err

    rows = data["data"][tc][period]
    bars = []
    for r in rows:
        dt = datetime.strptime(r[0], "%Y%m%d%H%M" if period != "day" else "%Y%m%d")
        o, c, h, l = float(r[1]), float(r[2]), float(r[3]), float(r[4])
        vol = float(r[5]) * 100  # 手→股
        bars.append({"dt": dt, "o": o, "h": h, "l": l, "c": round(c, 2), "vol": vol, "amt": 0})
    return bars


def fetch_daily_kline(code: str, count: int = 160) -> list[dict]:
    """拉日线（腾讯用独立的前复权接口）"""
    tc = _tencent_code(code)
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc},day,,,{count},qfq"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    MAX_RETRIES = 3
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            raw = urllib.request.urlopen(req, timeout=15).read().decode()
            data = json.loads(raw)
            break
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                import time; time.sleep(2 * (attempt + 1))
    else:
        raise last_err

    # 腾讯日线前复权格式: [日期, 开, 收, 高, 低, 成交量(股)]
    rows = data["data"][tc].get("qfqday", []) or data["data"][tc].get("day", [])
    bars = []
    for r in rows:
        dt = datetime.strptime(r[0], "%Y-%m-%d")
        o, c, h, l = float(r[1]), float(r[2]), float(r[3]), float(r[4])
        vol = float(r[5])
        bars.append({"dt": dt, "o": o, "h": h, "l": l, "c": round(c, 2), "vol": vol, "amt": 0})
    return bars


def fetch_30min_kline(code: str, count: int = 320) -> list[dict]:
    """拉 30 分钟线（腾讯接口直接提供 m30）"""
    return fetch_kline(code, "m30", count)


def fetch_5min_kline(code: str, count: int = 640) -> list[dict]:
    """拉 5 分钟线"""
    return fetch_kline(code, "m5", count)


# ═══════════════════════════════════════════
#  分形计算（与 auto_fractal.py 完全一致）
# ═══════════════════════════════════════════

def _deduplicate(bars: list[dict], precision: int = 2) -> list[dict]:
    """去重：合并连续重复的收盘价"""
    if not bars:
        return bars
    result = [bars[0]]
    for b in bars[1:]:
        if round(b["c"], precision) != round(result[-1]["c"], precision):
            result.append(b)
    return result


def _find_pivots(bars: list[dict], level: str = "5min") -> tuple[list[float], list[str]]:
    """识别价格拐点（已去重）。
    返回: (价格列表, 类型列表['H'|'L'])
    """
    prices = [b["c"] for b in bars]
    if len(prices) < 3:
        return [], []

    pivots_y = [prices[0]]
    pivots_type = ["H" if len(prices) > 1 and prices[0] > prices[1] else "L"]

    for i in range(1, len(prices) - 1):
        a, b, c = prices[i-1], prices[i], prices[i+1]
        if a < b > c:
            pivots_y.append(b)
            pivots_type.append("H")
        elif a > b < c:
            pivots_y.append(b)
            pivots_type.append("L")

    pivots_y.append(prices[-1])
    last_type = "H" if prices[-1] > prices[-2] else "L"
    pivots_type.append(last_type)

    return pivots_y, pivots_type


def _build_generator(ys: list[float], types: list[str]) -> list[float]:
    """筛选三级嵌套包络生成器"""
    if len(ys) < 5:
        return ys[-3:] if len(ys) >= 3 else ys

    W_EST = len(ys) * 2 // 3
    env_phases = W_EST // 3

    generators = [ys[0]]
    for i in range(1, len(ys) - 1):
        phase = i / W_EST if W_EST > 0 else 0
        env = envelope_at(phase, 1/3)
        dist = abs(ys[i] - generators[-1])

        if env < 0.015:
            break

        do_include = False
        if types[i] != types[i-1]:
            # 方向翻转，收紧条件
            if dist > 0.005 * (1 + env):
                do_include = True
        else:
            # 同方向延伸
            if dist > 0.003 * (1 + env * 0.5):
                do_include = True

        if do_include:
            generators.append(ys[i])

    return generators


def compute_fractal(code: str, level: str = "all", pin_price: float | None = None):
    """核心计算入口。

    Args:
        code: 股票代码，如 "601238"
        level: "all" | "daily" | "30min" | "5min"
        pin_price: 可选，固定锚点价格

    Returns:
        dict: 包含完整分形数据、信号、错误信息
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
    }

    try:
        name = fetch_stock_name(code)
        result["name"] = name
    except:
        result["name"] = code

    try:
        live_price = fetch_realtime_price(code)
        result["live_price"] = live_price
    except:
        pass

    # ── 日线 ──
    daily = None
    if level in ("daily", "all"):
        try:
            daily_bars = fetch_daily_kline(code, 160)
            daily_dedup = _deduplicate(daily_bars)
            daily_prices = [b["c"] for b in daily_dedup]
            daily_piv_y, daily_piv_t = _find_pivots(daily_dedup, "daily")
            daily_gen = _build_generator(daily_piv_y, daily_piv_t)
            daily = {
                "bars_count": len(daily_bars),
                "pivots": [{"y": y, "type": t} for y, t in zip(daily_piv_y, daily_piv_t)],
                "generators": daily_gen,
                "last_type": daily_piv_t[-1] if daily_piv_t else None,
                "last_value": daily_piv_y[-1] if daily_piv_y else None,
                "pmax": None,
                "pmin": None,
            }
            # 极值
            if len(daily_gen) >= 2:
                gen_y = daily_gen
                daily["pmax"] = {"y": max(gen_y), "idx": gen_y.index(max(gen_y))}
                daily["pmin"] = {"y": min(gen_y), "idx": gen_y.index(min(gen_y))}
            result["daily"] = daily
        except Exception as e:
            result["daily"] = {"error": str(e)}

    # ── 30min ──
    min30 = None
    if level in ("30min", "all"):
        try:
            bars30 = fetch_30min_kline(code, 320)
            dedup30 = _deduplicate(bars30)
            piv_y30, piv_t30 = _find_pivots(dedup30, "30min")
            gen30 = _build_generator(piv_y30, piv_t30)
            min30 = {
                "bars_count": len(bars30),
                "pivots": [{"y": y, "type": t} for y, t in zip(piv_y30, piv_t30)],
                "generators": gen30,
                "last_type": piv_t30[-1] if piv_t30 else None,
                "last_value": piv_y30[-1] if piv_y30 else None,
                "pmax": None,
                "pmin": None,
            }
            if len(gen30) >= 2:
                min30["pmax"] = {"y": max(gen30), "idx": gen30.index(max(gen30))}
                min30["pmin"] = {"y": min(gen30), "idx": gen30.index(min(gen30))}
            result["30min"] = min30
        except Exception as e:
            result["30min"] = {"error": str(e)}

    # ── 5min ──
    min5 = None
    if level in ("5min", "all"):
        try:
            bars5 = fetch_5min_kline(code, 640)
            dedup5 = _deduplicate(bars5)
            piv_y5, piv_t5 = _find_pivots(dedup5, "5min")
            gen5 = _build_generator(piv_y5, piv_t5)
            min5 = {
                "bars_count": len(bars5),
                "pivots": [{"y": y, "type": t} for y, t in zip(piv_y5, piv_t5)],
                "generators": gen5,
                "last_type": piv_t5[-1] if piv_t5 else None,
                "last_value": piv_y5[-1] if piv_y5 else None,
                "pmax": None,
                "pmin": None,
            }
            if len(gen5) >= 2:
                min5["pmax"] = {"y": max(gen5), "idx": gen5.index(max(gen5))}
                min5["pmin"] = {"y": min(gen5), "idx": gen5.index(min(gen5))}
            result["5min"] = min5
        except Exception as e:
            result["5min"] = {"error": str(e)}

    # ── 共振点 ──
    if daily and min30 and min5:
        resonance = []
        for dp in daily.get("pivots", []):
            dy, dt = dp["y"], dp["type"]
            for mp in min30.get("pivots", []):
                if abs(dy - mp["y"]) < 0.03:
                    for fp in min5.get("pivots", []):
                        if abs(dy - fp["y"]) < 0.03:
                            resonance.append({"y": round(dy, 2), "type": dt})
                            break
                    break
        result["resonance"] = resonance[:15]

    # ── 交易信号 ──
    if (min5 and not min5.get("error") and len(min5.get("generators", [])) >= 2):
        result["signal"] = _compute_signal(result)
    elif (min30 and not min30.get("error") and len(min30.get("generators", [])) >= 2):
        result["signal"] = _compute_signal(result, prefer="30min")

    return result


def _compute_signal(result: dict, prefer: str = "5min") -> dict:
    """计算交易信号"""
    level = result.get(prefer) or result.get("30min") or result.get("daily")
    if not level:
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
        target_val = pmin.get("y", last_val) if pmin else last_val
    else:
        target_val = pmax.get("y", last_val) if pmax else last_val
    signal["target"] = round(target_val, 2)

    # 止损
    margin = max(last_val * 0.005, 0.02)
    if last_type == "H":
        signal["stop"] = round(last_val + margin, 2)
    else:
        signal["stop"] = round(last_val - margin, 2)

    # 盈亏比
    reward = abs(target_val - last_val)
    risk = abs(signal["stop"] - last_val)
    signal["rr"] = round(reward / risk, 2) if risk > 0 else 0

    # 三层一致
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
    if min30_lt and min5_lt:
        signal["pendulum"] = (min5_lt != min30_lt)
    else:
        signal["pendulum"] = False

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
    print(f"🧪 测试 fractal_api.compute_fractal('{code}')")
    r = compute_fractal(code)
    if r["error"]:
        print(f"❌ {r['error']}")
    else:
        print(f"✅ {r['name']} | 现价={r.get('live_price')}")
        for lv in ["daily", "30min", "5min"]:
            lvd = r.get(lv, {})
            if lvd and not lvd.get("error"):
                print(f"  {lv}: {len(lvd.get('generators',[]))} 个生成器, 末点={lvd.get('last_value')} ({lvd.get('last_type')})")
        sig = r.get("signal", {})
        if sig:
            print(f"  信号: {sig['direction']} | 入场={sig['entry']} | 止盈={sig['target']} | 止损={sig['stop']} | RR={sig['rr']}")
