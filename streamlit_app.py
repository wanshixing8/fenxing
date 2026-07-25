"""
分形监控 — Streamlit嵌入PWA + 浏览器端数据代理
"""
import streamlit as st
import json, os

st.set_page_config(page_title="分形监控", page_icon="⌂", layout="wide")

HTML_FILE = os.path.join(os.path.dirname(__file__), "fractal_app.html")

# ═══════════════════════════════════════════
# 第1步：在Streamlit宿主页面注入数据代理JS
# （宿主页面≠iframe，可直接fetch腾讯API）
# ═══════════════════════════════════════════
proxy_js = """
<script>
(function(){
  if (window.__fractalProxyReady) return;
  window.__fractalProxyReady = true;

  // 监听iframe发来的数据请求
  window.addEventListener('message', async function(e) {
    const msg = e.data;
    if (!msg || msg.src !== 'fractal_pwa') return;

    const reqId = msg.reqId;
    try {
      if (msg.type === 'kline') {
        const url = 'https://ifzq.gtimg.cn/appstock/app/kline/mkline?param='
                  + msg.code + ',' + msg.period + ',,' + msg.count;
        const resp = await fetch(url, {
          headers: { 'Referer': 'https://finance.qq.com' }
        });
        const data = await resp.json();
        const rows = (data.data||{})[msg.code]?.[msg.period] || [];
        const bars = rows.map(function(r){
          var s = r[0], dt;
          if (s.length===12) dt = s.slice(0,4)+'-'+s.slice(4,6)+'-'+s.slice(6,8)+'T'+s.slice(8,10)+':'+s.slice(10,12);
          else dt = s.slice(0,4)+'-'+s.slice(4,6)+'-'+s.slice(6,8);
          return {dt:dt, o:+r[1], c:+r[2], h:+r[3], l:+r[4], vol:(+(r[5]||0))*100};
        });

        // 发回给iframe
        e.source.postMessage({
          src: 'fractal_proxy',
          reqId: reqId,
          type: 'kline_reply',
          ok: true,
          bars: bars
        }, '*');
      }
      else if (msg.type === 'name') {
        const url = 'http://qt.gtimg.cn/q=' + msg.code;
        const resp = await fetch(url);
        const text = await resp.text();
        const m = text.match(/~([^~]+)/);
        e.source.postMessage({
          src: 'fractal_proxy',
          reqId: reqId,
          type: 'name_reply',
          ok: true,
          name: m ? m[1] : msg.code
        }, '*');
      }
    } catch(err) {
      e.source.postMessage({
        src: 'fractal_proxy',
        reqId: reqId,
        type: (msg.type==='kline'?'kline_reply':'name_reply'),
        ok: false,
        error: err.message
      }, '*');
    }
  });

  console.log('🔄 分形数据代理已就绪（宿主页面）');
})();
</script>
"""

st.markdown(proxy_js, unsafe_allow_html=True)
st.caption("🔄 数据代理已就绪")

# ═══════════════════════════════════════════
# 第2步：渲染PWA（iframe内，通过postMessage获取数据）
# ═══════════════════════════════════════════
try:
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    st.components.v1.html(html, height=800, scrolling=True)
except FileNotFoundError:
    st.error("fractal_app.html 未找到")
except Exception as e:
    st.error(f"错误: {e}")
