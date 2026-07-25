"""
分形监控 Streamlit CORS 代理
部署到 https://share.streamlit.io/ → 新建 App → 指向此文件
仅做一件事：转发腾讯K线/报价API，加 CORS 头给 PWA 用
"""
import streamlit as st
import urllib.request
import urllib.parse
import json

st.set_page_config(page_title="分形监控·数据代理", page_icon="⌂", layout="centered")

# ── 风险提示 ──
st.markdown("""
<div style="background:#1a1a2e;padding:16px;border-radius:8px;border:1px solid #f44336;text-align:center">
<h3 style="color:#f44336">⚠️ 风险郑重提示</h3>
<p style="color:#aaa;font-size:13px;line-height:1.8">
没有高手，没有万能药，盈亏在心，所有预测都是欺骗<br>
软件只是换个角度看市场，改变不了贪嗔痴和盈亏<br>
市场无敌，熊市最好的方法是不操作，永不亏钱的方法是不碰股票<br>
<b style="color:#f44336">【仅限内部交流，转发分享违法，切记！】</b>
</p>
</div>
""", unsafe_allow_html=True)

# ── API 代理 ──
query = st.query_params

if "code" in query and ("period" in query or "count" in query):
    # /?code=sh601985&period=m5&count=320
    code = query.get("code", "sh601985")
    period = query.get("period", "m5")
    count = query.get("count", "320")
    url = f"http://ifzq.gtimg.cn/appstock/app/kline/mkline?param={code},{period},,{count}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=15).read()
        data = json.loads(raw)
        st.json(data)
    except Exception as e:
        st.error(f"K线代理失败: {e}")

elif "name_code" in query:
    code = query.get("name_code", "")
    url = f"http://qt.gtimg.cn/q={code}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=10).read()
        text = raw.decode("gbk", errors="replace")
        m = __import__("re").search(r'~([^~]+)', text)
        name = m.group(1) if m else code
        st.json({"code": code, "name": name})
    except Exception as e:
        st.error(f"名称代理失败: {e}")

else:
    st.markdown("""
<div style="color:#888;text-align:center;padding:40px">
<p>📡 数据代理运行中</p>
<p style="font-size:12px">供分形监控 PWA 后端使用</p>
<p style="font-size:11px;color:#555">v1.0 · © wsx · 内部交流 禁止转发</p>
</div>
""", unsafe_allow_html=True)
