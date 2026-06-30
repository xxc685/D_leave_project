"""
扫码签到系统 - 后端核心接口(B 部分)

职责范围:
    1. 教师发起签到            POST   /api/sessions
    2. 学生扫码签到(核心)      POST   /api/sign_in
    3. 关闭场次并补全缺勤      POST   /api/sessions/<id>/finalize
    4. 教师手动修正签到记录    PATCH  /api/records/<record_id>
    5. 查询场次/学生的签到记录 GET    /api/sessions/<id>/records、/api/students/<id>/records
    6. 二维码 token 反查会话   GET    /api/sessions/by_token/<qr_token>

字段/状态值约定(全模块统一):
    attendance_status: present(正常) / late(迟到) / absent(缺勤) / invalid(无效) / leave(请假)
    is_valid:          valid / invalid
    session_status:    ongoing(进行中) / closed(已结束)
    enroll_status:     enrolled(在选)  / dropped(已退)
"""

from flask import Flask, request, jsonify, Response
from db import get_conn
from datetime import date, datetime, timedelta
from decimal import Decimal
from math import radians, sin, cos, asin, sqrt
from typing import Any, cast
import uuid
import csv
import io
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

from leave_api import leave_bp
from management_api import management_bp
app.register_blueprint(leave_bp)
app.register_blueprint(management_bp)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, PUT, DELETE, OPTIONS"
    return response

VALID_ATTEND_STATUS = {"present", "late", "absent", "invalid", "leave"}
VALID_IS_VALID = {"valid", "invalid"}
DbRow = dict[str, Any]


# ===================== 工具函数 =====================

def generate_qr_token() -> str:
    return uuid.uuid4().hex


def parse_dt(value: object) -> datetime:
    """容忍 datetime 直接传入,或字符串解析。无法解析时抛 ValueError。"""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        raise ValueError(f"无法解析日期时间: {value!r}")
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine 公式计算地表两点距离(米)。"""
    R = 6_371_000.0
    rlat1, rlat2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


def judge_time_status(
    scan_time: datetime,
    start_time: datetime,
    valid_minutes: int,
    end_time: datetime,
) -> tuple[str, str, str]:
    """
    返回 (attendance_status, is_valid, message)。
      - 开始前        -> invalid
      - 开始~开始+valid_minutes -> present
      - 之后~end_time -> late
      - end_time 之后 -> invalid
    """
    if scan_time < start_time:
        return "invalid", "invalid", "签到尚未开始"
    valid_deadline = start_time + timedelta(minutes=valid_minutes)
    if scan_time <= valid_deadline:
        return "present", "valid", "签到成功"
    if scan_time <= end_time:
        return "late", "valid", "签到成功(迟到)"
    return "invalid", "invalid", "签到已结束"


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def ok(data: Any = None, msg: str = "ok"):
    return jsonify({"code": 200, "message": msg, "data": json_safe(data)})


def fail(msg: str, code: int = 400, data: Any = None):
    return jsonify({"code": code, "message": msg, "data": json_safe(data)})


# ===================== 1. 教师发起签到 =====================

@app.route("/api/sessions", methods=["POST"])
def create_session():
    """
    入参 JSON:
        class_id, session_date(YYYY-MM-DD),
        start_time, end_time (YYYY-MM-DD HH:MM:SS),
        valid_minutes, location_latitude, location_longitude, location_radius
    """
    data = request.get_json(silent=True) or {}

    required = ["class_id", "session_date", "start_time", "end_time",
                "valid_minutes", "location_latitude",
                "location_longitude", "location_radius"]
    for k in required:
        if data.get(k) in (None, ""):
            return fail(f"参数 {k} 不能为空")

    try:
        start_time = parse_dt(data["start_time"])
        end_time = parse_dt(data["end_time"])
    except (ValueError, TypeError):
        return fail("时间格式应为 YYYY-MM-DD HH:MM:SS")
    if start_time >= end_time:
        return fail("开始时间必须早于结束时间")

    try:
        valid_minutes = int(data["valid_minutes"])
        if valid_minutes <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return fail("valid_minutes 必须为正整数")
    if start_time + timedelta(minutes=valid_minutes) > end_time:
        return fail("valid_minutes 不能超过 start_time 到 end_time 的跨度")

    try:
        lat = float(data["location_latitude"])
        lon = float(data["location_longitude"])
        radius = int(data["location_radius"])
        if radius <= 0:
            return fail("location_radius 必须为正整数")
    except (TypeError, ValueError):
        return fail("定位参数格式错误")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT class_id FROM teaching_class WHERE class_id=%s",
                (data["class_id"],))
            teaching_class = cast(DbRow , cursor.fetchone())
            if teaching_class is None:
                return fail("教学班不存在")

            qr_token = generate_qr_token()
            cursor.execute("""
                INSERT INTO attendance_session
                (class_id, session_date, start_time, end_time, qr_token,
                 valid_minutes, location_latitude, location_longitude,
                 location_radius, session_status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["class_id"], data["session_date"], start_time, end_time,
                qr_token, valid_minutes, lat, lon, radius, "ongoing"
            ))
            session_id = cursor.lastrowid
        conn.commit()
        return ok({"session_id": session_id, "qr_token": qr_token},
                  "签到场次创建成功")
    except Exception as e:
        conn.rollback()
        return fail(str(e), code=500)
    finally:
        conn.close()


# ===================== 2. 学生扫码签到(核心) =====================

@app.route("/api/sign_in", methods=["POST"])
def sign_in():
    """
    入参 JSON: qr_token, student_id, latitude, longitude

    校验顺序:
        二维码有效 -> 场次仍开放 -> 学生存在 -> 已选课
        -> 未重复签到(SELECT FOR UPDATE 锁防并发)
        -> 时间窗口 -> 定位范围
    失败也写入 record(is_valid='invalid'),保留审计痕迹。
    """
    data = request.get_json(silent=True) or {}
    for k in ["qr_token", "student_id", "latitude", "longitude"]:
        if data.get(k) in (None, ""):
            return fail(f"参数 {k} 不能为空")

    try:
        lat = float(data["latitude"])
        lon = float(data["longitude"])
    except (TypeError, ValueError):
        return fail("经纬度格式错误")

    conn = get_conn()
    try:
        # 事务包裹整个判定,行锁防止并发重复签到
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM attendance_session "
                "WHERE qr_token=%s FOR UPDATE",
                (data["qr_token"],))
            session = cast(DbRow , cursor.fetchone())
            if session is None:
                conn.rollback()
                return fail("二维码无效或已失效")
            if session["session_status"] != "ongoing":
                conn.rollback()
                return fail("该签到场次已关闭")

            cursor.execute(
                "SELECT student_id FROM student WHERE student_id=%s",
                (data["student_id"],))
            student = cast(DbRow , cursor.fetchone())
            if student is None:
                conn.rollback()
                return fail("学生不存在")

            cursor.execute("""
                SELECT enrollment_id FROM enrollment
                WHERE student_id=%s AND class_id=%s
                  AND enroll_status='enrolled'
            """, (data["student_id"], session["class_id"]))
            enrollment = cast(DbRow , cursor.fetchone())
            if enrollment is None:
                conn.rollback()
                return fail("该学生未选修当前教学班")

            cursor.execute("""
                SELECT record_id FROM attendance_record
                WHERE session_id=%s AND student_id=%s AND is_valid='valid'
                FOR UPDATE
            """, (session["session_id"], data["student_id"]))
            valid_record = cast(DbRow , cursor.fetchone())
            if valid_record is not None:
                conn.rollback()
                return fail("已签到过,无需重复签到")

            scan_time = datetime.now()
            status, is_valid, msg = judge_time_status(
                scan_time, session["start_time"],
                session["valid_minutes"], session["end_time"])

            # 计算学生上传定位与场次中心点的距离
            sess_lat = float(session["location_latitude"])
            sess_lon = float(session["location_longitude"])

            # 教师未开启定位时坐标为 (0, 0)，直接放行定位校验
            if sess_lat == 0.0 and sess_lon == 0.0:
                location_ok = True
                distance = 0.0
            else:
                distance = haversine_meters(lat, lon, sess_lat, sess_lon)
                location_ok = distance <= session["location_radius"]

            # 同时记录所有失败原因到 remark
            remark_bits = []
            location_fail_msg = ""
            if not location_ok:
                location_fail_msg = (
                    f"定位超出范围(距离={distance:.1f}m, "
                    f"允许半径={session['location_radius']}m)")
                remark_bits.append(location_fail_msg)

            if status == "late":
                remark_bits.append("迟到")
            elif status == "invalid":
                remark_bits.append(msg)

            # 决定最终状态:任一失败均整体置为 invalid
            if not location_ok:
                status = "invalid"
                is_valid = "invalid"
                msg = f"签到失败:{location_fail_msg}"
            elif status == "invalid":
                pass  # 已是时间失败的 invalid

            cursor.execute("""
                INSERT INTO attendance_record
                (session_id, student_id, scan_time, attendance_status,
                 latitude, longitude, is_valid, remark)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                session["session_id"], data["student_id"], scan_time,
                status, lat, lon, is_valid,
                "; ".join(remark_bits) or None
            ))
            record_id = cursor.lastrowid
        conn.commit()
        return ok({
            "record_id": record_id,
            "attendance_status": status,
            "is_valid": is_valid,
            "distance_m": round(distance, 1),
            "scan_time": scan_time.strftime("%Y-%m-%d %H:%M:%S")
        }, msg)
    except Exception as e:
        conn.rollback()
        return fail(str(e), code=500)
    finally:
        conn.close()


# ===================== 3. 关闭场次 + 缺勤补录 =====================

@app.route("/api/sessions/<int:session_id>/finalize", methods=["POST"])
def finalize_session(session_id):
    """
    将场次置为 closed,并为"无任何有效签到记录"的在选学生
    写入一条 absent + invalid 的考勤记录。

    入参 JSON(可选):
        force: true 时允许在 end_time 之前提前关闭(默认 false)
    """
    data = request.get_json(silent=True) or {}
    force = bool(data.get("force", False))

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM attendance_session WHERE session_id=%s",
                (session_id,))
            session = cast(DbRow , cursor.fetchone())
            if session is None:
                return fail("签到场次不存在", code=404)
            if session["session_status"] == "closed":
                return fail("该签到场次已关闭")
            end_time = cast(datetime, session["end_time"])
            if not force and datetime.now() < end_time:
                return fail(
                    "尚未到 end_time,如需提前关闭请传 force=true",
                    data={"end_time": end_time})

            cursor.execute("""
                SELECT e.student_id FROM enrollment e
                WHERE e.class_id=%s AND e.enroll_status='enrolled'
                  AND NOT EXISTS (
                    SELECT 1 FROM attendance_record r
                    WHERE r.session_id=%s
                      AND r.student_id=e.student_id
                      AND r.is_valid='valid'
                  )
            """, (session["class_id"], session_id))
            absent_rows = cast(list[DbRow], cursor.fetchall())
            absent_students = [row["student_id"] for row in absent_rows]

            now = datetime.now()
            for sid in absent_students:
                cursor.execute("""
                    INSERT INTO attendance_record
                    (session_id, student_id, scan_time, attendance_status,
                     latitude, longitude, is_valid, remark)
                    VALUES (%s,%s,%s,'absent',0,0,'invalid','未签到,系统补录')
                """, (session_id, sid, now))

            cursor.execute(
                "UPDATE attendance_session SET session_status='closed' "
                "WHERE session_id=%s",
                (session_id,))
        conn.commit()
        return ok({
            "absent_count": len(absent_students),
            "absent_students": absent_students,
            "force": force
        }, "签到场次已关闭")
    except Exception as e:
        conn.rollback()
        return fail(str(e), code=500)
    finally:
        conn.close()


# ===================== 4. 教师手动修正签到记录 =====================

@app.route("/api/records/<int:record_id>", methods=["PATCH"])
def update_record(record_id):
    """
    教师纠错接口:
      入参 JSON 可选字段
        attendance_status: present/late/absent/invalid/leave
        is_valid:          valid/invalid (不传则根据 status 自动:
                                          absent/invalid -> invalid,其他 valid)
        remark:            备注(覆盖旧值;传空串则清空)
    """
    data = request.get_json(silent=True) or {}
    new_status = data.get("attendance_status")
    new_valid = data.get("is_valid")
    new_remark = data.get("remark")  # None=不改;空串=清空

    if new_status is None and new_valid is None and new_remark is None:
        return fail("至少需要提供一个待修改字段")

    if new_status is not None and new_status not in VALID_ATTEND_STATUS:
        return fail(f"attendance_status 必须为 {sorted(VALID_ATTEND_STATUS)} 之一")
    if new_valid is not None and new_valid not in VALID_IS_VALID:
        return fail(f"is_valid 必须为 {sorted(VALID_IS_VALID)} 之一")

    # 当传入 status 但未传 is_valid 时自动推断
    if new_status is not None and new_valid is None:
        new_valid = "invalid" if new_status in ("absent", "invalid") else "valid"

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM attendance_record WHERE record_id=%s",
                (record_id,))
            record = cast(DbRow, cursor.fetchone())
            if record is None:
                return fail("签到记录不存在", code=404)

            sets: list[str] = []
            params: list[Any] = []
            if new_status is not None:
                sets.append("attendance_status=%s")
                params.append(new_status)
            if new_valid is not None:
                sets.append("is_valid=%s")
                params.append(new_valid)
            if new_remark is not None:
                sets.append("remark=%s")
                params.append(new_remark if new_remark != "" else None)
            params.append(record_id)

            cursor.execute(
                f"UPDATE attendance_record SET {', '.join(sets)} "
                "WHERE record_id=%s",
                tuple(params))

            cursor.execute(
                "SELECT * FROM attendance_record WHERE record_id=%s",
                (record_id,))
            updated = cast(DbRow, cursor.fetchone())
            if updated is None:
                return fail("签到记录不存在", code=404)
        conn.commit()
        # datetime 序列化
        for k in ("scan_time",):
            if isinstance(updated.get(k), datetime):
                updated[k] = updated[k].strftime("%Y-%m-%d %H:%M:%S")
        return ok(updated, "签到记录已更新")
    except Exception as e:
        conn.rollback()
        return fail(str(e), code=500)
    finally:
        conn.close()


# ===================== 5. 查询接口 =====================

@app.route("/api/sessions/by_token/<qr_token>", methods=["GET"])
def get_session_by_token(qr_token):
    """学生扫码后,前端用此接口拉取场次基本信息再发起签到。"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT s.session_id, s.class_id, s.session_date,
                       s.start_time, s.end_time, s.valid_minutes,
                       s.session_status,
                       s.location_latitude, s.location_longitude,
                       s.location_radius,
                       c.course_name, t.location AS classroom
                FROM attendance_session s
                JOIN teaching_class t ON t.class_id = s.class_id
                JOIN course c ON c.course_id = t.course_id
                WHERE s.qr_token=%s
            """, (qr_token,))
            row = cast(DbRow, cursor.fetchone())
        if row is None:
            return fail("二维码无效", code=404)
        return ok(row)
    finally:
        conn.close()


@app.route("/api/sessions/<int:session_id>/records", methods=["GET"])
def list_session_records(session_id):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT r.record_id, r.student_id, s.name AS student_name,
                       r.scan_time, r.attendance_status, r.is_valid,
                       r.latitude, r.longitude, r.remark
                FROM attendance_record r
                LEFT JOIN student s ON s.student_id = r.student_id
                WHERE r.session_id=%s
                ORDER BY r.scan_time
            """, (session_id,))
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    finally:
        conn.close()


@app.route("/api/admin/attendance_records", methods=["GET"])
def admin_list_attendance_records():
    """
    Web 管理端：查询全部签到记录（支持按学号、状态筛选）。
    Query params:
        student_id        可选，精确匹配学号
        attendance_status 可选，present/late/absent/invalid
    """
    student_id = (request.args.get("student_id") or "").strip()
    attendance_status = (request.args.get("attendance_status") or "").strip()

    if attendance_status and attendance_status not in VALID_ATTEND_STATUS:
        return fail(f"attendance_status 必须为 {sorted(VALID_ATTEND_STATUS)} 之一")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT r.record_id, r.student_id, st.name AS student_name,
                       c.course_name, r.scan_time, r.attendance_status,
                       r.latitude, r.longitude, r.remark,
                       sess.location_latitude, sess.location_longitude,
                       sess.session_id, sess.session_date
                FROM attendance_record r
                LEFT JOIN student st ON st.student_id = r.student_id
                JOIN attendance_session sess ON sess.session_id = r.session_id
                JOIN teaching_class t ON t.class_id = sess.class_id
                JOIN course c ON c.course_id = t.course_id
                WHERE 1=1
            """
            params: list[Any] = []
            if student_id:
                sql += " AND r.student_id = %s"
                params.append(student_id)
            if attendance_status:
                sql += " AND r.attendance_status = %s"
                params.append(attendance_status)
            sql += " ORDER BY r.scan_time DESC"

            cursor.execute(sql, tuple(params))
            rows = cast(list[DbRow], cursor.fetchall())

        for row in rows:
            lat = row.get("latitude")
            lon = row.get("longitude")
            sess_lat = row.get("location_latitude")
            sess_lon = row.get("location_longitude")
            if lat is not None and lon is not None and sess_lat is not None and sess_lon is not None:
                if float(lat) != 0 or float(lon) != 0:
                    row["distance_m"] = round(haversine_meters(
                        float(lat), float(lon),
                        float(sess_lat), float(sess_lon)), 1)
                else:
                    row["distance_m"] = None
            else:
                row["distance_m"] = None
            row.pop("latitude", None)
            row.pop("longitude", None)
            row.pop("location_latitude", None)
            row.pop("location_longitude", None)

        return ok(rows)
    except Exception as e:
        return fail(str(e), code=500)
    finally:
        conn.close()


@app.route("/api/students/<student_id>/records", methods=["GET"])
def list_student_records(student_id):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT r.record_id, r.session_id, r.scan_time,
                       r.attendance_status, r.is_valid, r.remark,
                       sess.session_date, sess.class_id, c.course_name
                FROM attendance_record r
                JOIN attendance_session sess ON sess.session_id = r.session_id
                JOIN teaching_class t ON t.class_id = sess.class_id
                JOIN course c ON c.course_id = t.course_id
                WHERE r.student_id=%s
                ORDER BY r.scan_time DESC
            """, (student_id,))
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    finally:
        conn.close()


# ===================== 6. 学生基础 CRUD =====================

@app.route("/api/students", methods=["GET"])
def list_students():
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT student_id, name, gender, department, major, class_name "
                "FROM student ORDER BY student_id")
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    finally:
        conn.close()


@app.route("/api/students/export", methods=["GET"])
def export_students():
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT student_id, name, gender, department, major, class_name "
                "FROM student ORDER BY student_id")
            rows = cast(list[DbRow], cursor.fetchall())

        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        csv_content = output.getvalue()
        output.close()

        return Response(
            csv_content,
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=students.csv"
            }
        )
    finally:
        conn.close()


@app.route("/api/students/import", methods=["POST"])
def import_students():
    if "file" not in request.files:
        return fail("未收到上传文件")
    file = request.files["file"]
    if file.filename == "":
        return fail("文件名为空")

    try:
        content = file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        conn = get_conn()
        try:
            count = 0
            with conn.cursor() as cursor:
                for row in reader:
                    sid = (row.get("student_id") or "").strip()
                    name = (row.get("name") or "").strip()
                    if not sid or not name:
                        continue
                    cursor.execute(
                        "INSERT INTO student (student_id, name, gender, department, major, class_name) "
                        "VALUES (%s, %s, %s, %s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE "
                        "name=VALUES(name), gender=VALUES(gender), "
                        "department=VALUES(department), major=VALUES(major), "
                        "class_name=VALUES(class_name)",
                        (sid, name,
                         row.get("gender") or None,
                         row.get("department") or None,
                         row.get("major") or None,
                         row.get("class_name") or None))
                    count += 1
            conn.commit()
            return ok({"imported": count}, f"成功处理 {count} 条记录")
        except Exception as e:
            conn.rollback()
            return fail(str(e), code=500)
        finally:
            conn.close()
    except Exception as e:
        return fail(f"文件解析失败: {str(e)}", code=400)


@app.route("/api/students", methods=["POST"])
def create_student():
    data = request.get_json(silent=True) or {}
    required = ["student_id", "name"]
    for k in required:
        if data.get(k) in (None, ""):
            return fail(f"参数 {k} 不能为空")

    if data.get("gender") and data["gender"] not in ("男", "女"):
        return fail("gender 必须为 男 或 女")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT student_id FROM student WHERE student_id=%s",
                (data["student_id"],))
            if cursor.fetchone() is not None:
                return fail("该学号已存在")

            cursor.execute(
                "INSERT INTO student (student_id, name, gender, department, major, class_name) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (data["student_id"], data["name"],
                 data.get("gender") or None,
                 data.get("department") or None,
                 data.get("major") or None,
                 data.get("class_name") or None))
        conn.commit()
        return ok({"student_id": data["student_id"]}, "学生添加成功")
    except Exception as e:
        conn.rollback()
        return fail(str(e), code=500)
    finally:
        conn.close()


@app.route("/api/students/<student_id>", methods=["PUT"])
def update_student(student_id):
    data = request.get_json(silent=True) or {}
    if not data:
        return fail("至少需要提供一个待修改字段")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT student_id FROM student WHERE student_id=%s",
                (student_id,))
            if cursor.fetchone() is None:
                return fail("学生不存在", code=404)

            sets: list[str] = []
            params: list[Any] = []
            for field in ["name", "gender", "department", "major", "class_name"]:
                if field in data:
                    sets.append(f"{field}=%s")
                    params.append(data[field] if data[field] != "" else None)
            if not sets:
                return fail("没有可修改的字段")
            params.append(student_id)

            cursor.execute(
                f"UPDATE student SET {', '.join(sets)} WHERE student_id=%s",
                tuple(params))
        conn.commit()
        return ok(None, "学生信息已更新")
    except Exception as e:
        conn.rollback()
        return fail(str(e), code=500)
    finally:
        conn.close()


@app.route("/api/students/<student_id>", methods=["DELETE"])
def delete_student(student_id):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT student_id FROM student WHERE student_id=%s",
                (student_id,))
            if cursor.fetchone() is None:
                return fail("学生不存在", code=404)

            cursor.execute(
                "DELETE FROM student WHERE student_id=%s", (student_id,))
        conn.commit()
        return ok(None, "学生已删除")
    except Exception as e:
        conn.rollback()
        return fail(str(e), code=500)
    finally:
        conn.close()


# ===================== 7. 教师专属查询 =====================

@app.route("/api/teacher/<teacher_id>/classes", methods=["GET"])
def list_teacher_classes(teacher_id):
    """查询指定教师所授教学班及课程信息。"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT t.class_id, t.course_id, t.teacher_id, t.semester,
                       t.location, t.max_students, c.course_name
                FROM teaching_class t
                JOIN course c ON c.course_id = t.course_id
                WHERE t.teacher_id = %s
                ORDER BY t.class_id
            """, (teacher_id,))
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    except Exception as e:
        return fail(str(e), code=500)
    finally:
        conn.close()


@app.route("/api/teacher/<teacher_id>/sessions", methods=["GET"])
def list_teacher_sessions(teacher_id):
    """查询指定教师发起过的全部签到场次（按开始时间倒序）。"""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT s.session_id, s.class_id, s.session_date,
                       s.start_time, s.end_time, s.session_status,
                       s.valid_minutes, s.qr_token,
                       s.location_latitude, s.location_longitude,
                       t.location, c.course_name
                FROM attendance_session s
                JOIN teaching_class t ON t.class_id = s.class_id
                JOIN course c ON c.course_id = t.course_id
                WHERE t.teacher_id = %s
                ORDER BY s.start_time DESC
            """, (teacher_id,))
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    except Exception as e:
        return fail(str(e), code=500)
    finally:
        conn.close()


# ===================== 8. 教学班基础 CRUD =====================

@app.route("/api/teaching_classes", methods=["GET"])
def list_teaching_classes():
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT tc.class_id, tc.course_id, c.course_name,
                       tc.teacher_id, t.name AS teacher_name,
                       tc.semester, tc.location, tc.max_students
                FROM teaching_class tc
                LEFT JOIN course c ON c.course_id=tc.course_id
                LEFT JOIN teacher t ON t.teacher_id=tc.teacher_id
                ORDER BY tc.class_id
            """)
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    except Exception as e:
        return fail(str(e), code=500)
    finally:
        conn.close()


@app.route("/api/teaching_classes", methods=["POST"])
def create_teaching_class():
    data = request.get_json(silent=True) or {}
    required = ["class_id", "course_id", "teacher_id", "semester", "location", "max_students"]
    for k in required:
        if data.get(k) in (None, ""):
            return fail(f"参数 {k} 不能为空")

    try:
        max_students = int(data["max_students"])
        if max_students <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return fail("max_students 必须为正整数")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT class_id FROM teaching_class WHERE class_id=%s",
                (data["class_id"],))
            if cursor.fetchone() is not None:
                return fail("该班级编号已存在")
            cursor.execute("SELECT course_id FROM course WHERE course_id=%s", (data["course_id"],))
            if cursor.fetchone() is None:
                return fail("课程不存在", code=404)
            cursor.execute("SELECT teacher_id FROM teacher WHERE teacher_id=%s", (data["teacher_id"],))
            if cursor.fetchone() is None:
                return fail("教师不存在", code=404)

            cursor.execute(
                "INSERT INTO teaching_class (class_id, course_id, teacher_id, semester, location, max_students) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (data["class_id"], data["course_id"],
                 data.get("teacher_id") or None,
                 data["semester"],
                 data["location"],
                 max_students))
        conn.commit()
        return ok({"class_id": data["class_id"]}, "教学班添加成功")
    except Exception as e:
        conn.rollback()
        return fail(str(e), code=500)
    finally:
        conn.close()


@app.route("/api/teaching_classes/<class_id>", methods=["PUT"])
def update_teaching_class(class_id):
    data = request.get_json(silent=True) or {}
    if not data:
        return fail("至少需要提供一个待修改字段")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT class_id FROM teaching_class WHERE class_id=%s",
                (class_id,))
            if cursor.fetchone() is None:
                return fail("教学班不存在", code=404)

            sets: list[str] = []
            params: list[Any] = []
            for field in ["course_id", "teacher_id", "semester", "location", "max_students"]:
                if field in data:
                    sets.append(f"{field}=%s")
                    params.append(data[field] if data[field] != "" else None)
            if not sets:
                return fail("没有可修改的字段")
            params.append(class_id)

            cursor.execute(
                f"UPDATE teaching_class SET {', '.join(sets)} WHERE class_id=%s",
                tuple(params))
        conn.commit()
        return ok(None, "教学班信息已更新")
    except Exception as e:
        conn.rollback()
        return fail(str(e), code=500)
    finally:
        conn.close()


@app.route("/api/teaching_classes/<class_id>", methods=["DELETE"])
def delete_teaching_class(class_id):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT class_id FROM teaching_class WHERE class_id=%s",
                (class_id,))
            if cursor.fetchone() is None:
                return fail("教学班不存在", code=404)

            cursor.execute(
                "DELETE FROM teaching_class WHERE class_id=%s", (class_id,))
        conn.commit()
        return ok(None, "教学班已删除")
    except Exception as e:
        conn.rollback()
        return fail(str(e), code=500)
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
