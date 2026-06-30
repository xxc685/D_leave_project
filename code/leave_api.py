"""Student leave requests and teacher review APIs."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

from flask import Blueprint, jsonify, request

from db import get_conn


leave_bp = Blueprint("leave", __name__)
DbRow = dict[str, Any]
VALID_LEAVE_STATUS = {"pending", "approved", "rejected"}


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


@leave_bp.route("/api/students/<student_id>/leave_options", methods=["GET"])
def list_leave_options(student_id: str):
    """Return sessions for which the student may submit or resubmit leave."""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT student_id FROM student WHERE student_id=%s",
                (student_id,),
            )
            if cursor.fetchone() is None:
                return fail("学生不存在", code=404)

            cursor.execute(
                """
                SELECT sess.session_id, sess.class_id, sess.session_date,
                       sess.start_time, sess.end_time, sess.session_status,
                       c.course_name, tc.location,
                       lr.request_id, lr.status AS leave_status
                FROM enrollment e
                JOIN attendance_session sess ON sess.class_id=e.class_id
                JOIN teaching_class tc ON tc.class_id=sess.class_id
                JOIN course c ON c.course_id=tc.course_id
                LEFT JOIN leave_request lr
                  ON lr.student_id=e.student_id AND lr.session_id=sess.session_id
                WHERE e.student_id=%s AND e.enroll_status='enrolled'
                  AND (lr.request_id IS NULL OR lr.status='rejected')
                  AND NOT EXISTS (
                    SELECT 1 FROM attendance_record ar
                    WHERE ar.student_id=e.student_id
                      AND ar.session_id=sess.session_id
                      AND ar.is_valid='valid'
                      AND ar.attendance_status IN ('present','late','leave')
                  )
                ORDER BY sess.start_time DESC
                LIMIT 50
                """,
                (student_id,),
            )
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    except Exception as exc:
        return fail(str(exc), code=500)
    finally:
        conn.close()


@leave_bp.route("/api/students/<student_id>/leave_requests", methods=["GET"])
def list_student_leave_requests(student_id: str):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT lr.request_id, lr.student_id, lr.session_id, lr.class_id,
                       lr.reason, lr.status, lr.submit_time, lr.review_time,
                       lr.reviewer_id, lr.review_remark,
                       sess.session_date, sess.start_time, sess.end_time,
                       c.course_name, tc.location, t.name AS reviewer_name
                FROM leave_request lr
                JOIN attendance_session sess ON sess.session_id=lr.session_id
                JOIN teaching_class tc ON tc.class_id=lr.class_id
                JOIN course c ON c.course_id=tc.course_id
                LEFT JOIN teacher t ON t.teacher_id=lr.reviewer_id
                WHERE lr.student_id=%s
                ORDER BY lr.submit_time DESC
                """,
                (student_id,),
            )
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    except Exception as exc:
        return fail(str(exc), code=500)
    finally:
        conn.close()


@leave_bp.route("/api/leave_requests", methods=["POST"])
def create_leave_request():
    data = request.get_json(silent=True) or {}
    student_id = str(data.get("student_id") or "").strip()
    reason = str(data.get("reason") or "").strip()
    try:
        session_id = int(data.get("session_id"))
    except (TypeError, ValueError):
        return fail("session_id 格式错误")

    if not student_id:
        return fail("student_id 不能为空")
    if not reason:
        return fail("请填写请假原因")
    if len(reason) > 500:
        return fail("请假原因不能超过 500 个字符")

    conn = get_conn()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT sess.session_id, sess.class_id, sess.start_time,
                       c.course_name
                FROM attendance_session sess
                JOIN teaching_class tc ON tc.class_id=sess.class_id
                JOIN course c ON c.course_id=tc.course_id
                WHERE sess.session_id=%s
                FOR UPDATE
                """,
                (session_id,),
            )
            session = cast(DbRow, cursor.fetchone())
            if session is None:
                conn.rollback()
                return fail("签到场次不存在", code=404)

            cursor.execute(
                """
                SELECT enrollment_id FROM enrollment
                WHERE student_id=%s AND class_id=%s AND enroll_status='enrolled'
                """,
                (student_id, session["class_id"]),
            )
            if cursor.fetchone() is None:
                conn.rollback()
                return fail("你未选修该教学班，不能申请请假")

            cursor.execute(
                """
                SELECT record_id FROM attendance_record
                WHERE session_id=%s AND student_id=%s AND is_valid='valid'
                  AND attendance_status IN ('present','late','leave')
                LIMIT 1
                """,
                (session_id, student_id),
            )
            if cursor.fetchone() is not None:
                conn.rollback()
                return fail("该场次已有有效出勤或请假记录")

            cursor.execute(
                """
                SELECT request_id, status FROM leave_request
                WHERE student_id=%s AND session_id=%s
                FOR UPDATE
                """,
                (student_id, session_id),
            )
            old_request = cast(DbRow, cursor.fetchone())
            now = datetime.now()
            if old_request is None:
                cursor.execute(
                    """
                    INSERT INTO leave_request
                    (student_id, session_id, class_id, reason, status, submit_time)
                    VALUES (%s,%s,%s,%s,'pending',%s)
                    """,
                    (student_id, session_id, session["class_id"], reason, now),
                )
                request_id = cursor.lastrowid
            elif old_request["status"] == "rejected":
                cursor.execute(
                    """
                    UPDATE leave_request
                    SET reason=%s, status='pending', submit_time=%s,
                        review_time=NULL, reviewer_id=NULL, review_remark=NULL
                    WHERE request_id=%s
                    """,
                    (reason, now, old_request["request_id"]),
                )
                request_id = old_request["request_id"]
            else:
                conn.rollback()
                return fail("该场次已有待审批或已批准的请假申请")

        conn.commit()
        return ok(
            {"request_id": request_id, "status": "pending"},
            "请假申请已提交",
        )
    except Exception as exc:
        conn.rollback()
        return fail(str(exc), code=500)
    finally:
        conn.close()


@leave_bp.route("/api/teacher/<teacher_id>/leave_requests", methods=["GET"])
def list_teacher_leave_requests(teacher_id: str):
    status = (request.args.get("status") or "").strip()
    if status and status not in VALID_LEAVE_STATUS:
        return fail("status 必须为 pending、approved 或 rejected")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT lr.request_id, lr.student_id, st.name AS student_name,
                       lr.session_id, lr.class_id, lr.reason, lr.status,
                       lr.submit_time, lr.review_time, lr.review_remark,
                       sess.session_date, sess.start_time, sess.end_time,
                       c.course_name, tc.location
                FROM leave_request lr
                JOIN student st ON st.student_id=lr.student_id
                JOIN attendance_session sess ON sess.session_id=lr.session_id
                JOIN teaching_class tc ON tc.class_id=lr.class_id
                JOIN course c ON c.course_id=tc.course_id
                WHERE tc.teacher_id=%s
            """
            params: list[Any] = [teacher_id]
            if status:
                sql += " AND lr.status=%s"
                params.append(status)
            sql += " ORDER BY CASE lr.status WHEN 'pending' THEN 0 ELSE 1 END, lr.submit_time DESC"
            cursor.execute(sql, tuple(params))
            rows = cast(list[DbRow], cursor.fetchall())
        return ok(rows)
    except Exception as exc:
        return fail(str(exc), code=500)
    finally:
        conn.close()


@leave_bp.route("/api/leave_requests/<int:request_id>/review", methods=["POST"])
def review_leave_request(request_id: int):
    data = request.get_json(silent=True) or {}
    reviewer_id = str(data.get("reviewer_id") or "").strip()
    action = str(data.get("action") or data.get("status") or "").strip()
    review_remark = str(data.get("review_remark") or "").strip()
    status = {"approve": "approved", "reject": "rejected"}.get(action, action)

    if not reviewer_id:
        return fail("reviewer_id 不能为空")
    if status not in {"approved", "rejected"}:
        return fail("action 必须为 approve 或 reject")
    if len(review_remark) > 255:
        return fail("审批备注不能超过 255 个字符")

    conn = get_conn()
    try:
        conn.begin()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT lr.*, tc.teacher_id, c.course_name
                FROM leave_request lr
                JOIN teaching_class tc ON tc.class_id=lr.class_id
                JOIN course c ON c.course_id=tc.course_id
                WHERE lr.request_id=%s
                FOR UPDATE
                """,
                (request_id,),
            )
            leave_request = cast(DbRow, cursor.fetchone())
            if leave_request is None:
                conn.rollback()
                return fail("请假申请不存在", code=404)
            if leave_request["teacher_id"] != reviewer_id:
                conn.rollback()
                return fail("你无权审批该教学班的请假", code=403)
            if leave_request["status"] != "pending":
                conn.rollback()
                return fail("该申请已审批，不能重复操作")

            now = datetime.now()
            if status == "approved":
                cursor.execute(
                    """
                    SELECT record_id FROM attendance_record
                    WHERE session_id=%s AND student_id=%s
                      AND is_valid='valid'
                      AND attendance_status IN ('present','late')
                    LIMIT 1
                    FOR UPDATE
                    """,
                    (leave_request["session_id"], leave_request["student_id"]),
                )
                if cursor.fetchone() is not None:
                    conn.rollback()
                    return fail("该学生已经有效签到，不能再批准请假")

                remark = "请假已批准：" + leave_request["reason"]
                if review_remark:
                    remark += "；审批备注：" + review_remark
                remark = remark[:255]

                cursor.execute(
                    """
                    UPDATE attendance_record
                    SET scan_time=%s, attendance_status='leave',
                        latitude=0, longitude=0, is_valid='valid', remark=%s
                    WHERE session_id=%s AND student_id=%s
                      AND attendance_status='absent'
                    """,
                    (
                        now,
                        remark,
                        leave_request["session_id"],
                        leave_request["student_id"],
                    ),
                )
                if cursor.rowcount == 0:
                    cursor.execute(
                        """
                        INSERT INTO attendance_record
                        (session_id, student_id, scan_time, attendance_status,
                         latitude, longitude, is_valid, remark)
                        VALUES (%s,%s,%s,'leave',0,0,'valid',%s)
                        """,
                        (
                            leave_request["session_id"],
                            leave_request["student_id"],
                            now,
                            remark,
                        ),
                    )

            cursor.execute(
                """
                UPDATE leave_request
                SET status=%s, review_time=%s, reviewer_id=%s, review_remark=%s
                WHERE request_id=%s
                """,
                (status, now, reviewer_id, review_remark or None, request_id),
            )
        conn.commit()
        message = "请假申请已批准" if status == "approved" else "请假申请已驳回"
        return ok({"request_id": request_id, "status": status}, message)
    except Exception as exc:
        conn.rollback()
        return fail(str(exc), code=500)
    finally:
        conn.close()
