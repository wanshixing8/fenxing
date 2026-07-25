# 📊 河与岸 · 分形投射系统（多用户 Web 版）

三级嵌套包络分形系统 — 从 A 股日线/30min/5min K 线数据自动识别分形拐点，投射未来包络，生成交易信号。

> 代码托管在 GitHub，部署到 **Streamlit Cloud**（免费），支持多用户 + 密码保护。

---

## 🚀 快速部署（5 分钟）

### 1. Fork 此仓库到你的 GitHub

### 2. 部署到 Streamlit Cloud

1. 访问 [share.streamlit.io](https://share.streamlit.io)
2. 用 GitHub 登录
3. 点击 **New app** → 选择你的仓库 → 主文件选 `app.py`
4. 点击 **Deploy**

### 3. 设置访问密码（可选）

在 Streamlit Cloud 的 **Settings → Secrets** 中添加：

```toml
FRACTAL_PASSWORD = "你的密码"
```

默认密码是 `888888`。

---

## 📖 功能

| 功能 | 说明 |
|------|------|
| 🔐 密码保护 | 多用户安全隔离 |
| 🔍 任意 A 股代码 | 输入 6 位代码，自动识别市场 |
| 📊 三级分形 | 日线 / 30分钟 / 5分钟 三级嵌套包络 |
| 🎯 交易信号 | 入场价、止盈、止损、盈亏比 R:R |
| 🔗 三级共振 | 日线+30min+5min 三方向一致时高亮警示 |
| ⏰ 钟摆预警 | 5min 已翻转但 30min 未变 |
| ⚡ 共振点 | 三级重叠价格区域高亮 |
| ⏱ 自动刷新 | 60 秒自动更新（盘中模式） |
| 📱 响应式 | 手机/平板/桌面均可访问 |

---

## 🏗️ 架构

```
fractal_api.py       ← 纯 API 引擎（腾讯行情接口）
    ↓
fractal_core.py      ← 核心算法（包络函数）
    ↓
app.py               ← Streamlit Web 界面
```

- **零本地文件依赖**：全部数据来自腾讯公开 HTTP 接口
- **无数据库**：每次请求实时计算
- **纯 Python**：`fractal_core.py` 与本机版完全一致

---

## 📦 本地运行

```bash
pip install streamlit plotly
streamlit run app.py
```

---

## ⚠️ 宪法声明

本系统遵循 **河与岸分形系统宪法 (CONSTITUTION.md)**：

- 日线⊃30min⊃5min 三级嵌套包络投射
- 包络函数 `envelope_at()` 是统一核心（`fractal_core.py`）
- 不做预测，只做投射
- 交易信号基于河岸钓鱼模型

---

## 📄 许可证

MIT
