"""
分形监控 — 同源查询代理: PWA fetch /?proxy=... → Python 抓腾讯API → 返回数据
"""
import streamlit as st
import json as json_mod
import urllib.request
import os

st.set_page_config(page_title="分形监控", page_icon="⌂", layout="wide")

HTML_FILE = os.path.join(os.path.dirname(__file__), "fractal_app.html")

# ═══════════════════════════════════════════
# 代理端点: 当 query param 含 ?proxy= 时，抓腾讯 API 返回数据
# ═══════════════════════════════════════════
params = st.query_params
if "proxy" in params:
    raw = params["proxy"]  # 格式: sh601238,m5,320 或 sh601238__name
    parts = raw.split(",")
    resp_data = {"ok": False, "error": "unknown"}

    try:
        if parts[0].endswith("__name"):
            # 股票名称查询
            tc = parts[0].replace("__name", "")
            url = f"http://qt.gtimg.cn/q={tc}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                text = r.read().decode("gbk", errors="replace")
            import re
            m = re.search(r'~([^~]+)', text)
            resp_data = {"ok": True, "name": m.group(1) if m else tc}
        else:
            # K线数据查询
            code = parts[0]
            period = parts[1] if len(parts) > 1 else "m5"
            count = parts[2] if len(parts) > 2 else "320"
            url = f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={code},{period},,{count}"
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://finance.qq.com"
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json_mod.loads(r.read().decode("utf-8"))
            rows = ((data.get("data") or {}).get(code) or {}).get(period) or []
            bars = []
            for r_ in rows:
                s = r_[0]
                if len(s) == 12:
                    dt = s[:4] + "-" + s[4:6] + "-" + s[6:8] + "T" + s[8:10] + ":" + s[10:12]
                else:
                    dt = s[:4] + "-" + s[4:6] + "-" + s[6:8]
                bars.append({"dt": dt, "o": float(r_[1]), "c": float(r_[2]),
                             "h": float(r_[3]), "l": float(r_[4]),
                             "vol": (float(r_[5]) if r_[5] else 0) * 100})
            resp_data = {"ok": True, "bars": bars}
    except Exception as e:
        resp_data = {"ok": False, "error": str(e)}

    # 把 JSON 藏在 div 中返回
    st.markdown(
        f'<div id="fx-data" style="display:none">{json_mod.dumps(resp_data, ensure_ascii=False)}</div>',
        unsafe_allow_html=True
    )
    st.stop()

# ═══════════════════════════════════════════
# 正常模式: 渲染 PWA iframe
# ═══════════════════════════════════════════
try:
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    st.components.v1.html(html, height=800, scrolling=True)
except FileNotFoundError:
    st.error("fractal_app.html 未找到")
except Exception as e:
    st.error(f"错误: {e}")
