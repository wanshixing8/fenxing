"""
分形监控 — 双iframe: 代理iframe + PWA iframe, localStorage通信
"""
import streamlit as st
import os

st.set_page_config(page_title="分形监控", page_icon="⌂", layout="wide")

HTML_FILE = os.path.join(os.path.dirname(__file__), "fractal_app.html")

# ═══════════════════════════════════════════
# 代理iframe：监听localStorage请求，fetch腾讯API后回写
# ═══════════════════════════════════════════
PROXY_HTML = """<!DOCTYPE html><html><body>
<script>
(function(){
  // 清除旧数据
  var keys = [];
  for (var i=0; i<localStorage.length; i++) keys.push(localStorage.key(i));
  keys.forEach(function(k){ if(k.startsWith('fx_')) localStorage.removeItem(k); });

  // 监听来自PWA的请求
  var _fetching = {};
  window.addEventListener('storage', function(e) {
    if (!e.key || !e.key.startsWith('fx_req_')) return;
    if (!e.newValue) return;
    var req;
    try { req = JSON.parse(e.newValue); } catch(ex) { return; }
    var reqId = req.reqId;
    if (!reqId || _fetching[reqId]) return;
    _fetching[reqId] = true;

    // 清除请求marker
    localStorage.removeItem(e.key);

    if (req.type === 'kline') {
      var url = 'https://ifzq.gtimg.cn/appstock/app/kline/mkline?param='
              + req.code + ',' + req.period + ',,' + req.count;
      fetch(url, {headers: {'Referer':'https://finance.qq.com'}})
        .then(function(r){ return r.json(); })
        .then(function(data){
          var rows = ((data.data||{})[req.code]||{})[req.period] || [];
          var bars = rows.map(function(r){
            var s=r[0], dt;
            if (s.length===12) dt=s.slice(0,4)+'-'+s.slice(4,6)+'-'+s.slice(6,8)+'T'+s.slice(8,10)+':'+s.slice(10,12);
            else dt=s.slice(0,4)+'-'+s.slice(4,6)+'-'+s.slice(6,8);
            return {dt:dt, o:+r[1], c:+r[2], h:+r[3], l:+r[4], vol:(+(r[5]||0))*100};
          });
          localStorage.setItem('fx_res_'+reqId, JSON.stringify({ok:true, bars:bars}));
          delete _fetching[reqId];
        })
        .catch(function(err){
          localStorage.setItem('fx_res_'+reqId, JSON.stringify({ok:false, error:err.message}));
          delete _fetching[reqId];
        });
    }
    else if (req.type === 'name') {
      fetch('http://qt.gtimg.cn/q='+req.code)
        .then(function(r){ return r.text(); })
        .then(function(text){
          var m = text.match(/~([^~]+)/);
          localStorage.setItem('fx_res_'+reqId, JSON.stringify({ok:true, name: m?m[1]:req.code}));
          delete _fetching[reqId];
        })
        .catch(function(err){
          localStorage.setItem('fx_res_'+reqId, JSON.stringify({ok:false, error:err.message}));
          delete _fetching[reqId];
        });
    }
  });

  console.log('🔄 代理iframe就绪');
})();
</script>
</body></html>"""

# 先渲染代理（隐藏的）
st.components.v1.html(PROXY_HTML, height=0, scrolling=False)

# 然后渲染PWA
try:
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    st.components.v1.html(html, height=800, scrolling=True)
except FileNotFoundError:
    st.error("fractal_app.html 未找到")
except Exception as e:
    st.error(f"错误: {e}")
