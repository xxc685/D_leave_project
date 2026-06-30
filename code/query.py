from flask import Flask, jsonify, request
import pymysql
from flask_cors import CORS
from db import get_conn   # 使用统一的数据库连接
from datetime import datetime, date

app = Flask(__name__)
CORS(app)


# ==================== 首页 ====================
@app.route("/")
def index():
    return jsonify(code=200, msg="D模块统计接口运行成功", data={
        "学生统计": "/api/statistics/student/学号",
        "班级统计": "/api/statistics/class/班号",
        "院系统计": "/api/statistics/department",
        "缺勤TOP10": "/api/statistics/absent_top10",
        "教学班概览": "/api/statistics/class/<class_id>/overview",
        "教学班趋势": "/api/statistics/class/<class_id>/trend",
        "课程教学班对比": "/api/statistics/course/<course_id>/classes",
        "教师汇总": "/api/statistics/teacher/<teacher_id>/summary",
        "每日趋势": "/api/statistics/trend/daily",
        "连续缺勤预警": "/api/statistics/warning/continuous_absent",
        "无效签到预警": "/api/statistics/warning/invalid_signin",
        "场次未签到名单": "/api/statistics/session/<session_id>/absent_list"
    })


# ==================== 1. 学生个人统计 ====================
@app.route("/api/statistics/student/<student_id>")
def get_student_stats(student_id):
    """查询单个学生的出勤汇总（含出勤率）"""
    try:
        db = get_conn()
        cursor = db.cursor()
        sql = """
            SELECT s.student_id, s.name, s.department,
                   COUNT(DISTINCT ar.session_id) AS total_sessions,
                   COUNT(DISTINCT CASE WHEN ar.attendance_status = 'present' THEN ar.session_id END) AS present_count,
                   COUNT(DISTINCT CASE WHEN ar.attendance_status = 'late' THEN ar.session_id END) AS late_count,
                   COUNT(DISTINCT CASE WHEN ar.attendance_status = 'absent' THEN ar.session_id END) AS absent_count,
                   COUNT(DISTINCT CASE WHEN ar.attendance_status = 'leave' THEN ar.session_id END) AS leave_count
            FROM student s
            LEFT JOIN attendance_record ar ON s.student_id = ar.student_id
            WHERE s.student_id = %s
            GROUP BY s.student_id, s.name, s.department
        """
        cursor.execute(sql, [student_id])
        data = cursor.fetchone()

        if data is None:
            data = {
                "student_id": student_id,
                "name": "该学生不存在",
                "department": "-",
                "total_sessions": 0,
                "present_count": 0,
                "late_count": 0,
                "absent_count": 0,
                "leave_count": 0,
                "attendance_rate": 0.0
            }
        else:
            total = data["total_sessions"] or 0
            leave_count = data["leave_count"] or 0
            accountable = max(total - leave_count, 0)
            data["accountable_sessions"] = accountable
            data["attendance_rate"] = round((data["present_count"] + data["late_count"]) / accountable * 100, 2) if accountable > 0 else 0.0

        return jsonify(code=200, msg="success", data=data)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=None)


# ==================== 2. 班级统计  ====================
@app.route("/api/statistics/class/<class_id>")
def get_class_stats(class_id):
    try:
        db = get_conn()
        cursor = db.cursor()
        sql = """
            SELECT tc.class_id, c.course_name,
                   COUNT(DISTINCT e.student_id) AS total_students,
                   COUNT(DISTINCT CASE WHEN ar.attendance_status IN ('present','late') THEN ar.student_id END) AS checked_students,
                   SUM(CASE WHEN ar.attendance_status = 'absent' THEN 1 ELSE 0 END) AS absent_total
            FROM teaching_class tc
            JOIN course c ON tc.course_id = c.course_id
            JOIN enrollment e ON tc.class_id = e.class_id
            LEFT JOIN attendance_session ats ON tc.class_id = ats.class_id
            LEFT JOIN attendance_record ar ON ats.session_id = ar.session_id
            WHERE tc.class_id = %s
            GROUP BY tc.class_id, c.course_name
        """
        cursor.execute(sql, [class_id])
        data = cursor.fetchone()
        if data is None:
            data = {
                "class_id": class_id,
                "course_name": "该班级不存在",
                "total_students": 0,
                "checked_students": 0,
                "absent_total": 0,
                "attendance_rate": 0.0
            }
        else:
            total = data["total_students"]
            data["attendance_rate"] = round(data["checked_students"] / total * 100, 2) if total > 0 else 0.0
        return jsonify(code=200, msg="success", data=data)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=None)


# ==================== 3. 院系统计 ====================
@app.route("/api/statistics/department")
def get_dept_stats():
    """各院系平均出勤率及学生人数"""
    try:
        db = get_conn()
        cursor = db.cursor()
        sql = """
            SELECT s.department,
                   COUNT(DISTINCT s.student_id) AS student_count,
                   ROUND(AVG(CASE WHEN ar.attendance_status = 'leave' THEN NULL WHEN ar.attendance_status IN ('present', 'late') THEN 1 ELSE 0 END) * 100, 2) AS avg_attendance_rate
            FROM student s
            LEFT JOIN attendance_record ar ON s.student_id = ar.student_id
            GROUP BY s.department
        """
        cursor.execute(sql)
        data = cursor.fetchall()
        for item in data:
            if item["avg_attendance_rate"] is None:
                item["avg_attendance_rate"] = 0.0
        return jsonify(code=200, msg="success", data=data)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=[])


# ==================== 4. 缺勤TOP10 ====================
@app.route("/api/statistics/absent_top10")
def get_absent_top10():
    """缺勤次数最多的10名学生"""
    try:
        db = get_conn()
        cursor = db.cursor()
        sql = """
            SELECT s.student_id, s.name, s.department,
                   COUNT(ar.record_id) AS absent_count
            FROM student s
            JOIN attendance_record ar ON s.student_id = ar.student_id
            WHERE ar.attendance_status = 'absent'
            GROUP BY s.student_id, s.name, s.department
            ORDER BY absent_count DESC
            LIMIT 10
        """
        cursor.execute(sql)
        data = cursor.fetchall()
        return jsonify(code=200, msg="success", data=data)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=[])


# ==================== 5. 教学班整体概览 ====================
@app.route("/api/statistics/class/<class_id>/overview")
def get_class_overview(class_id):
    """教学班出勤率总览（含应到人次）"""
    try:
        db = get_conn()
        cursor = db.cursor()

        # 班级基本信息和选课人数
        cursor.execute("""
            SELECT tc.class_id, c.course_name, tc.semester, tc.location,
                   COUNT(DISTINCT e.student_id) AS total_students
            FROM teaching_class tc
            JOIN course c ON tc.course_id = c.course_id
            LEFT JOIN enrollment e ON tc.class_id = e.class_id AND e.enroll_status='enrolled'
            WHERE tc.class_id = %s
            GROUP BY tc.class_id, c.course_name, tc.semester, tc.location
        """, (class_id,))
        base = cursor.fetchone()
        if not base:
            return jsonify(code=404, msg="教学班不存在")

        # 统计该班所有场次的出勤情况
        cursor.execute("""
            SELECT
                COUNT(DISTINCT ats.session_id) AS total_sessions,
                COUNT(DISTINCT CASE WHEN ar.attendance_status IN ('present','late') THEN CONCAT(ar.student_id, '-', ar.session_id) END) AS valid_attendance,
                COUNT(DISTINCT CASE WHEN ar.attendance_status = 'leave' THEN CONCAT(ar.student_id, '-', ar.session_id) END) AS total_leave,
                SUM(CASE WHEN ar.attendance_status = 'absent' THEN 1 ELSE 0 END) AS total_absent
            FROM attendance_session ats
            LEFT JOIN attendance_record ar ON ats.session_id = ar.session_id
            WHERE ats.class_id = %s
        """, (class_id,))
        stats = cursor.fetchone()

        total_sessions = stats['total_sessions'] or 0
        valid_att = stats['valid_attendance'] or 0
        total_students = base['total_students'] or 0
        total_leave = stats['total_leave'] or 0
        expected = max(total_students * total_sessions - total_leave, 0)
        attendance_rate = round(valid_att / expected * 100, 2) if expected > 0 else 0.0

        data = {
            "class_id": class_id,
            "course_name": base['course_name'],
            "semester": base['semester'],
            "location": base['location'],
            "total_students": total_students,
            "total_sessions": total_sessions,
            "valid_attendance": valid_att,
            "total_absent": stats['total_absent'] or 0,
            "total_leave": total_leave,
            "expected_attendance": expected,
            "attendance_rate": attendance_rate
        }
        return jsonify(code=200, msg="success", data=data)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=None)


# ==================== 6. 教学班趋势 ====================
@app.route("/api/statistics/class/<class_id>/trend")
def get_class_trend(class_id):
    """教学班各场次的出勤率变化趋势"""
    try:
        db = get_conn()
        cursor = db.cursor()

        # 获取该班总选课人数（作为每场的应到人数）
        cursor.execute("""
            SELECT COUNT(DISTINCT student_id) AS total_students
            FROM enrollment
            WHERE class_id = %s AND enroll_status='enrolled'
        """, (class_id,))
        total_students = cursor.fetchone()['total_students'] or 0
        if total_students == 0:
            return jsonify(code=200, msg="该班级无学生", data=[])

        cursor.execute("""
            SELECT ats.session_id, ats.session_date,
                   COUNT(CASE WHEN ar.attendance_status IN ('present','late') THEN 1 END) AS valid_count,
                   COUNT(CASE WHEN ar.attendance_status = 'leave' THEN 1 END) AS leave_count,
                   COUNT(CASE WHEN ar.attendance_status = 'absent' THEN 1 END) AS absent_count
            FROM attendance_session ats
            LEFT JOIN attendance_record ar ON ats.session_id = ar.session_id
            WHERE ats.class_id = %s
            GROUP BY ats.session_id, ats.session_date
            ORDER BY ats.session_date ASC
        """, (class_id,))
        rows = cursor.fetchall()

        trend = []
        for row in rows:
            valid = row['valid_count'] or 0
            leave_count = row['leave_count'] or 0
            expected = max(total_students - leave_count, 0)
            rate = round(valid / expected * 100, 2) if expected > 0 else 0.0
            trend.append({
                "session_id": row['session_id'],
                "date": row['session_date'].strftime("%Y-%m-%d"),
                "valid_count": valid,
                "absent_count": row['absent_count'] or 0,
                "leave_count": leave_count,
                "attendance_rate": rate
            })
        return jsonify(code=200, msg="success", data=trend)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=[])


# ==================== 7. 课程下各教学班对比 ====================
@app.route("/api/statistics/course/<course_id>/classes")
def get_course_classes_stats(course_id):
    """同一课程下各教学班的出勤率对比"""
    try:
        db = get_conn()
        cursor = db.cursor()
        cursor.execute("""
            SELECT tc.class_id, tc.semester,
                   COUNT(DISTINCT e.student_id) AS total_students,
                   COUNT(DISTINCT ats.session_id) AS total_sessions,
                   COUNT(DISTINCT CASE WHEN ar.attendance_status IN ('present','late') THEN CONCAT(ar.student_id, '-', ar.session_id) END) AS valid_att,
                   COUNT(DISTINCT CASE WHEN ar.attendance_status = 'leave' THEN CONCAT(ar.student_id, '-', ar.session_id) END) AS leave_count
            FROM teaching_class tc
            LEFT JOIN enrollment e ON tc.class_id = e.class_id AND e.enroll_status='enrolled'
            LEFT JOIN attendance_session ats ON tc.class_id = ats.class_id
            LEFT JOIN attendance_record ar ON ats.session_id = ar.session_id
            WHERE tc.course_id = %s
            GROUP BY tc.class_id, tc.semester
        """, (course_id,))
        rows = cursor.fetchall()

        result = []
        for row in rows:
            total_students = row['total_students'] or 0
            total_sessions = row['total_sessions'] or 0
            valid_att = row['valid_att'] or 0
            leave_count = row['leave_count'] or 0
            expected = max(total_students * total_sessions - leave_count, 0)
            rate = round(valid_att / expected * 100, 2) if expected > 0 else 0.0
            result.append({
                "class_id": row['class_id'],
                "semester": row['semester'],
                "total_students": total_students,
                "total_sessions": total_sessions,
                "leave_count": leave_count,
                "attendance_rate": rate
            })
        return jsonify(code=200, msg="success", data=result)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=[])


# ==================== 8. 教师汇总 ====================
@app.route("/api/statistics/teacher/<teacher_id>/summary")
def get_teacher_summary(teacher_id):
    """教师所带所有教学班的汇总出勤"""
    try:
        db = get_conn()
        cursor = db.cursor()

        cursor.execute("SELECT name FROM teacher WHERE teacher_id=%s", (teacher_id,))
        teacher = cursor.fetchone()
        if not teacher:
            return jsonify(code=404, msg="教师不存在")

        cursor.execute("SELECT class_id FROM teaching_class WHERE teacher_id=%s", (teacher_id,))
        classes = cursor.fetchall()
        class_ids = [c['class_id'] for c in classes]
        if not class_ids:
            return jsonify(code=200, msg="该教师暂无教学班", data={
                "teacher_id": teacher_id,
                "name": teacher['name'],
                "total_classes": 0,
                "avg_attendance_rate": 0.0,
                "class_list": []
            })

        class_stats = []
        total_rate_sum = 0
        for cid in class_ids:
            cursor.execute("""
                SELECT COUNT(DISTINCT e.student_id) AS total_students,
                       COUNT(DISTINCT ats.session_id) AS total_sessions,
                       COUNT(DISTINCT CASE WHEN ar.attendance_status IN ('present','late') THEN CONCAT(ar.student_id, '-', ar.session_id) END) AS valid_att,
                       COUNT(DISTINCT CASE WHEN ar.attendance_status = 'leave' THEN CONCAT(ar.student_id, '-', ar.session_id) END) AS leave_count
                FROM teaching_class tc
                LEFT JOIN enrollment e ON tc.class_id = e.class_id AND e.enroll_status='enrolled'
                LEFT JOIN attendance_session ats ON tc.class_id = ats.class_id
                LEFT JOIN attendance_record ar ON ats.session_id = ar.session_id
                WHERE tc.class_id = %s
            """, (cid,))
            row = cursor.fetchone()
            total_students = row['total_students'] or 0
            total_sessions = row['total_sessions'] or 0
            valid_att = row['valid_att'] or 0
            leave_count = row['leave_count'] or 0
            expected = max(total_students * total_sessions - leave_count, 0)
            rate = round(valid_att / expected * 100, 2) if expected > 0 else 0.0
            class_stats.append({
                "class_id": cid,
                "total_students": total_students,
                "total_sessions": total_sessions,
                "leave_count": leave_count,
                "attendance_rate": rate
            })
            total_rate_sum += rate

        avg_rate = round(total_rate_sum / len(class_stats), 2) if class_stats else 0.0
        data = {
            "teacher_id": teacher_id,
            "name": teacher['name'],
            "total_classes": len(class_stats),
            "avg_attendance_rate": avg_rate,
            "class_list": class_stats
        }
        return jsonify(code=200, msg="success", data=data)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=None)


# ==================== 9. 每日出勤趋势 ====================
@app.route("/api/statistics/trend/daily")
def get_daily_trend():
    """全校每日出勤率（按日期分组）"""
    try:
        db = get_conn()
        cursor = db.cursor()
        # 查询每天的出勤数和应到总人次
        sql = """
            SELECT DATE(ats.session_date) AS date,
                   SUM(COALESCE(rec.total_valid, 0)) AS total_valid,
                   SUM(GREATEST(COALESCE(enr.total_students, 0) - COALESCE(rec.leave_count, 0), 0)) AS total_expected
            FROM attendance_session ats
            LEFT JOIN (
                SELECT class_id, COUNT(*) AS total_students
                FROM enrollment
                WHERE enroll_status='enrolled'
                GROUP BY class_id
            ) enr ON ats.class_id = enr.class_id
            LEFT JOIN (
                SELECT session_id,
                       SUM(CASE WHEN attendance_status IN ('present','late') THEN 1 ELSE 0 END) AS total_valid,
                       SUM(CASE WHEN attendance_status = 'leave' THEN 1 ELSE 0 END) AS leave_count
                FROM attendance_record
                GROUP BY session_id
            ) rec ON ats.session_id = rec.session_id
            GROUP BY DATE(ats.session_date)
            ORDER BY date ASC
        """
        cursor.execute(sql)
        rows = cursor.fetchall()

        trend = []
        for row in rows:
            date_str = row['date'].strftime("%Y-%m-%d")
            total_valid = row['total_valid'] or 0
            total_expected = row['total_expected'] or 1
            rate = round(total_valid / total_expected * 100, 2) if total_expected > 0 else 0.0
            trend.append({
                "date": date_str,
                "valid_count": total_valid,
                "expected_count": total_expected,
                "attendance_rate": rate
            })
        return jsonify(code=200, msg="success", data=trend)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=[])


# ==================== 10. 连续缺勤预警 ====================
@app.route("/api/statistics/warning/continuous_absent")
def get_continuous_absent():
    """缺勤次数≥3次的学生列表（近似连续缺勤预警）"""
    try:
        limit = request.args.get('limit', 20, type=int)
        db = get_conn()
        cursor = db.cursor()
        sql = """
            SELECT s.student_id, s.name, s.department,
                   COUNT(ar.record_id) AS absent_count
            FROM student s
            JOIN attendance_record ar ON s.student_id = ar.student_id
            WHERE ar.attendance_status = 'absent'
            GROUP BY s.student_id, s.name, s.department
            HAVING absent_count >= 3
            ORDER BY absent_count DESC
            LIMIT %s
        """
        cursor.execute(sql, (limit,))
        rows = cursor.fetchall()
        return jsonify(code=200, msg="success", data=rows)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=[])


# ==================== 11. 无效签到统计 ====================
@app.route("/api/statistics/warning/invalid_signin")
def get_invalid_signin():
    """无效签到次数最多的学生（is_valid='invalid'）"""
    try:
        limit = request.args.get('limit', 20, type=int)
        db = get_conn()
        cursor = db.cursor()
        sql = """
            SELECT s.student_id, s.name, COUNT(ar.record_id) AS invalid_count
            FROM student s
            JOIN attendance_record ar ON s.student_id = ar.student_id
            WHERE ar.is_valid = 'invalid'
            GROUP BY s.student_id, s.name
            ORDER BY invalid_count DESC
            LIMIT %s
        """
        cursor.execute(sql, (limit,))
        rows = cursor.fetchall()
        return jsonify(code=200, msg="success", data=rows)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=[])


# ==================== 12. 场次未签到名单 ====================
@app.route("/api/statistics/session/<int:session_id>/absent_list")
def get_session_absent_list(session_id):
    """某场次中已选课但未有效签到的学生名单"""
    try:
        db = get_conn()
        cursor = db.cursor()
        cursor.execute("SELECT class_id FROM attendance_session WHERE session_id=%s", (session_id,))
        sess = cursor.fetchone()
        if not sess:
            return jsonify(code=404, msg="场次不存在")
        class_id = sess['class_id']

        sql = """
            SELECT s.student_id, s.name, s.department
            FROM student s
            JOIN enrollment e ON s.student_id = e.student_id
            WHERE e.class_id = %s AND e.enroll_status='enrolled'
              AND NOT EXISTS (
                  SELECT 1 FROM attendance_record ar
                  WHERE ar.session_id = %s AND ar.student_id = s.student_id
                    AND ar.is_valid = 'valid'
              )
            ORDER BY s.student_id
        """
        cursor.execute(sql, (class_id, session_id))
        rows = cursor.fetchall()
        return jsonify(code=200, msg="success", data=rows)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=[])

# ==================== 13. 学生签到明细记录 ====================
@app.route("/api/statistics/student/<student_id>/records")
def get_student_records(student_id):
    """查询单个学生的所有签到记录明细（按时间倒序）"""
    try:
        db = get_conn()
        cursor = db.cursor()
        sql = """
            SELECT r.record_id, r.session_id, r.scan_time, r.attendance_status, r.is_valid, r.remark,
                   ats.session_date, c.course_name
            FROM attendance_record r
            JOIN attendance_session ats ON r.session_id = ats.session_id
            JOIN teaching_class tc ON ats.class_id = tc.class_id
            JOIN course c ON tc.course_id = c.course_id
            WHERE r.student_id = %s
            ORDER BY r.scan_time DESC
        """
        cursor.execute(sql, (student_id,))
        rows = cursor.fetchall()
        # 格式化日期时间
        for row in rows:
            if isinstance(row.get('scan_time'), datetime):
                row['scan_time'] = row['scan_time'].strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(row.get('session_date'), date):
                row['session_date'] = row['session_date'].strftime('%Y-%m-%d')
        return jsonify(code=200, msg="success", data=rows)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=[])

# ==================== 14. 教师列表 ====================
@app.route("/api/teachers", methods=["GET"])
def list_teachers():
    """查询所有教师（供下拉选择）"""
    try:
        db = get_conn()
        cursor = db.cursor()
        cursor.execute("SELECT teacher_id, name, department FROM teacher ORDER BY teacher_id")
        rows = cursor.fetchall()
        return jsonify(code=200, msg="success", data=rows)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=[])

# ==================== 15. 教学班缺勤学生统计 ====================
@app.route("/api/statistics/class/<class_id>/absent_students")
def get_class_absent_students(class_id):
    try:
        db = get_conn()
        cursor = db.cursor()
        sql = """
            SELECT 
                s.student_id,
                s.name,
                s.department,
                COUNT(DISTINCT ats.session_id) AS total_sessions,
                COUNT(DISTINCT CASE WHEN ar.attendance_status IN ('present','late') THEN ar.session_id END) AS valid_sessions,
                COUNT(DISTINCT CASE WHEN ar.attendance_status = 'leave' THEN ar.session_id END) AS leave_sessions,
                (COUNT(DISTINCT ats.session_id)
                 - COUNT(DISTINCT CASE WHEN ar.attendance_status IN ('present','late') THEN ar.session_id END)
                 - COUNT(DISTINCT CASE WHEN ar.attendance_status = 'leave' THEN ar.session_id END)) AS absent_count
            FROM student s
            JOIN enrollment e ON s.student_id = e.student_id AND e.enroll_status='enrolled'
            JOIN attendance_session ats ON e.class_id = ats.class_id
            LEFT JOIN attendance_record ar ON ar.session_id = ats.session_id AND ar.student_id = s.student_id
            WHERE e.class_id = %s
            GROUP BY s.student_id, s.name, s.department
            HAVING absent_count > 0
            ORDER BY absent_count DESC
        """
        cursor.execute(sql, (class_id,))
        rows = cursor.fetchall()
        return jsonify(code=200, msg="success", data=rows)
    except Exception as e:
        return jsonify(code=500, msg=f"服务器错误：{str(e)}", data=[])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)