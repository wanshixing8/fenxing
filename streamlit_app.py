"""
分形监控 — Streamlit嵌入PWA + 服务端预取数据注入
"""
import streamlit as st
import urllib.request, json, os

st.set_page_config(page_title="分形监控", page_icon="⌂", layout="wide")

HTML_FILE = os.path.join(os.path.dirname(__file__), "fractal_app.html")

# ═══════════════════════════════════════════
# 服务端预取腾讯K线
# ═══════════════════════════════════════════
def fetch_tencent_kline(code, period, count=320):
    """服务端从腾讯抓K线，返回 [bars] 或 None"""
    url = f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={code},{period},,{count}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.qq.com"
        })
        raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
        data = json.loads(raw)
        if data.get("code") != 0:
            return None
        rows = data.get("data", {}).get(code, {}).get(period)
        if not rows:
            return None
        bars = []
        for r in rows:
            s = r[0]
            if len(s) == 12:  # 分时: YYYYMMDDHHMM
                dt = f"{s[:4]}-{s[4:6]}-{s[6:8]}T{s[8:10]}:{s[10:12]}"
            else:  # 日线: YYYYMMDD
                dt = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
            bars.append({
                "dt": dt, "o": float(r[1]), "c": float(r[2]),
                "h": float(r[3]), "l": float(r[4]), "vol": (float(r[5] or 0)) * 100
            })
        return bars
    except Exception as e:
        st.sidebar.warning(f"预取 {code} {period} 失败: {e}")
        return None

# ═══════════════════════════════════════════
# 预取默认标的的日线+5min
# ═══════════════════════════════════════════
DEFAULT_CODES = ["sh601238", "sh601985"]
preload = {}
for code in DEFAULT_CODES:
    day = fetch_tencent_kline(code, "day", 500)
    if day:
        preload[f"{code}__day"] = day
    m5 = fetch_tencent_kline(code, "m5", 320)
    if m5:
        preload[f"{code}__m5"] = m5

st.sidebar.success(f"✅ 服务端预取: {len(preload)}/{len(DEFAULT_CODES)*2} 数据集")

# ═══════════════════════════════════════════
# 注入预取数据到 PWA HTML
# ═══════════════════════════════════════════
try:
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    inject = f'<script>window.__PRELOAD__ = {json.dumps(preload, ensure_ascii=False)};</script>'
    html = html.replace('<script>', inject + '\n<script>', 1)

    st.components.v1.html(html, height=800, scrolling=True)
except FileNotFoundError:
    st.error("fractal_app.html 未找到")
except Exception as e:
    st.error(f"错误: {e}")
