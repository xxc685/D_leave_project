"""
答辩演示 - 签到历史数据模拟脚本
=================================
用途：为两个教学班生成 5 周的历史签到场次和考勤记录，
      使后台统计看板展示丰富的图表数据。

使用方法：
  cd code
  python demo_simulate.py

前置条件：已执行 demo_data.sql 导入基础数据。
效果：生成 CL001(程序设计) 和 CL002(数据库原理) 各 5 次历史场次，
      涵盖 present / late / absent / invalid / leave 五种状态。
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import get_conn
from datetime import date, datetime, timedelta
import uuid, random

random.seed(42)  # 固定随机种子，每次运行结果一致

# ============================
# 配置
# ============================
WEEKS = 5  # 模拟最近 5 周的签到

CLASSES = [
    {
        "class_id": "CL001",
        "course_name": "程序设计",
        "students": [f"2025{str(i).zfill(3)}" for i in range(1, 21)],  # 2025001-2025020
        "location_lat": 30.5285,
        "location_lon": 114.3650,
        "radius": 200,
        "valid_minutes": 10,
    },
    {
        "class_id": "CL002",
        "course_name": "数据库原理",
        "students": [f"2024{str(i).zfill(3)}" for i in range(1, 31)],  # 2024001-2024030
        "location_lat": 30.5290,
        "location_lon": 114.3640,
        "radius": 200,
        "valid_minutes": 15,
    },
]

# 学生行为画像 - 决定每个人在每场签到中的表现
# pattern 取值及概率:
#   "good"     : 90% present,   5% late,   3% absent,  2% leave
#   "normal"   : 65% present,  15% late,  15% absent,  5% leave
#   "late_bird": 30% present,  50% late,  15% absent,  5% leave
#   "bad"      : 20% present,  10% late,  60% absent, 10% leave

STUDENT_PATTERNS = {}

# CL001 - 程序设计 (20人，软件学院)
for i in range(1, 21):
    sid = f"2025{str(i).zfill(3)}"
    if i <= 3:
        STUDENT_PATTERNS[sid] = "good"
    elif i <= 10:
        STUDENT_PATTERNS[sid] = "normal"
    elif i <= 16:
        STUDENT_PATTERNS[sid] = "late_bird"
    else:
        STUDENT_PATTERNS[sid] = "bad"

# CL002 - 数据库原理 (30人)
for i in range(1, 31):
    sid = f"2024{str(i).zfill(3)}"
    if i <= 5:
        STUDENT_PATTERNS[sid] = "good"       # 2024001-2024005 好学生
    elif i <= 18:
        STUDENT_PATTERNS[sid] = "normal"     # 2024006-2024018 普通
    elif i <= 24:
        STUDENT_PATTERNS[sid] = "late_bird"  # 2024019-2024024 迟到王
    else:
        STUDENT_PATTERNS[sid] = "bad"        # 2024025-2024030 缺勤王


def pick_status(pattern: str):
    """根据行为画像随机生成签到状态"""
    r = random.random()
    if pattern == "good":
        if r < 0.90: return "present"
        if r < 0.95: return "late"
        if r < 0.98: return "absent"
        return "leave"
    elif pattern == "late_bird":
        if r < 0.30: return "present"
        if r < 0.80: return "late"
        if r < 0.95: return "absent"
        return "leave"
    elif pattern == "bad":
        if r < 0.20: return "present"
        if r < 0.30: return "late"
        if r < 0.90: return "absent"
        return "leave"
    else:  # normal
        if r < 0.65: return "present"
        if r < 0.80: return "late"
        if r < 0.95: return "absent"
        return "leave"


def main():
    conn = get_conn()
    cursor = conn.cursor()

    # 清空旧的模拟数据（只清考勤记录、签到场次、请假申请）
    print("清理旧模拟数据...")
    cursor.execute("DELETE FROM leave_request")
    cursor.execute("DELETE FROM attendance_record")
    cursor.execute("DELETE FROM attendance_session")
    conn.commit()
    print("旧数据已清除。\n")

    total_sessions = 0
    total_records = 0
    total_leaves = 0

    today = date.today()

    for cls in CLASSES:
        class_id = cls["class_id"]
        students = cls["students"]
        print(f"===== {cls['course_name']} ({class_id}) =====")

        for week in range(WEEKS, 0, -1):
            # 场次日期: 每周一上午 8:00-9:30
            days_ago = (week - 1) * 7
            session_date = today - timedelta(days=days_ago)
            # 调整到最近的周一
            monday_offset = session_date.weekday()  # 0=Monday
            session_date = session_date - timedelta(days=monday_offset)

            start_time = datetime.combine(session_date, datetime.strptime("08:00:00", "%H:%M:%S").time())
            end_time   = datetime.combine(session_date, datetime.strptime("09:30:00", "%H:%M:%S").time())
            qr_token   = uuid.uuid4().hex

            cursor.execute("""
                INSERT INTO attendance_session
                (class_id, session_date, start_time, end_time, qr_token, valid_minutes,
                 location_latitude, location_longitude, location_radius, session_status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'closed')
            """, (
                class_id, session_date, start_time, end_time, qr_token,
                cls["valid_minutes"],
                cls["location_lat"], cls["location_lon"], cls["radius"]
            ))
            session_id = cursor.lastrowid
            total_sessions += 1

            present_cnt = late_cnt = absent_cnt = leave_cnt = invalid_cnt = 0

            for sid in students:
                pattern = STUDENT_PATTERNS.get(sid, "normal")
                status = pick_status(pattern)

                # 判断 is_valid
                if status in ("absent", "invalid"):
                    is_valid = "invalid"
                else:
                    is_valid = "valid"

                # 扫码时间
                if status == "present":
                    # 正常签到：开始后 0~valid_minutes 内
                    offset_min = random.randint(1, cls["valid_minutes"])
                    scan_time = start_time + timedelta(minutes=offset_min)
                elif status == "late":
                    # 迟到：valid_minutes ~ end_time 之间
                    total_min = int((end_time - start_time).total_seconds() / 60)
                    offset_min = random.randint(cls["valid_minutes"] + 1, total_min - 1)
                    scan_time = start_time + timedelta(minutes=offset_min)
                elif status == "absent":
                    # 缺勤：用场次结束时间作为补录时间
                    scan_time = end_time + timedelta(minutes=5)
                else:
                    # leave：同 absent，但后续会改成请假
                    scan_time = end_time + timedelta(minutes=5)

                # 经纬度（在场次中心附近随机偏移）
                lat = cls["location_lat"] + random.uniform(-0.001, 0.001)
                lon = cls["location_lon"] + random.uniform(-0.001, 0.001)

                # 备注 & 最终状态
                remark = None
                final_status = status
                if status == "absent":
                    remark = "未签到,系统补录"
                elif status == "late":
                    remark = "迟到"
                elif status == "leave":
                    # 模拟请假已批准的记录：直接写入 leave 状态
                    remark = "请假已批准：" + random.choice(
                        ["身体不适", "家中有事", "参加竞赛", "实习面试"])
                elif status == "present":
                    pass  # remark 为 None

                cursor.execute("""
                    INSERT INTO attendance_record
                    (session_id, student_id, scan_time, attendance_status,
                     latitude, longitude, is_valid, remark)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (session_id, sid, scan_time, final_status, lat, lon, is_valid, remark))
                total_records += 1

                if status == "present":
                    present_cnt += 1
                elif status == "late":
                    late_cnt += 1
                elif status == "absent":
                    absent_cnt += 1
                elif status == "leave":
                    leave_cnt += 1
                    # 同时创建已批准的请假申请记录
                    cursor.execute("""
                        INSERT INTO leave_request
                        (student_id, session_id, class_id, reason, status,
                         submit_time, review_time, reviewer_id, review_remark)
                        VALUES (%s,%s,%s,%s,'approved',%s,%s,'T001','同意请假')
                    """, (sid, session_id, class_id,
                          remark.replace("请假已批准：", ""),
                          scan_time - timedelta(days=1),
                          scan_time - timedelta(hours=12)))
                    total_leaves += 1

            print(f"  第{6-week}周 {session_date} | "
                  f"出勤{present_cnt} 迟到{late_cnt} 缺勤{absent_cnt} 请假{leave_cnt}")

        print()

    conn.commit()
    cursor.close()
    conn.close()

    print("=" * 55)
    print(f"✅ 模拟完成！")
    print(f"   签到场次: {total_sessions} 次")
    print(f"   考勤记录: {total_records} 条")
    print(f"   请假申请: {total_leaves} 条")
    print(f"   CL001(程序设计) 5次 + CL002(数据库原理) 5次")
    print()
    print("⚠️  以上是历史数据，答辩时还需手动演示：")
    print("   1. 教师创建新的数据库原理二维码")
    print("   2. 学生2024001扫码签到(出勤)")
    print("   3. 学生2024030申请请假 → 教师审批")
    print("   4. 教师结束签到 → 未签到者自动补录缺勤")


if __name__ == "__main__":
    main()
