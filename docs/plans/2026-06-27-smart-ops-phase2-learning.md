# SmartOps Phase 2 — 学习路线：Web 面板

> **目标：** 用 HTML + CSS + JavaScript + Chart.js 做一个运维面板，展示服务器状态和指标趋势。不改 Phase 1 的 API 代码，只加新接口。

---

## 总览：学完这个阶段你会什么

| 概念 | 学到什么 |
|------|---------|
| GET 路由 | API 不止收数据，还要给数据 |
| HTML | 页面结构、布局 |
| CSS | Flexbox、颜色、深色模式 |
| JavaScript fetch | 从 API 拿 JSON 数据 |
| Chart.js | 画折线图、实时更新 |

**技术前提：** Phase 1 的 API 能跑通，PostgreSQL 里有数据。

---

## 学习阶段 1：给 API 加 GET 路由

**目标：** 前端需要数据，API 要有"读数据"的接口。

现在你的 API 只有 POST 路由（收数据），前端要展示数据就必须有 GET 路由。

### 1.1 查最新一条指标的路由

在 `api.py` 加：

```python
@app.route("/api/servers")
def list_servers():
    """返回所有服务器的最新状态"""
    session = get_session()
    servers = session.query(Server).all()
    data = []
    for s in servers:
        # 查每台服务器最新一条指标
        metric = session.query(Metric).filter_by(
            server_id=s.id
        ).order_by(Metric.id.desc()).first()
        
        data.append({
            "name": s.name,
            "ip": s.ip,
            "os": s.os,
            "status": s.status,
            "last_heartbeat": str(s.last_heartbeat)[:19] if s.last_heartbeat else None,
            "cpu": metric.cpu if metric else None,
            "memory": metric.memory if metric else None,
            "disk": metric.disk if metric else None,
        })
    session.close()
    return jsonify(data)
```

**提示：** `str(...)[:19]` 是把时间截成 `"2026-06-27 10:30:00"` 格式，前端好显示。

**验收：** 浏览器打开 `http://127.0.0.1:5001/api/servers`，能看到 JSON：

```json
[
  {
    "name": "test-vps",
    "ip": "127.0.0.1",
    "os": "Ubuntu 22.04",
    "status": "online",
    "last_heartbeat": "2026-06-27 10:30:00",
    "cpu": 12.5,
    "memory": 65.3,
    "disk": 41.8
  }
]
```

### 1.2 查历史趋势的路由

加另一个路由，给 Chart.js 提供数据：

```python
@app.route("/api/servers/<name>/history")
def server_history(name):
    """返回某台服务器最近的指标趋势"""
    session = get_session()
    server = session.query(Server).filter_by(name=name).first()
    if not server:
        session.close()
        return jsonify({"error": "server not found"}), 404

    # 查最近 60 条
    metrics = session.query(Metric).filter_by(
        server_id=server.id
    ).order_by(Metric.id.desc()).limit(60).all()
    session.close()

    data = []
    for m in reversed(metrics):  # 反转为按时间升序
        data.append({
            "time": str(m.created_at)[:16],
            "cpu": m.cpu,
            "memory": m.memory,
            "disk": m.disk,
        })
    return jsonify(data)
```

`<name>` 是 URL 参数，Flask 自动捕获。访问 `http://127.0.0.1:5001/api/servers/test-vps/history` 就能拿到这台服务器的数据。

**验收：** 能看到一个 JSON 数组，每条包含 time/cpu/memory/disk。

---

## 学习阶段 2：HTML 页面骨架

**目标：** 写一个 HTML 页面，有侧边栏和主内容区。

### 2.1 新建页面

创建 `templates/dashboard.html`。这是你的运维面板。

**提示：** 先把骨架搭出来，不要想美化。

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartOps</title>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h2>SmartOps</h2>
            <ul>
                <li>总览</li>
                <li>服务器</li>
                <li>趋势</li>
            </ul>
        </div>
        <div class="main">
            <h1>运维面板</h1>
            <div id="content">加载中...</div>
        </div>
    </div>
</body>
</html>
```

### 2.2 加路由渲染页面

```python
from flask import render_template

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")
```

现在访问 `http://127.0.0.1:5001/dashboard`。

### 2.3 CSS 做侧边栏布局

用 Flexbox 做两栏布局。

**提示：** 侧边栏固定宽度 250px，左侧深色背景，主区域白色。里面的 `ul` 去掉列表圆点。

```html
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, sans-serif; }

    .container { display: flex; min-height: 100vh; }

    .sidebar {
        width: 250px;
        background: #1a1a2e;
        color: white;
        padding: 20px;
    }

    .main { flex: 1; padding: 30px; background: #f5f5f5; }

    .sidebar ul { list-style: none; margin-top: 20px; }
    .sidebar li {
        padding: 10px 15px;
        margin: 5px 0;
        border-radius: 8px;
        cursor: pointer;
    }
    .sidebar li:hover { background: #16213e; }
    .sidebar li.active { background: #0f3460; }
</style>
```

**验收：** 页面左边一个深色侧边栏，右边白色内容区。

---

## 学习阶段 3：JavaScript 拿 API 数据

**目标：** 页面打开时自动从 API 拿数据，显示在页面上。

### 3.1 加到 HTML 页面

```html
<script>
async function loadServers() {
    const resp = await fetch("/api/servers");
    const servers = await resp.json();
    // servers 就是 JSON 数组
}
</script>
```

**提示：** `fetch()` 返回一个 Promise，`await` 等它完成。`.json()` 把响应体解析成 JSON。

### 3.2 把服务器展示成卡片

用 JS 动态生成卡片 HTML：

```javascript
async function loadServers() {
    const resp = await fetch("/api/servers");
    const servers = await resp.json();

    const html = servers.map(s => `
        <div class="server-card">
            <h3>${s.name}</h3>
            <p>IP: ${s.ip}</p>
            <p>系统: ${s.os}</p>
            <p>状态: ${s.status === 'online' ? '🟢 在线' : '🔴 失联'}</p>
            <p>CPU: ${s.cpu ?? '-'}%</p>
            <p>内存: ${s.memory ?? '-'}%</p>
            <p>磁盘: ${s.disk ?? '-'}%</p>
        </div>
    `).join("");

    document.getElementById("content").innerHTML = html;
}

// 页面加载完执行
loadServers();
```

**`??`** 是空值合并运算符。如果 `s.cpu` 是 `null` 或 `undefined`，显示 `-`。不会显示 0（因为 CPU 可能是真的 0%）。

### 3.3 给卡片加点 CSS

```css
.server-card {
    background: white;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 15px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.server-card h3 { margin-bottom: 10px; color: #1a1a2e; }
.server-card p { margin: 5px 0; color: #555; font-size: 14px; }
```

**验收：** 刷新页面，能看到服务器卡片列表，每张卡片显示 name、IP、CPU 等。

---

## 学习阶段 4：Chart.js 趋势图

**目标：** 点服务器卡片，弹出一个折线图展示趋势。

### 4.1 引入 Chart.js

在 HTML 的 `<head>` 里加：

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
```

### 4.2 在页面加一个画图区域

```html
<div class="main">
    <h1>运维面板</h1>
    <div id="content">加载中...</div>
    <div id="chart-area" style="display:none; margin-top: 30px;">
        <h2 id="chart-title"></h2>
        <canvas id="chart" height="300"></canvas>
    </div>
</div>
```

### 4.3 写一个加载趋势的函数

```javascript
let chart = null;

async function showTrend(serverName) {
    const resp = await fetch(`/api/servers/${serverName}/history`);
    const data = await resp.json();

    document.getElementById("chart-area").style.display = "block";
    document.getElementById("chart-title").textContent = `${serverName} - 趋势`;

    // Chart.js 需要的格式
    const labels = data.map(d => d.time);
    const cpuData = data.map(d => d.cpu);
    const memData = data.map(d => d.memory);

    if (chart) chart.destroy(); // 每次重建之前销毁旧的

    chart = new Chart(document.getElementById("chart"), {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                { label: "CPU %", data: cpuData, borderColor: "#e74c3c", fill: false },
                { label: "内存 %", data: memData, borderColor: "#3498db", fill: false }
            ]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: "top" } }
        }
    });
}
```

### 4.4 把卡片点成可点击的

改一下卡片生成代码，加个点击事件：

```javascript
const html = servers.map(s => `
    <div class="server-card" onclick="showTrend('${s.name}')">
        <h3>${s.name}</h3>
        ...
    </div>
`).join("");
```

**验收：** 点一张卡片，下面出现折线图，显示 CPU 和内存的趋势。

---

## 学习阶段 5：总览页 + 美化

### 5.1 总览页展示什么

页面最上面加汇总信息：

```javascript
// 计算状态统计
const online = servers.filter(s => s.status === 'online').length;
const offline = servers.filter(s => s.status !== 'online').length;

const summaryHTML = `
    <div class="summary">
        <div class="stat">🟢 在线: ${online}</div>
        <div class="stat">🔴 失联: ${offline}</div>
        <div class="stat">📊 服务器总数: ${servers.length}</div>
    </div>
`;
```

### 5.2 侧边栏菜单切换

用 `onclick` 切换不同视图：

```html
<li onclick="showPage('overview')">总览</li>
<li onclick="showPage('servers')">服务器</li>
<script>
function showPage(page) {
    if (page === 'overview') loadOverview();
    if (page === 'servers') loadServers();
}
</script>
```

### 5.3 深色模式（可选）

加个按钮，用 CSS 变量切换：

```css
:root { --bg: #f5f5f5; --card-bg: white; --text: #333; }
[data-theme="dark"] { --bg: #1a1a2e; --card-bg: #16213e; --text: #eee; }
```

```javascript
function toggleTheme() {
    document.documentElement.dataset.theme = 
        document.documentElement.dataset.theme === "dark" ? "light" : "dark";
}
```

---

## 总结

学完 Phase 2 后你掌握了：

1. ✅ **GET 路由** — 从 API 读数据给前端
2. ✅ **HTML 布局** — 侧边栏 + 主内容区
3. ✅ **CSS Flexbox** — 两栏布局、卡片
4. ✅ **JavaScript fetch** — 从后端拿 JSON
5. ✅ **Chart.js** — 画折线图

**Phase 3 学什么：** LLM 对话、LangChain 工具调用、RAG 日志检索。
