# ⚠️ 历史备份文件 — 仅供版本参考，请勿运行！
#    缺失正式版功能：PUT 方法、CSV 导入/导出、教学班 CRUD、教师管理接口等。
#    当前正式版本为 code/app.py。

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
    attendance_status: present(正常) / late(迟到) / absent(缺勤) / invalid(无效)
    is_valid:          valid / invalid
    session_status:    ongoing(进行中) / closed(已结束)
    enroll_status:     enrolled(在选)  / dropped(已退)
"""

from flask import Flask, request, jsonify
from db import get_conn
from datetime import date, datetime, timedelta
from decimal import Decimal
from math import radians, sin, cos, asin, sqrt
from typing import Any, cast
import uuid

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
    return response

VALID_ATTEND_STATUS = {"present", "late", "absent", "invalid"}
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
            teaching_class = cast(DbRow | None, cursor.fetchone())
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
            session = cast(DbRow | None, cursor.fetchone())
            if session is None:
                conn.rollback()
                return fail("二维码无效或已失效")
            if session["session_status"] != "ongoing":
                conn.rollback()
                return fail("该签到场次已关闭")

            cursor.execute(
                "SELECT student_id FROM student WHERE student_id=%s",
                (data["student_id"],))
            student = cast(DbRow | None, cursor.fetchone())
            if student is None:
                conn.rollback()
                return fail("学生不存在")

            cursor.execute("""
                SELECT enrollment_id FROM enrollment
                WHERE student_id=%s AND class_id=%s
                  AND enroll_status='enrolled'
            """, (data["student_id"], session["class_id"]))
            enrollment = cast(DbRow | None, cursor.fetchone())
            if enrollment is None:
                conn.rollback()
                return fail("该学生未选修当前教学班")

            cursor.execute("""
                SELECT record_id FROM attendance_record
                WHERE session_id=%s AND student_id=%s AND is_valid='valid'
                FOR UPDATE
            """, (session["session_id"], data["student_id"]))
            valid_record = cast(DbRow | None, cursor.fetchone())
            if valid_record is not None:
                conn.rollback()
                return fail("已签到过,无需重复签到")

            scan_time = datetime.now()
            status, is_valid, msg = judge_time_status(
                scan_time, session["start_time"],
                session["valid_minutes"], session["end_time"])

            distance = haversine_meters(
                lat, lon,
                float(session["location_latitude"]),
                float(session["location_longitude"]))
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
            session = cast(DbRow | None, cursor.fetchone())
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
        attendance_status: present/late/absent/invalid
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
            record = cast(DbRow | None, cursor.fetchone())
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
            updated = cast(DbRow | None, cursor.fetchone())
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
            row = cast(DbRow | None, cursor.fetchone())
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
