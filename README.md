# 课堂扫码签到与请假管理系统

本项目是一套数据库课程设计系统，由微信小程序、PC 管理端、Flask 后端和 MySQL 数据库组成，覆盖课堂签到、定位校验、缺勤补录、学生请假、教师审批、考勤修正和多维统计。

## GitHub 仓库

- 仓库地址：https://github.com/xxc685/D_leave_project
- 提交要求：仓库 Visibility 必须为 **Public**，并确保未登录浏览器也能打开仓库和本 README。

## 目录说明

| 路径 | 作用 |
| --- | --- |
| `pages/`、`app.*`、`utils/` | 微信小程序 |
| `code/app.py` | 5000 端口核心业务入口 |
| `code/leave_api.py` | 请假接口模块，由 `app.py` 自动注册 |
| `code/management_api.py` | 教师、课程和名单管理模块，由 `app.py` 自动注册 |
| `code/query.py` | 8080 端口统计服务入口 |
| `admin_web/index.html` | PC 管理端 |
| `attendance_system.sql` | 全量建库建表脚本 |
| `demo_data.sql` | 答辩基础数据 |
| `code/demo_simulate.py` | 历史考勤模拟脚本 |
| `output/pdf/` | 期末提交 PDF 报告 |

## 环境要求

- Windows 10/11
- MySQL 8.x
- Python 3.9 或更高版本
- 微信开发者工具稳定版
- Chrome 或 Edge；推荐安装 VS Code Live Server

## 安装与数据库初始化

1. 在 MySQL Workbench 中执行 `attendance_system.sql`。
2. 需要答辩演示数据时，再执行 `demo_data.sql`。
3. 打开 `code/db.py`，把数据库密码修改为本机 MySQL 密码。
4. 安装 Python 依赖：

```powershell
python -m pip install flask flask-cors pymysql
```

已有旧数据库只补请假表时可执行 `leave_feature.sql`；全新安装已经由 `attendance_system.sql` 包含请假功能，无需重复执行。SQL 只在初始化或重置数据时运行，不需要每次启动都执行。

## 运行系统

终端 1 启动核心业务服务：

```powershell
cd code
python app.py
```

终端 2 启动统计服务：

```powershell
cd code
python query.py
```

正常情况下：

- 核心业务 API：`http://127.0.0.1:5000`
- 统计 API：`http://127.0.0.1:8080`
- `management_api.py` 和 `leave_api.py` 是被 `app.py` 导入的模块，不能也不需要单独运行。

## 打开微信小程序

1. 打开微信开发者工具并扫码登录。
2. 点击“导入项目”，目录选择本仓库根目录。
3. 在“详情 - 本地设置”中勾选“不校验合法域名”，仅用于本地调试。
4. 点击“编译”。
5. 模拟器可使用 `127.0.0.1`；真机调试需把 `utils/config.js` 中地址改为电脑局域网 IP，并确保手机与电脑在同一网络。

## 打开 PC 管理端

使用 VS Code Live Server 打开 `admin_web/index.html`。管理端会访问 5000 和 8080 端口，因此两个后端服务都应保持运行。

## 使用说明

### 学生端

1. 选择学生身份并使用数据库中的学号登录。
2. 点击“扫一扫签到”，扫描教师二维码并允许定位。
3. 在签到历史中查看正常、迟到、缺勤、无效和请假状态。
4. 在请假页面选择场次、填写原因并提交，刷新后查看审批结果。
5. 在统计页面查看个人出勤率和考勤明细。

### 教师端

1. 使用教师工号登录，选择本人教学班。
2. 设置有效时长和定位半径，创建签到并展示二维码。
3. 查看学生签到记录和历史场次。
4. 在请假审批中批准或驳回申请。
5. 到结束时间后关闭场次，系统自动为未签到且未获批请假的学生补录缺勤。

### PC 管理端

可维护教师、课程、学生和教学班名单，筛选或修正考勤记录，并查看个人、班级、院系、教师、时间趋势和异常预警统计。

## 测试说明

### 1. 基础检查

```powershell
python -m compileall code
```

后端启动后，在浏览器访问以下地址，确认返回 JSON：

- `http://127.0.0.1:5000/api/students`
- `http://127.0.0.1:5000/api/teachers`
- `http://127.0.0.1:5000/api/courses`
- `http://127.0.0.1:8080/api/statistics/department`

### 2. 核心功能验证

1. 教师 T001 创建签到场次并显示二维码。
2. 学生 2024001 扫码，验证生成正常或迟到记录。
3. 同一学生再次扫码，验证系统拒绝重复有效签到。
4. 学生 2024030 提交请假，教师 T001 批准。
5. 验证请假申请变为 `approved`，考勤状态变为 `leave`。
6. 教师关闭场次，验证其他未签到学生自动生成 `absent`。
7. 打开统计看板，验证请假不计缺勤且从应到分母中排除。

### 3. 答辩数据

```powershell
cd code
python demo_simulate.py
```

`demo_data.sql + code/demo_simulate.py` 是项目保留的演示数据方案。

> `demo_simulate.py` 会清空请假申请、考勤记录和签到场次，只能在演示数据库执行，真实数据必须先备份。

## 演示账号

| 角色 | ID | 姓名 |
| --- | --- | --- |
| 教师 | T001 | 张三 |
| 正常签到学生 | 2024001 | 陈志远 |
| 请假学生 | 2024030 | 邱思敏 |

## 发布到 GitHub

1. 在 GitHub 新建空仓库，并把 Visibility 设为 Public。
2. 在本项目目录执行：

```powershell
git init
git add .
git commit -m "Complete attendance and leave management system"
$REPO_URL = Read-Host "粘贴刚创建的 GitHub 仓库地址"
git branch -M main
git remote add origin $REPO_URL
git push -u origin main
```

3. 使用未登录的浏览器打开仓库，确认代码和 README 可见。
4. 将实际仓库 URL 写入期末 PDF 报告后再提交。
