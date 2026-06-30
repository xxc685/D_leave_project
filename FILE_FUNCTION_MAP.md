# 文件功能说明 —— 扫码签到系统

> **版本**：v2.0 | **更新日期**：2026-06-23
> **适用对象**：新加入团队成员、接手开发者

---

## 一、项目目录总览

```
D:\数据库pj/
├── app.js / app.json / app.wxss     ← 小程序入口 & 全局配置
├── project.config.json              ← 微信开发者工具配置
├── sitemap.json                     ← 站点地图（SEO）
├── ER.jpg                           ← 数据库 ER 图
├── claude_prompt.md                 ← AI 开发提示词记录
│
├── utils/                           ← 工具库
│   ├── config.js                    ← API 地址配置
│   ├── qrcode.js                    ← 轻量纯 JS 二维码生成器
│   └── util.js                      ← 微信默认工具（时间格式化）
│
├── pages/                           ← 小程序页面
│   ├── login/login                  ← 登录页（首页面）
│   ├── home/home                    ← 首页工作台（Tab 1）
│   ├── mine/mine                    ← 我的（Tab 2）
│   ├── teacher/teacher              ← 教师管理（发起签到）
│   ├── student/student              ← 学生签到助手
│   ├── stats/stats                  ← 出勤统计看板
│   ├── index/index                  ← [旧] 原双按钮首页（已弃用）
│   ├── logs/logs                    ← [旧] 微信默认示例
│   ├── FDU_logo.png                 ← 学校 Logo
│   └── images/                      ← TabBar 图标
│
├── admin_web/                       ← Web 管理端
│   └── index.html                   ← 单文件 SPA（Vue 3 + Element Plus）
│
└── code/                            ← 后端服务 & 数据分析
    ├── app.py                       ← 核心业务后端（Flask :5000）
    ├── db.py                        ← MySQL 连接配置
    ├── 查询功能.py                    ← 统计查询服务（Flask :8080）
    ├── app_backup.py                ← [旧] app.py 早期备份
    ├── 查询单个学生.sql               ← SQL 参考脚本
    ├── 教学班整体出勤率.sql            ← SQL 参考脚本
    ├── 按全院系统计出勤率.sql          ← SQL 参考脚本
    └── 缺勤次数最多前 10 名学生.sql    ← SQL 参考脚本
```

---

## 二、核心文件功能详表

### 2.1 全局入口文件

| 文件 | 功能 | 关键内容 |
|---|---|---|
| `app.json` | 小程序全局配置 | pages 注册列表、window 样式、tabBar 定义（首页/我的）、定位权限声明 |
| `app.js` | 小程序生命周期入口 | onLaunch：初始化日志缓存、wx.login 获取 openId |
| `app.wxss` | 全局样式 | 仅含 `.container` 基础样式（各页面自行覆盖） |
| `project.config.json` | 开发者工具配置 | appid: `wxa536117e48c3ba20`、ES6 转译、增强编译等 |

### 2.2 工具库 (utils/)

| 文件 | 功能 | 导出 |
|---|---|---|
| `config.js` | 后端 API 基地址配置 | `{ API_BASE: 'http://127.0.0.1:5000' }` |
| `qrcode.js` | 纯 JS 二维码编码器（520+ 行） | `encode(text)` → 矩阵数据、`drawToCanvas(ctx, text, size)` → Canvas 2D 绘制 |
| `util.js` | 时间格式化工具 | `formatTime(date)` → `"YYYY/MM/DD HH:mm:ss"` |

### 2.3 小程序页面

#### 2.3.1 登录页 (pages/login/login)

| 文件 | 业务逻辑 |
|---|---|
| `login.wxml` | Logo（140rpx）+ 标题 + 身份切换分段器（学生绿/教师蓝）+ 学号/工号 + 姓名输入 + 渐变登录按钮 |
| `login.js` | `switchRole` 切换身份；`handleLogin` 校验空值 → `wx.setStorageSync('role'/'id'/'name')` → `wx.switchTab('/pages/home/home')` |
| `login.wxss` | 全屏渐变背景、圆角胶囊 Tab 条、渐变按钮阴影 |
| `login.json` | 导航栏标题："课堂扫码签到" |

#### 2.3.2 首页工作台 (pages/home/home)

| 文件 | 业务逻辑 |
|---|---|
| `home.wxml` | 问候语 + 学生绿色大卡片「📷 扫一扫签到」/ 教师蓝色大卡片「📋 发起签到」+ 未登录提示 |
| `home.js` | `onShow` 读 Storage 生成问候语；`handleScan` 扫码→定位→校验场次→POST sign_in→弹窗引导查看记录；`handleTeacherAction` navigateTo teacher 页 |
| `home.wxss` | 全屏渐变背景、大卡片 28rpx 圆角 + 16rpx 阴影、hover 缩放动画 |
| `home.json` | 导航栏标题："首页"（TabBar 页） |

#### 2.3.3 我的 (pages/mine/mine)

| 文件 | 业务逻辑 |
|---|---|
| `mine.wxml` | 头像（取姓名字首）+ 姓名 + 角色标签 + ID；菜单：动态历史入口 + 出勤统计看板；退出登录按钮 |
| `mine.js` | `onShow` 读 Storage 生成 roleLabel 和 menuLabel；`goToHistory` 按角色跳转 student/teacher 页；`goToStats` 跳转 stats 页；`handleLogout` 二次确认 → clearStorage → reLaunch 登录页 |
| `mine.wxss` | 白色圆角卡片 + 蓝色渐变头像 + 线框退出按钮 |
| `mine.json` | 导航栏标题："我的"（TabBar 页） |

#### 2.3.4 教师管理 (pages/teacher/teacher)

| 文件 | 业务逻辑 |
|---|---|
| `teacher.wxml` | 教师信息条 + 班级选择器 + 有效时长 + 定位开关/半径 + 发起按钮 + Canvas 二维码 + 保存相册按钮 + 结束签到 + 历史场次列表 |
| `teacher.js` | `onLoad` 从 Storage 读 id/name → 加载班级列表和历史；`generateQRCode` POST /api/sessions → 生成 QR → drawQRCode → Canvas 绘制；`saveQRCode` canvasToTempFilePath + saveImageToPhotosAlbum + 权限处理；`finalizeSession` POST /api/sessions/../finalize + 缺勤补录；`viewHistorySession` 回载历史场次口令 |
| `teacher.wxss` | 卡片式表单布局、二维码带蓝框装饰、红色结束按钮 |
| `teacher.json` | 导航栏标题："教师端" |

#### 2.3.5 学生签到助手 (pages/student/student)

| 文件 | 业务逻辑 |
|---|---|
| `student.wxml` | 学生信息条 + 扫码按钮 + 签到状态展示区 + 签到历史列表 |
| `student.js` | `onLoad` 从 Storage 读 id/name → 自动加载签到历史；`handleScan` → `fetchLocationAndSignIn` → `processCheckIn`（三级链路同 home.js）；`loadHistory` GET /api/students/<id>/records；`onRefreshHistory` 手动刷新 |
| `student.wxss` | 卡片布局、状态标签颜色（绿/黄/红/灰） |
| `student.json` | 导航栏标题："学生签到" |

#### 2.3.6 出勤统计看板 (pages/stats/stats)

| 文件 | 业务逻辑 |
|---|---|
| `stats.wxml` | 顶栏标题 + CSS 柱状图（6 根彩色柱子+数值+课程标签）+ 汇总卡片（平均出勤率/课程数）+ 底部开发者提示 |
| `stats.js` | `onLoad` 读 Storage → 展示 Demo 静态数据 `chartData[]`；预留 `wx.request` 接口调用注释供 D 同学接入 |
| `stats.wxss` | 白色圆角卡片 + 柱状图 flexbox 底部对齐 + 彩色渐变圆角柱体 + 过渡动画 |
| `stats.json` | 导航栏标题："出勤统计看板" |

#### 2.3.7 已弃用页面

| 页面 | 状态 | 说明 |
|---|---|---|
| `pages/index/index` | 未删除 | 原双按钮首页（教师入口/学生入口），已由 login 页替代。仍注册于 app.json 但不在路由中使用 |
| `pages/logs/logs` | 未删除 | 微信小程序默认启动模板示例页 |

### 2.4 Web 管理端

| 文件 | 技术栈 | 功能模块 |
|---|---|---|
| `admin_web/index.html` | Vue 3 + Element Plus + Axios（全部 CDN 引入） | **学生管理**：CRUD + CSV 批量导入/导出；**教学班管理**：CRUD；**签到数据管理**：按学号/状态筛选 + 表格 + 修改状态 + CSV 导出；**出勤大数据分析**：占位容器（D 同学填充） |

### 2.5 后端服务

#### 2.5.1 核心业务后端 (code/app.py)

| 路由 | 方法 | 功能 | 关键细节 |
|---|---|---|---|
| `/api/sessions` | POST | 创建签到场次 | 校验教学班存在 → 生成 UUID token → INSERT session |
| `/api/sign_in` | POST | 学生扫码签到 | **行锁防并发**：SELECT FOR UPDATE → 校验 token/场次状态/学生存在/选课/未重复签到 → Haversine 定位计算 → 时间窗口判定 → INSERT record |
| `/api/sessions/<id>/finalize` | POST | 结束签到 | 查未签到学生 → 逐条 INSERT absent 记录 → 更新 session_status=closed |
| `/api/records/<id>` | PATCH | 教师修正记录 | 支持 status/valid/remark 部分更新，自动推断 is_valid |
| `/api/sessions/by_token/<token>` | GET | 二维码反查 | 3 表 JOIN 返回场次+课程信息 |
| `/api/admin/attendance_records` | GET | 管理端查询 | 4 表 JOIN + 动态筛选 + 服务端计算签到距离 |
| `/api/students/<id>/records` | GET | 学生历史 | 4 表 JOIN，按 scan_time 倒序 |
| `/api/students` | GET/POST | 学生管理 | 列表 + 新增 |
| `/api/students/<id>` | PUT/DELETE | 学生编辑/删除 | 部分字段更新 |
| `/api/students/import` | POST | CSV 导入 | multipart/form-data 接收，ON DUPLICATE KEY UPDATE |
| `/api/students/export` | GET | CSV 导出 | Content-Disposition: attachment |
| `/api/teacher/<id>/classes` | GET | 教师课程 | JOIN course 表 |
| `/api/teacher/<id>/sessions` | GET | 教师历史 | JOIN teaching_class + course |
| `/api/teaching_classes` | GET/POST | 教学班 CRUD | |
| `/api/teaching_classes/<id>` | PUT/DELETE | 教学班编辑/删除 | |

**关键机制**：
- **CORS**：全局 `Access-Control-Allow-Origin: *`
- **事务管理**：签到使用 `conn.begin()` + `FOR UPDATE` 行锁防并发重复签到
- **Haversine 公式**：精确计算地表两点距离（米），用于定位校验
- **时间窗口判定**：`scan_time < start_time → invalid` / `start_time ~ valid_deadline → present` / `~ end_time → late` / `> end_time → invalid`

#### 2.5.2 统计查询服务 (code/查询功能.py)

| 路由 | 方法 | 功能 | 端口 |
|---|---|---|---|
| `/` | GET | 服务首页 + 接口文档 | 8080 |
| `/api/statistics/student/<id>` | GET | 单个学生出勤统计（total/present/late/absent/rate） | 8080 |
| `/api/statistics/class/<id>` | GET | 教学班出勤统计（总人数/已签到/缺勤/出勤率） | 8080 |
| `/api/statistics/department` | GET | 按院系分组出勤率 | 8080 |
| `/api/statistics/absent_top10` | GET | 缺勤次数最多的前 10 名学生 | 8080 |

#### 2.5.3 数据库连接 (code/db.py)

```python
# 核心业务后端使用
host="localhost", user="root", password="hjj20060629", database="attendance_system"
```

```python
# 统计服务使用 (code/查询功能.py 内联)
host="localhost", user="root", password="curry20090730", database="attendance_system"
```

> ⚠️ 两个密码不同，需确认 `curry20090730` 对 `attendance_system` 库有读权限。

### 2.6 SQL 参考脚本 (code/*.sql)

| 文件 | 功能 | 核心 SQL |
|---|---|---|
| `查询单个学生.sql` | 按学号统计出勤 | `SUM(CASE WHEN status IN ('present','late') THEN 1 ELSE 0 END) / COUNT(*) * 100` |
| `教学班整体出勤率.sql` | 按班级统计签到覆盖率 | `COUNT(DISTINCT ar.student_id) / COUNT(DISTINCT e.student_id) * 100` |
| `按全院系统计出勤率.sql` | 按院系分组平均出勤率 | `AVG(CASE WHEN status IN ('present','late') THEN 1 ELSE 0 END) * 100` |
| `缺勤次数最多前 10 名学生.sql` | TOP10 缺勤榜 | `WHERE attendance_status='absent' GROUP BY student_id ORDER BY COUNT DESC LIMIT 10` |

---

## 三、数据流向图

```
┌─ 小程序端 ─────────────────────────────────────────────┐
│                                                         │
│  login ──Storage──▶ home ──navigateTo──▶ teacher        │
│    │                   │                    │           │
│    │              scanCode+sign_in    POST /api/sessions │
│    │                   │                    │           │
│    │                   ▼                    ▼           │
│    │              student              Canvas 二维码     │
│    │                   │                    │           │
│    └──── TabBar ──▶ mine ──navigateTo──▶ stats          │
│                   goToHistory          (D 同学填充)      │
│                   goToStats                              │
│                                                         │
└────────────────────┬────────────────────────────────────┘
                     │ wx.request
                     ▼
┌─ 后端 API (:5000) ─────────────────────────────────────┐
│  app.py ← db.py ← MySQL (attendance_system)             │
│  签到 / 查记录 / 学生 CRUD / 教学班 CRUD / 发起/结束     │
└─────────────────────────────────────────────────────────┘

┌─ 统计 API (:8080) ─────────────────────────────────────┐
│  查询功能.py → MySQL (attendance_system)                 │
│  学生统计 / 班级统计 / 院系统计 / 缺勤 TOP10             │
└─────────────────────────────────────────────────────────┘

┌─ Web 管理端 ───────────────────────────────────────────┐
│  admin_web/index.html (Vue 3 + Element Plus)            │
│  → axios → :5000 API → 学生/班级/签到/统计管理          │
└─────────────────────────────────────────────────────────┘
```

---

## 四、字段/状态值约定

| 字段 | 可选值 | 说明 |
|---|---|---|
| `role` (Storage) | `student` / `teacher` | 用户身份 |
| `attendance_status` | `present` / `late` / `absent` / `invalid` | 考勤状态 |
| `is_valid` | `valid` / `invalid` | 签到是否有效 |
| `session_status` | `ongoing` / `closed` | 场次是否开放 |
| `enroll_status` | `enrolled` / `dropped` | 选课状态 |
