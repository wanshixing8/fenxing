"""
分形监控 — 纯前端PWA + K线代理
部署: https://share.streamlit.io/ → 指向此文件
"""
import streamlit as st
import urllib.request, urllib.parse, json, os, re

st.set_page_config(page_title="分形监控", page_icon="⌂", layout="wide")

query = st.query_params

# ═══════════════════════════════════════════
# API 代理模式（PWA 内部 fetch 走这里）
# ═══════════════════════════════════════════
if "code" in query and "period" in query:
    code = query.get("code", "sh601985")
    period = query.get("period", "m5")
    count = query.get("count", "320")
    url = f"http://ifzq.gtimg.cn/appstock/app/kline/mkline?param={code},{period},,{count}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=15).read()
        st.json(json.loads(raw))
    except Exception as e:
        st.json({"error": str(e)})
    st.stop()

if "name_code" in query:
    code = query.get("name_code", "")
    url = f"http://qt.gtimg.cn/q={code}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=10).read()
        text = raw.decode("gbk", errors="replace")
        m = re.search(r'~([^~]+)', text)
        st.json({"code": code, "name": m.group(1) if m else code})
    except Exception as e:
        st.json({"error": str(e)})
    st.stop()

# ═══════════════════════════════════════════
# PWA 模式：嵌入完整前端
# ═══════════════════════════════════════════
HTML_FILE = os.path.join(os.path.dirname(__file__), "fractal_app.html")
try:
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    st.components.v1.html(html, height=800, scrolling=True)
except FileNotFoundError:
    st.error("fractal_app.html 未找到，请确保与 streamlit_app.py 同目录部署")
