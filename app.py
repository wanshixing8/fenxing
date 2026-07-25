"""
河与岸分形系统 — 多用户 Web 版
================================
部署: 推送到 GitHub → Streamlit Cloud 自动部署
访问密码: 通过环境变量 FRACTAL_PASSWORD 设置（默认 "888888"）
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.subplots as sp
from datetime import datetime
import random
import hashlib
import os
from fractal_api_v2 import compute_fractal, fetch_stock_name, fetch_realtime_price

st.set_page_config(
    page_title="河与岸 · 分形投射",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ═══════════════════════════════════════════
#  密码保护
# ═══════════════════════════════════════════

PASSWORD_HASH = hashlib.sha256(
    os.environ.get("FRACTAL_PASSWORD", "888888").encode()
).hexdigest()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("""
    <style>
    .login-box {
        max-width: 400px; margin: 80px auto; padding: 40px;
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 1px solid #333; border-radius: 16px; text-align: center;
    }
    .login-box h1 { color: #ffd700; font-size: 28px; margin-bottom: 6px; }
    .login-box .sub { color: #888; font-size: 13px; margin-bottom: 24px; }
    </style>
    <div class="login-box">
        <h1>📊 河与岸</h1>
        <p class="sub">三级嵌套包络分形投射系统</p>
    """, unsafe_allow_html=True)

    pwd = st.text_input("访问密码", type="password", key="login_pwd", placeholder="请输入访问密码")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🔓 进入系统", use_container_width=True):
            if hashlib.sha256(pwd.encode()).hexdigest() == PASSWORD_HASH:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("密码错误")

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ═══════════════════════════════════════════
#  CSS
# ═══════════════════════════════════════════

st.markdown("""
<style>
    .main-header { color: #ffd700; font-size: 22px; font-weight: bold; }
    .sig-panel { background: #1e1e36; border: 1px solid #333; border-radius: 10px;
                 padding: 14px 18px; margin: 8px 0; }
    .sig-row { display: flex; flex-wrap: wrap; gap: 16px; justify-content: space-around; }
    .sig-item { text-align: center; min-width: 80px; }
    .sig-label { font-size: 10px; color: #888; }
    .sig-value { font-size: 16px; font-weight: bold; }
    .triple-banner { max-width: 100%; margin: 8px auto; border-radius: 10px;
                     padding: 12px 18px; text-align: center; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.7; } }
    .footer { text-align: center; color: #555; font-size: 11px; margin-top: 20px; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════
#  工具栏
# ═══════════════════════════════════════════

col_title, col_logout = st.columns([5, 1])
with col_title:
    st.markdown('<p class="main-header">📊 河与岸 · 分形投射系统</p>', unsafe_allow_html=True)
with col_logout:
    if st.button("🚪 退出", key="logout"):
        st.session_state.authenticated = False
        st.rerun()

# ═══════════════════════════════════════════
#  风险提示
# ═══════════════════════════════════════════

st.markdown("""
<div style="
    background: linear-gradient(90deg, #3d1a1a, #2d1515);
    border: 1px solid #d32f2f; border-left: 4px solid #d32f2f;
    border-radius: 8px; padding: 10px 16px; margin: 8px 0 14px 0;
    font-size: 12px; line-height: 1.7; color: #e0a0a0;
">
    <strong style="color:#ff6b6b;font-size:13px">⚠️ 风险郑重提示</strong><br>
    本网站仅为金融时间序列分形算法<strong>技术演示程序</strong>，仅对历史 K 线图形进行数学绘图展示。<br>
    本工具<strong>不提供</strong>任何证券分析、行情预测、选股、买卖操作建议，<strong>不构成</strong>任何投资咨询意见。<br>
    股票、金融市场存在极高风险，所有市场形态历史走势<strong>不能推演</strong>未来收益。<br>
    作者<strong>不承担</strong>任何用户依据本页面图形自行交易产生的盈亏责任。<br>
    严禁将本工具作为交易决策依据。
</div>
""", unsafe_allow_html=True)

# 代码输入 + 回车即分析
code = st.text_input("股票代码", value="601238", placeholder="如 601238、600519",
                     key="code_input", on_change=lambda: st.session_state.update(trigger_go=True))

col_level, col_go, col_refresh = st.columns([2, 2, 1])

with col_level:
    level = st.selectbox("级别", ["all", "daily", "30min", "5min"],
                         format_func=lambda x: {"all": "全部三级", "daily": "日线",
                                                "30min": "30分钟", "5min": "5分钟"}[x],
                         on_change=lambda: st.session_state.update(trigger_go=True))

with col_go:
    st.write("")
    go_clicked = st.button("🔍 开始分析", use_container_width=True, key="go_btn",
                           type="primary")

with col_refresh:
    st.write("")
    auto_refresh = st.checkbox("⏱ 自动刷新", value=False, key="auto_refresh")

if auto_refresh:
    st.markdown(f'<p style="color:#ff6600;font-size:12px">⚡ 每60秒自动刷新 | 上次: {datetime.now().strftime("%H:%M:%S")}</p>',
                unsafe_allow_html=True)
    import time
    time.sleep(60)
    st.rerun()

# ═══════════════════════════════════════════
#  计算 & 渲染
# ═══════════════════════════════════════════

# 首次加载或点击分析（含回车触发）
if "trigger_go" not in st.session_state:
    st.session_state.trigger_go = False

if go_clicked or st.session_state.trigger_go:
    with st.spinner(f"📡 正在获取 {code} 数据..."):
        result = compute_fractal(code, level)
    st.session_state.last_result = result
    st.session_state.last_code = code
    st.session_state.trigger_go = False
else:
    result = st.session_state.get("last_result", {})

if result.get("error"):
    st.error(f"计算失败: {result['error']}")
    st.stop()

# ═══════════════════════════════════════════
#  信号面板
# ═══════════════════════════════════════════

signal = result.get("signal", {})

if signal:
    bank = signal.get("bank", "?")
    bank_color = "#ff6666" if bank == "H" else "#66ff66"
    bank_emoji = "🏔️" if bank == "H" else "🏖️"
    direction = signal.get("direction", "?")
    dir_emoji = "↘️ 做空" if direction == "down" else "↗️ 做多"
    dir_color = "#ff4444" if direction == "down" else "#44ff44"
    rr = signal.get("rr", 0)
    rr_color = "#44ff44" if rr >= 2 else ("#ffd700" if rr >= 1 else "#ff4444")
    con = signal.get("three_consistent", False)
    con_str = "✅ 三层一致" if con else "⚠️ 矛盾"
    con_color = "#ffd700" if con else "#ff8844"

    st.markdown(f"""
    <div class="sig-panel">
    <div class="sig-row">
        <div class="sig-item"><div class="sig-label">标的</div><div class="sig-value" style="color:#ffd700">{code} {result.get('name','')}</div></div>
        <div class="sig-item"><div class="sig-label">当前岸</div><div class="sig-value" style="color:{bank_color}">{bank_emoji} {bank}岸 {signal['entry']:.2f}</div></div>
        <div class="sig-item"><div class="sig-label">方向</div><div class="sig-value" style="color:{dir_color}">{dir_emoji}</div></div>
        <div class="sig-item"><div class="sig-label">止盈 🎯</div><div class="sig-value" style="color:#44ff44">{signal['target']:.2f}</div></div>
        <div class="sig-item"><div class="sig-label">止损 🛑</div><div class="sig-value" style="color:#ff4444">{signal['stop']:.2f}</div></div>
        <div class="sig-item"><div class="sig-label">盈亏比</div><div class="sig-value" style="color:{rr_color}">R:R {rr}</div></div>
        <div class="sig-item"><div class="sig-label">三层</div><div class="sig-value" style="color:{con_color};font-size:13px">{con_str}</div></div>
        <div class="sig-item"><div class="sig-label">现价</div><div class="sig-value" style="color:#ff5050">{signal.get('live_price','N/A')}</div></div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    # 三级共振横幅
    if con:
        all_dir = direction
        if all_dir == "up":
            banner_bg = "linear-gradient(135deg, #0a3a0a, #1a1a2e, #0a3a0a)"
            banner_border = "#44ff44"
            banner_icon = "🔥🔥🔥"
            banner_label = "三级共振做多"
            banner_color = "#44ff44"
        else:
            banner_bg = "linear-gradient(135deg, #3a0a0a, #1a1a2e, #3a0a0a)"
            banner_border = "#ff4444"
            banner_icon = "💀💀💀"
            banner_label = "三级共振做空"
            banner_color = "#ff4444"
        st.markdown(f"""
        <div class="triple-banner" style="background:{banner_bg};border:2px solid {banner_border};box-shadow:0 0 20px {banner_border}44;animation:pulse 1.5s ease-in-out infinite">
            <div style="font-size:20px;font-weight:bold;color:{banner_color}">{banner_icon} {banner_label} {banner_icon}</div>
            <div style="font-size:13px;color:#ccc">日线 · 30min · 5min 三层方向共振</div>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════
#  图表渲染 (Plotly)
# ═══════════════════════════════════════════

def plot_fractal(result, level):
    """用 Plotly 渲染分形图，替代原来的 Canvas"""
    daily = result.get("daily")
    min30 = result.get("30min")
    min5 = result.get("5min")

    if level == "daily":
        data = daily
        title_suffix = "日线"
        color_main = "#ffcc00"
    elif level == "30min":
        data = min30
        title_suffix = "30分钟"
        color_main = "#c090ff"
    elif level == "5min":
        data = min5
        title_suffix = "5分钟"
        color_main = "#4cc9f0"
    else:
        data = min5
        title_suffix = "全部三级"
        color_main = "#4cc9f0"

    if not data or data.get("error"):
        st.warning(f"{title_suffix} 数据不可用")
        return

    generators = data.get("generators", [])
    pivots = data.get("pivots", [])
    pmax = data.get("pmax", {})
    pmin = data.get("pmin", {})

    fig = go.Figure()

    # 生成器连线
    if generators:
        xs = list(range(len(generators)))
        fig.add_trace(go.Scatter(
            x=xs, y=generators, mode='lines+markers',
            name=f'{title_suffix}生成器',
            line=dict(color=color_main, width=2.5),
            marker=dict(size=8, symbol='diamond', color=color_main),
            hovertemplate='%{y:.2f}',
        ))

    # 投射区虚线
    if generators and len(generators) >= 3:
        sep_idx = len(generators) * 2 // 3
        hist_x = xs[:sep_idx+1]
        hist_y = generators[:sep_idx+1]
        proj_x = xs[sep_idx:]
        proj_y = generators[sep_idx:]
        fig.add_trace(go.Scatter(
            x=proj_x, y=proj_y, mode='lines',
            name='投射区', line=dict(color=color_main, width=1.5, dash='dot'),
            showlegend=False,
        ))

    # 止损/止盈/入场
    signal = result.get("signal", {})
    if signal:
        entry = signal.get("entry")
        target = signal.get("target")
        stop = signal.get("stop")
        if entry:
            fig.add_hline(y=entry, line_dash="dash", line_color="white", opacity=0.4,
                          annotation_text=f"入场 {entry}", annotation_position="top right")
        if target:
            fig.add_hline(y=target, line_dash="dash", line_color="#44ff44", opacity=0.5,
                          annotation_text=f"止盈 {target}", annotation_position="top right")
        if stop:
            fig.add_hline(y=stop, line_dash="dash", line_color="#ff4444", opacity=0.5,
                          annotation_text=f"止损 {stop}", annotation_position="top right")

    # 极值标注
    if pmax:
        fig.add_annotation(x=pmax.get("idx", 0), y=pmax["y"],
                           text=f"高 {pmax['y']:.2f}", showarrow=True,
                           arrowhead=2, arrowcolor="#ff6666", font=dict(color="#ff6666"))
    if pmin:
        fig.add_annotation(x=pmin.get("idx", 0), y=pmin["y"],
                           text=f"低 {pmin['y']:.2f}", showarrow=True,
                           arrowhead=2, arrowcolor="#66ff66", font=dict(color="#66ff66"))

    # 共振点
    resonance = result.get("resonance", [])
    if resonance and level == "all":
        res_ys = [r["y"] for r in resonance]
        for r in resonance[:10]:
            fig.add_hline(y=r["y"], line_dash="dot", line_color="#ffd700", opacity=0.3)

    fig.update_layout(
        title=dict(
            text=f"{result.get('code','')} {result.get('name','')} · {title_suffix}分形投射",
            font=dict(color="#e0e0e0", size=16),
        ),
        plot_bgcolor="#16213e",
        paper_bgcolor="#1a1a2e",
        font=dict(color="#ccc"),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="分形步数"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title="价格",
                   tickformat=".2f"),
        height=500,
        margin=dict(l=40, r=40, t=50, b=40),
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )

    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════
#  多级图表区
# ═══════════════════════════════════════════

if level == "all":
    tabs = st.tabs(["📅 日线", "🕐 30分钟", "⏱ 5分钟"])

    with tabs[0]:
        plot_fractal(result, "daily")

    with tabs[1]:
        plot_fractal(result, "30min")

    with tabs[2]:
        plot_fractal(result, "5min")
else:
    plot_fractal(result, level)


# ═══════════════════════════════════════════
#  数据面板
# ═══════════════════════════════════════════

with st.expander("📋 详细数据", expanded=False):
    col_d, col_30, col_5 = st.columns(3)

    for col, lv, name in [(col_d, "daily", "日线"), (col_30, "30min", "30分钟"), (col_5, "5min", "5分钟")]:
        with col:
            lvd = result.get(lv)
            if lvd and not lvd.get("error"):
                gen = lvd.get("generators", [])
                last_t = lvd.get("last_type", "?")
                last_v = lvd.get("last_value", "?")
                st.markdown(f"**{name}**")
                st.write(f"末点: {last_v} ({last_t})")
                st.write(f"生成器: {len(gen)} 个")
                if gen:
                    st.write(f"序列: {' → '.join(f'{y:.2f}' for y in gen)}")
                pmax = lvd.get("pmax")
                pmin = lvd.get("pmin")
                if pmax:
                    st.write(f"投射高: {pmax['y']:.2f}")
                if pmin:
                    st.write(f"投射低: {pmin['y']:.2f}")

    resonance = result.get("resonance", [])
    if resonance:
        st.markdown("**⚡ 共振点**")
        res_str = ', '.join(f"{r['y']:.2f}({r['type']})" for r in resonance[:15])
        st.write(res_str)


# ═══════════════════════════════════════════
#  页脚
# ═══════════════════════════════════════════

st.markdown(f"""
<div class="footer">
    河与岸分形投射系统 v2.0 | 数据源: 腾讯行情 | 更新时间: {result.get('fetched_at', datetime.now().isoformat())[:19]}
</div>
""", unsafe_allow_html=True)
