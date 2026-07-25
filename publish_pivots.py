"""拐点摘要发布脚本 v2 — 三层（周线+日线+30min），全量主板

每天盘后运行 publish_pivots.py --batch：
  1. 扫描所有沪深主板标的（60xxxx + 00xxxx）
  2. 每只计算 周线 / 日线 / 30min 拐点
  3. 导出 deploy/pivots_{code}.json（~12 KB / 只）
  4. 生成 deploy/pivots_index.json 索引
  5. 总耗时 ~40 分钟，总大小 ~36 MB

用法:
  py publish_pivots.py 601985       # 单标的测试
  py publish_pivots.py --batch      # 全量主板
  py publish_pivots.py --top 100    # 只跑long_rank前100名
"""

import json, os, sys, glob
from datetime import datetime

# ── 数据源路径 ──
EXPORT_ROOT = r"D:\海王星金融终端-中国银河证券\T0002\export"
DEPLOY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy")


# ═══════════════════════════════════════════════
#  拐点检测核心（纯 window 分形，不跑 CZSC fusion）
# ═══════════════════════════════════════════════
def find_fractals(highs, lows, window):
    """找顶底分形拐点，返回 [(index, price, 'H'|'L'), ...]"""
    n = len(highs)
    if n < 2 * window + 1:
        return []

    pivots = []
    for i in range(window, n - window):
        h, l = highs[i], lows[i]
        # 顶分形
        if all(h >= highs[i - j] and h >= highs[i + j] for j in range(1, window + 1)):
            pivots.append((i, round(float(h), 3), "H"))
        # 底分形
        if all(l <= lows[i - j] and l <= lows[i + j] for j in range(1, window + 1)):
            pivots.append((i, round(float(l), 3), "L"))

    return sorted(pivots, key=lambda x: x[0])


def alternation_filter(pivots):
    """确保 H-L 交替，去掉连续同向拐点"""
    if len(pivots) < 2:
        return pivots
    result = [pivots[0]]
    for p in pivots[1:]:
        if p[2] != result[-1][2]:
            result.append(p)
    return result


def make_generator(pivots, count):
    """取最后 count 个拐点，去连续同向"""
    recent = pivots[-count * 2:]  # 多取一些避免同向
    gen = []
    for _, price, kind in recent:
        if not gen:
            gen.append((price, kind))
        elif kind != gen[-1][1]:
            gen.append((price, kind))
    return gen[-count:]


def read_5min_bars(code):
    """从本地券商导出文件读取 5 分钟 K 线"""
    market = "SH" if code[0] == "6" else "SZ"
    fpath = os.path.join(EXPORT_ROOT, "5分钟", f"{market}#{code}.txt")

    if not os.path.exists(fpath):
        return None

    bars = []
    with open(fpath, "r", encoding="gbk") as f:
        for i, line in enumerate(f):
            if i < 2:
                continue
            parts = line.strip().split()
            if len(parts) < 8:
                continue
            bars.append({
                "h": float(parts[3]),
                "l": float(parts[4]),
                "c": float(parts[5]),
                "dt": parts[0] + " " + parts[1],
            })
    return bars if bars else None


def read_daily_bars(code):
    """从本地券商导出文件读取日线 K 线"""
    market = "SH" if code[0] == "6" else "SZ"
    fpath = os.path.join(EXPORT_ROOT, f"{market}#{code}.txt")

    if not os.path.exists(fpath):
        return None

    bars = []
    with open(fpath, "r", encoding="gbk") as f:
        for i, line in enumerate(f):
            if i < 2:
                continue
            parts = line.strip().split()
            if len(parts) < 7:
                continue
            bars.append({
                "h": float(parts[2]),
                "l": float(parts[3]),
                "c": float(parts[4]),
                "dt": parts[0],
            })
    return bars if bars else None


def compute_pivots_summary(code, name=""):
    """计算单个标的的三层拐点摘要"""
    # ── 日线 ──
    dbars = read_daily_bars(code)
    if not dbars:
        return None

    hD = [b["h"] for b in dbars]
    lD = [b["l"] for b in dbars]
    fxD = find_fractals(hD, lD, window=2)
    fxD = alternation_filter(fxD)

    # ── 周线（从日线合成，5 日一组取 HL） ──
    wbars = []
    for i in range(0, len(dbars), 5):
        chunk = dbars[i:i + 5]
        if chunk:
            wbars.append({"h": max(b["h"] for b in chunk),
                          "l": min(b["l"] for b in chunk)})
    hW = [b["h"] for b in wbars]
    lW = [b["l"] for b in wbars]
    fxW = find_fractals(hW, lW, window=1)
    fxW = alternation_filter(fxW)

    # ── 30min（从 5min 合成，6 根一组） ──
    bars5 = read_5min_bars(code)
    pivots_30 = []
    gen_30 = []
    if bars5:
        m30 = []
        for i in range(0, len(bars5), 6):
            chunk = bars5[i:i + 6]
            if chunk:
                m30.append({"h": max(b["h"] for b in chunk),
                            "l": min(b["l"] for b in chunk),
                            "c": chunk[-1]["c"]})
        h30 = [b["h"] for b in m30]
        l30 = [b["l"] for b in m30]
        fx30 = find_fractals(h30, l30, window=5)
        fx30 = alternation_filter(fx30)
        pivots_30 = [(int(idx), round(float(price), 3), kind) for idx, price, kind in fx30]
        gen_30_raw = make_generator(fx30, 6)
        gen_30 = [round(price, 3) for price, _ in gen_30_raw]

    pivots_D = [(int(idx), round(float(price), 3), kind) for idx, price, kind in fxD]
    pivots_W = [(int(idx), round(float(price), 3), kind) for idx, price, kind in fxW]
    gen_D_raw = make_generator(fxD, 4)
    gen_D = [round(price, 3) for price, _ in gen_D_raw]
    gen_W_raw = make_generator(fxW, 3)
    gen_W = [round(price, 3) for price, _ in gen_W_raw]

    summary = {
        "code": code,
        "name": name,
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_bars_weekly": len(wbars),
        "n_bars_daily": len(dbars),
        "n_bars_30min": len(pivots_30) > 0 if bars5 else 0,
        "pivots_weekly": pivots_W,
        "pivots_daily": pivots_D,
        "pivots_30min": pivots_30,
        "gen_weekly": gen_W,
        "gen_daily": gen_D,
        "gen_30min": gen_30,
        "last_pivot_weekly": pivots_W[-1] if pivots_W else None,
        "last_pivot_daily": pivots_D[-1] if pivots_D else None,
        "last_pivot_30min": pivots_30[-1] if pivots_30 else None,
    }

    return summary


def publish_single(code):
    """发布单个标的的拐点摘要 JSON"""
    name = _get_name(code)
    summary = compute_pivots_summary(code, name)
    if not summary:
        print(f"    ⚠️ {code} 无数据")
        return None

    os.makedirs(DEPLOY_DIR, exist_ok=True)

    out_path = os.path.join(DEPLOY_DIR, f"pivots_{code}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False)

    size_kb = os.path.getsize(out_path) / 1024
    print(f"    ✅ {out_path} ({size_kb:.1f} KB)")
    return summary


def scan_main_board_codes():
    """扫描本地券商导出目录，找出所有沪深主板标的"""
    codes = set()
    m5_dir = os.path.join(EXPORT_ROOT, "5分钟")
    if not os.path.exists(m5_dir):
        print(f"[WARN] 5分钟数据目录不存在: {m5_dir}")
        return []

    # 文件直接放在 5分钟\ 根目录，格式 SH#601985.txt / SZ#000001.txt
    for fname in os.listdir(m5_dir):
        for prefix in ["SH", "SZ"]:
            if fname.startswith(f"{prefix}#") and fname.endswith(".txt"):
                c = fname.replace(f"{prefix}#", "").replace(".txt", "")
                if len(c) == 6 and c.isdigit():
                    # 只留主板：60xxxx 和 00xxxx（排除BJ/3/688等）
                    if c.startswith("60") or c.startswith("00"):
                        codes.add(c)

    return sorted(codes)


def publish_batch(top_n=None):
    """批量发布所有沪深主板标的"""
    all_codes = scan_main_board_codes()
    print(f"\n📊 扫描到 {len(all_codes)} 只沪深主板标的")

    if top_n:
        # 取 long_rank 前 N 名
        ranked = _get_ranked_codes()
        if ranked:
            codes = ranked[:top_n]
            # 把不在扫描结果中的去掉
            code_set = set(all_codes)
            codes = [c for c in codes if c in code_set]
            print(f"🎯 取 long_rank 前 {len(codes)} 名（请求 {top_n}）")
        else:
            print("[WARN] 无 long_rank 结果，回退到全量扫描")
            codes = all_codes
    else:
        codes = all_codes

    print(f"📦 开始发布 {len(codes)} 只标的拐点...\n")

    results = []
    n = 0
    for code in codes:
        n += 1
        msg = f"[{n}/{len(codes)}] {code}"
        try:
            name = _get_name(code)
            print(f"  {msg} {name}", end=" ", flush=True)
            s = compute_pivots_summary(code, name)
            if s:
                os.makedirs(DEPLOY_DIR, exist_ok=True)
                out_path = os.path.join(DEPLOY_DIR, f"pivots_{code}.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(s, f, ensure_ascii=False)
                kb = os.path.getsize(out_path) / 1024
                print(f"✅ {kb:.1f}KB")
                results.append(s)
            else:
                print("⚠️ 无数据")
        except Exception as e:
            print(f"❌ {e}")

    # 生成索引
    index = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(results),
        "stocks": [{"code": r["code"], "name": r["name"]} for r in results],
    }
    with open(os.path.join(DEPLOY_DIR, "pivots_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)

    print(f"\n✅ 完成: {len(results)}/{len(codes)} 标的，索引 deploy/pivots_index.json")


def _get_ranked_codes():
    """从最新的 long_rank 结果中提取排名列表"""
    rank_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rank")
    if not os.path.exists(rank_dir):
        return []
    rank_files = sorted(glob.glob(os.path.join(rank_dir, "long_*.txt")), reverse=True)
    if not rank_files:
        return []

    codes = []
    with open(rank_files[0], "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0].rstrip(".").isdigit():
                code = parts[1]
                if len(code) == 6 and code.isdigit():
                    codes.append(code)
    return codes


def _get_name(code):
    """从腾讯 API 获取股票名称（带缓存）"""
    _name_cache = getattr(_get_name, "_cache", None)
    if _name_cache is None:
        _get_name._cache = {}
    if code in _get_name._cache:
        return _get_name._cache[code]
    try:
        import urllib.request, re
        market = "sh" if code[0] == "6" else "sz"
        url = f"https://qt.gtimg.cn/q={market}{code}"
        resp = urllib.request.urlopen(url, timeout=5)
        text = resp.read().decode("gbk", errors="replace")
        m = re.search(r'~([^~]+)', text)
        name = m.group(1) if m else code
    except:
        name = code
    _get_name._cache[code] = name
    return name


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--batch":
            publish_batch()
        elif arg == "--top":
            top_n = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            publish_batch(top_n=top_n)
        else:
            # 单标的
            s = publish_single(arg)
            if s:
                print(f"✅ {s['code']} {s['name']} — {len(s['pivots_daily'])}日线拐点 / {len(s['pivots_30min'])}30min拐点")
    else:
        print("用法:")
        print("  py publish_pivots.py 601985       # 单标的测试")
        print("  py publish_pivots.py --batch      # 全量沪深主板")
        print("  py publish_pivots.py --top 100    # long_rank 前100名")
