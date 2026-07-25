"""
分形监控 — 服务端预取K线数据注入PWA
"""
import streamlit as st
import urllib.request, json, os, re

st.set_page_config(page_title="分形监控", page_icon="⌂", layout="wide")

# ═══════════════════════════════════════════
# 预取默认K线数据，注入HTML避免iframe CSP问题
# ═══════════════════════════════════════════
DEFAULT_CODE = "sh601985"
DEFAULT_PERIOD = "m5"
DEFAULT_COUNT = 320

def fetch_tencent_kline(code, period, count):
    """服务端取腾讯K线，不受CSP限制"""
    url = f"https://ifzq.gtimg.cn/appstock/app/kline/mkline?param={code},{period},,{count}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.qq.com"
        })
        raw = urllib.request.urlopen(req, timeout=15).read()
        return raw.decode("utf-8")
    except Exception as e:
        return json.dumps({"error": str(e)})

default_kline = fetch_tencent_kline(DEFAULT_CODE, DEFAULT_PERIOD, DEFAULT_COUNT)

# ═══════════════════════════════════════════
# API 代理模式（其他请求走这里）
# ═══════════════════════════════════════════
query = st.query_params
if "code" in query and "period" in query:
    code = query.get("code", DEFAULT_CODE)
    period = query.get("period", DEFAULT_PERIOD)
    count = query.get("count", DEFAULT_COUNT)
    raw = fetch_tencent_kline(code, period, count)
    st.text(f"__JSON__{raw}__JSON__")
    st.stop()

if "name_code" in query:
    code = query.get("name_code", "")
    url = f"http://qt.gtimg.cn/q={code}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=10).read()
        text = raw.decode("gbk", errors="replace")
        m = re.search(r'~([^~]+)', text)
        st.text(f"__JSON__{json.dumps({'code': code, 'name': m.group(1) if m else code})}__JSON__")
    except Exception as e:
        st.text(f"__JSON__{json.dumps({'error': str(e)})}__JSON__")
    st.stop()

# ═══════════════════════════════════════════
# PWA 模式：注入预取数据
# ═══════════════════════════════════════════
HTML_FILE = os.path.join(os.path.dirname(__file__), "fractal_app.html")
try:
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    # 注入预取数据，PWA优先使用
    inject = f'<script>window.__PRELOAD__ = {default_kline};</script>'
    html = html.replace('<script>', inject + '\n<script>', 1)
    st.components.v1.html(html, height=800, scrolling=True)
except FileNotFoundError:
    st.error("fractal_app.html 未找到")
