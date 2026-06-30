#  统计模块 — 本地运行与交接指南

整个系统由 **Flask 后端 × 2** + **PC 管理端** + **微信小程序** 四部分组成，统计相关的工作集中在后三步。

---

## 1. 数据库准备

### 1.1 创建数据库

打开本地 MySQL，执行：

```sql
CREATE DATABASE IF NOT EXISTS attendance_system
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;
```

> 如果项目附带 SQL 建表/导入脚本，请一并执行。

### 1.2 ⚠️ 改密码

代码里数据库密码位置目前是 **空字符串**，你需要改成自己电脑上 MySQL 的 `root` 密码。

涉及 **两个文件**：

| 文件 | 位置 | 说明 |
|------|------|------|
| `code/db.py` | 第 9 行 `password=""` | 被 `app.py` 引用（核心业务） |
| `code/查询功能.py` | 第 12 行 `password=""` | 统计模块专属服务 |

两处都长这样，把空字符串换成你的密码：

```python
"password": "",            # TODO: 改成你自己电脑的 MySQL root 密码
# 改成 ↓
"password": "你的MySQL密码",
```

---

## 2. 启动后端服务器（系统心脏）

> 统计模块依赖两个 Flask 服务同时运行。**打开两个终端窗口**，都 `cd` 到 `code/` 目录。

### 2.1 终端 ① — 核心业务服务（端口 5000）

```bash
cd code
python app.py
```

- 对外提供签到、学生管理、教学班管理等全部业务 API
- 监听 `http://0.0.0.0:5000`
- 终端看到 `Running on http://0.0.0.0:5000` 就说明起来了

### 2.2 终端 ② — 统计查询服务（端口 8080）⭐

```bash
cd code
python 查询功能.py
```

- 你主要负责维护的模块 🎯
- 监听 `http://0.0.0.0:8080`
- 启动后访问 `http://localhost:8080/` 会看到所有可用统计接口列表

**统计 API 速查表：**

| 接口 | 用途 |
|------|------|
| `/api/statistics/student/<学号>` | 单个学生出勤统计 |
| `/api/statistics/class/<班号>` | 教学班整体出勤率 |
| `/api/statistics/department` | 按院系统计出勤率 |
| `/api/statistics/gender` | 按性别统计出勤率 |
| `/api/statistics/absent_top10` | 缺勤次数 Top 10 |

### 依赖安装

如果 `import` 报错，先装依赖：

```bash
pip install flask pymysql flask-cors
```

---

## 3. 启动 PC 管理端

PC 管理端是一个纯前端 SPA（Vue 3 + Element Plus，CDN 引入），无需构建。

### 启动方式

1. 用 **VS Code** 打开项目根目录
2. 右键 `admin_web/index.html` → **"Open with Live Server"**
3. 浏览器会自动打开管理面板

### 统计图表渲染入口

打开 `admin_web/index.html`，搜索 `stats-container`，能看到下面所示的占位区域：

```html
<div id="stats-container">
  <div class="stats-placeholder">
    📊 出勤大数据分析
    此处由 D 同学完成统计图表渲染
    —— 预留数据接口 ——
    GET /api/admin/attendance_stats
  </div>
</div>
```

把占位内容替换成 **ECharts** 图表，调用 `http://localhost:8080` 上的统计接口获取数据。

> 💡 建议引入 ECharts CDN：
> ```html
> <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
> ```
> 然后在 Vue 的 `activeMenu === 'stats'` 条件下初始化图表实例并绑定到 `#stats-container`。

## 4. 启动微信小程序调试

### 4.1 打开项目

1. 启动 **微信开发者工具**
2. 选择 **导入项目**，目录选项目根目录
3. AppID 已在 `project.config.json` 中配置（`wxa536117e48c3ba20`）

### 4.2 运行

- 点击工具栏 **「编译」** 按钮能看到小程序的界面，通过这个界面来进行调试

---

## 🧩 架构速览

```
                    ┌──────────────────────┐
                    │   MySQL (localhost)   │
                    │  attendance_system    │
                    └──────┬───────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
     ┌───────▼───────┐        ┌────────▼────────┐
     │  app.py       │        │  查询功能.py      │
     │  :5000        │        │  :8080 ⭐        │
     │  核心业务 API  │        │  统计专属 API     │
     └───┬───┬───────┘        └──────┬───────────┘
         │   │                       │
    ┌────▼┐ ┌▼────────┐    ┌────────▼──────┐
    │小程序│ │admin_web│    │ PC 管理端       │
    │      │ │index.html│   │ (ECharts 图表) │
    └──────┘ └─────────┘    └───────────────┘
```

