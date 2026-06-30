"""Management APIs for teachers, courses, sessions, and class rosters."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

from flask import Blueprint, jsonify, request

from db import get_conn


management_bp = Blueprint("management", __name__)
DbRow = dict[str, Any]


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def ok(data: Any = None, message: str = "ok"):
    return jsonify({"code": 200, "message": message, "data": json_safe(data)})


def fail(message: str, code: int = 400, data: Any = None):
    return jsonify({"code": code, "message": message, "data": json_safe(data)})


def required_text(data: dict[str, Any], field: str) -> str:
    value = str(data.get(field) or "").strip()
    if not value:
        raise ValueError(f"参数 {field} 不能为空")
    return value


# ===================== Teacher CRUD =====================

@management_bp.route("/api/teachers", methods=["GET"])
def list_teachers():
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT teacher_id, name, department FROM teacher ORDER BY teacher_id"
            )
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    except Exception as exc:
        return fail(str(exc), code=500)
    finally:
        conn.close()


@management_bp.route("/api/teachers/<teacher_id>", methods=["GET"])
def get_teacher(teacher_id: str):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT teacher_id, name, department FROM teacher WHERE teacher_id=%s",
                (teacher_id,),
            )
            row = cast(DbRow, cursor.fetchone())
        if row is None:
            return fail("教师不存在", code=404)
        return ok(row)
    except Exception as exc:
        return fail(str(exc), code=500)
    finally:
        conn.close()


@management_bp.route("/api/teachers", methods=["POST"])
def create_teacher():
    data = request.get_json(silent=True) or {}
    try:
        teacher_id = required_text(data, "teacher_id")
        name = required_text(data, "name")
        department = required_text(data, "department")
    except ValueError as exc:
        return fail(str(exc))

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT teacher_id FROM teacher WHERE teacher_id=%s",
                (teacher_id,),
            )
            if cursor.fetchone() is not None:
                return fail("该工号已存在")
            cursor.execute(
                "INSERT INTO teacher (teacher_id, name, department) VALUES (%s,%s,%s)",
                (teacher_id, name, department),
            )
        conn.commit()
        return ok({"teacher_id": teacher_id}, "教师添加成功")
    except Exception as exc:
        conn.rollback()
        return fail(str(exc), code=500)
    finally:
        conn.close()


@management_bp.route("/api/teachers/<teacher_id>", methods=["PUT"])
def update_teacher(teacher_id: str):
    data = request.get_json(silent=True) or {}
    fields: dict[str, str] = {}
    for field in ("name", "department"):
        if field in data:
            value = str(data.get(field) or "").strip()
            if not value:
                return fail(f"参数 {field} 不能为空")
            fields[field] = value
    if not fields:
        return fail("至少需要提供 name 或 department")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT teacher_id FROM teacher WHERE teacher_id=%s",
                (teacher_id,),
            )
            if cursor.fetchone() is None:
                return fail("教师不存在", code=404)
            assignments = ", ".join(f"{field}=%s" for field in fields)
            params = [*fields.values(), teacher_id]
            cursor.execute(
                f"UPDATE teacher SET {assignments} WHERE teacher_id=%s",
                tuple(params),
            )
        conn.commit()
        return ok(None, "教师信息已更新")
    except Exception as exc:
        conn.rollback()
        return fail(str(exc), code=500)
    finally:
        conn.close()


@management_bp.route("/api/teachers/<teacher_id>", methods=["DELETE"])
def delete_teacher(teacher_id: str):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT teacher_id FROM teacher WHERE teacher_id=%s",
                (teacher_id,),
            )
            if cursor.fetchone() is None:
                return fail("教师不存在", code=404)
            cursor.execute(
                "SELECT class_id FROM teaching_class WHERE teacher_id=%s LIMIT 1",
                (teacher_id,),
            )
            if cursor.fetchone() is not None:
                return fail("该教师已被教学班引用，无法删除")
            cursor.execute("DELETE FROM teacher WHERE teacher_id=%s", (teacher_id,))
        conn.commit()
        return ok(None, "教师已删除")
    except Exception as exc:
        conn.rollback()
        return fail(str(exc), code=500)
    finally:
        conn.close()


# ===================== Course and session lookup =====================

@management_bp.route("/api/courses", methods=["GET"])
def list_courses():
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT course_id, course_name, department, credit "
                "FROM course ORDER BY course_id"
            )
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    except Exception as exc:
        return fail(str(exc), code=500)
    finally:
        conn.close()


@management_bp.route("/api/courses/<course_id>", methods=["GET"])
def get_course(course_id: str):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT course_id, course_name, department, credit "
                "FROM course WHERE course_id=%s",
                (course_id,),
            )
            row = cast(DbRow, cursor.fetchone())
        if row is None:
            return fail("课程不存在", code=404)
        return ok(row)
    except Exception as exc:
        return fail(str(exc), code=500)
    finally:
        conn.close()


@management_bp.route("/api/sessions", methods=["GET"])
def list_sessions():
    teacher_id = (request.args.get("teacher_id") or "").strip()
    class_id = (request.args.get("class_id") or "").strip()
    status = (request.args.get("status") or "").strip()
    if status and status not in {"ongoing", "closed"}:
        return fail("status 必须为 ongoing 或 closed")

    sql = """
        SELECT sess.session_id, sess.class_id, sess.session_date,
               sess.start_time, sess.end_time, sess.valid_minutes,
               sess.session_status, sess.qr_token,
               tc.teacher_id, tc.location, c.course_id, c.course_name
        FROM attendance_session sess
        JOIN teaching_class tc ON tc.class_id=sess.class_id
        JOIN course c ON c.course_id=tc.course_id
        WHERE 1=1
    """
    params: list[Any] = []
    if teacher_id:
        sql += " AND tc.teacher_id=%s"
        params.append(teacher_id)
    if class_id:
        sql += " AND sess.class_id=%s"
        params.append(class_id)
    if status:
        sql += " AND sess.session_status=%s"
        params.append(status)
    sql += " ORDER BY sess.start_time DESC LIMIT 200"

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    except Exception as exc:
        return fail(str(exc), code=500)
    finally:
        conn.close()


# ===================== Class roster management =====================

@management_bp.route("/api/teaching_classes/<class_id>/students", methods=["GET"])
def list_enrolled_students(class_id: str):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT class_id FROM teaching_class WHERE class_id=%s",
                (class_id,),
            )
            if cursor.fetchone() is None:
                return fail("教学班不存在", code=404)
            cursor.execute(
                """
                SELECT s.student_id, s.name, s.gender, s.department,
                       s.major, s.class_name, e.enroll_date
                FROM enrollment e
                JOIN student s ON s.student_id=e.student_id
                WHERE e.class_id=%s AND e.enroll_status='enrolled'
                ORDER BY s.student_id
                """,
                (class_id,),
            )
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    except Exception as exc:
        return fail(str(exc), code=500)
    finally:
        conn.close()


@management_bp.route("/api/teaching_classes/<class_id>/students", methods=["POST"])
def add_student_to_class(class_id: str):
    data = request.get_json(silent=True) or {}
    student_id = str(data.get("student_id") or "").strip()
    if not student_id:
        return fail("参数 student_id 不能为空")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT class_id FROM teaching_class WHERE class_id=%s",
                (class_id,),
            )
            if cursor.fetchone() is None:
                return fail("教学班不存在", code=404)
            cursor.execute(
                "SELECT student_id FROM student WHERE student_id=%s",
                (student_id,),
            )
            if cursor.fetchone() is None:
                return fail("学生不存在", code=404)
            cursor.execute(
                """
                INSERT INTO enrollment
                    (student_id, class_id, enroll_date, enroll_status)
                VALUES (%s,%s,CURRENT_DATE,'enrolled')
                ON DUPLICATE KEY UPDATE
                    enroll_status='enrolled', enroll_date=CURRENT_DATE
                """,
                (student_id, class_id),
            )
        conn.commit()
        return ok(None, "学生已加入教学班")
    except Exception as exc:
        conn.rollback()
        return fail(str(exc), code=500)
    finally:
        conn.close()


@management_bp.route(
    "/api/teaching_classes/<class_id>/students/<student_id>",
    methods=["DELETE"],
)
def remove_student_from_class(class_id: str, student_id: str):
    """Soft-delete enrollment so historical attendance remains traceable."""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT enrollment_id FROM enrollment
                WHERE class_id=%s AND student_id=%s
                """,
                (class_id, student_id),
            )
            if cursor.fetchone() is None:
                return fail("该学生不在教学班中", code=404)
            cursor.execute(
                """
                UPDATE enrollment SET enroll_status='dropped'
                WHERE class_id=%s AND student_id=%s
                """,
                (class_id, student_id),
            )
        conn.commit()
        return ok(None, "学生已退出教学班")
    except Exception as exc:
        conn.rollback()
        return fail(str(exc), code=500)
    finally:
        conn.close()
