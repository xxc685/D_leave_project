-- =====================================================================
--  扫码签到系统 - 数据库建库脚本
--  统一版本(对齐 A.docx 设计文档,与 B/D 模块代码完全一致)
--  字符集:utf8mb4   排序规则:utf8mb4_unicode_ci
-- =====================================================================

CREATE DATABASE IF NOT EXISTS attendance_system
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE attendance_system;

-- 教师表
CREATE TABLE IF NOT EXISTS teacher (
    teacher_id  VARCHAR(20) PRIMARY KEY COMMENT '教师工号',
    name        VARCHAR(50) NOT NULL    COMMENT '教师姓名',
    department  VARCHAR(50) NOT NULL    COMMENT '所属院系'
) COMMENT = '教师信息表';

-- 课程表
CREATE TABLE IF NOT EXISTS course (
    course_id   VARCHAR(20)  PRIMARY KEY COMMENT '课程编号',
    course_name VARCHAR(100) NOT NULL    COMMENT '课程名称',
    department  VARCHAR(50)  NOT NULL    COMMENT '开课院系',
    credit      INT          NOT NULL    COMMENT '课程学分'
) COMMENT = '课程信息表';

-- 学生表
CREATE TABLE IF NOT EXISTS student (
    student_id VARCHAR(20) PRIMARY KEY COMMENT '学号',
    name       VARCHAR(50) NOT NULL    COMMENT '学生姓名',
    gender     VARCHAR(10) DEFAULT NULL COMMENT '性别',
    department VARCHAR(50) NOT NULL    COMMENT '所属院系',
    major      VARCHAR(50) NOT NULL    COMMENT '所属专业',
    class_name VARCHAR(50) NOT NULL    COMMENT '班级名称'
) COMMENT = '学生信息表';

-- 教学班表
CREATE TABLE IF NOT EXISTS teaching_class (
    class_id     VARCHAR(20)  PRIMARY KEY COMMENT '教学班编号',
    semester     VARCHAR(20)  NOT NULL    COMMENT '所属学期',
    location     VARCHAR(100) NOT NULL    COMMENT '上课地点',
    max_students INT          NOT NULL    COMMENT '最大容纳人数',
    teacher_id   VARCHAR(20)  NOT NULL    COMMENT '授课教师工号',
    course_id    VARCHAR(20)  NOT NULL    COMMENT '所属课程编号',
    CONSTRAINT fk_class_teacher FOREIGN KEY (teacher_id) REFERENCES teacher(teacher_id),
    CONSTRAINT fk_class_course  FOREIGN KEY (course_id)  REFERENCES course(course_id)
) COMMENT = '教学班信息表';

-- 选课记录表
CREATE TABLE IF NOT EXISTS enrollment (
    enrollment_id INT          PRIMARY KEY AUTO_INCREMENT COMMENT '选课记录自增ID',
    student_id    VARCHAR(20)  NOT NULL                   COMMENT '学号',
    class_id      VARCHAR(20)  NOT NULL                   COMMENT '教学班编号',
    enroll_date   DATE         NOT NULL                   COMMENT '选课日期',
    enroll_status VARCHAR(20)  NOT NULL                   COMMENT '选课状态:enrolled/dropped',
    CONSTRAINT fk_enroll_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_enroll_class   FOREIGN KEY (class_id)   REFERENCES teaching_class(class_id),
    UNIQUE KEY uk_student_class (student_id, class_id)
) COMMENT = '学生选课记录表';

-- 考勤会话表(每一次签到场次)
CREATE TABLE IF NOT EXISTS attendance_session (
    session_id         INT             PRIMARY KEY AUTO_INCREMENT COMMENT '考勤会话ID',
    class_id           VARCHAR(20)     NOT NULL                   COMMENT '所属教学班编号',
    session_date       DATE            NOT NULL                   COMMENT '考勤日期',
    start_time         DATETIME        NOT NULL                   COMMENT '签到开始时间',
    end_time           DATETIME        NOT NULL                   COMMENT '签到结束时间',
    qr_token           VARCHAR(64)     NOT NULL UNIQUE            COMMENT '二维码唯一令牌',
    valid_minutes      INT             NOT NULL                   COMMENT '二维码正常签到时长(分钟)',
    location_latitude  DECIMAL(10, 7)  NOT NULL                   COMMENT '签到中心点纬度',
    location_longitude DECIMAL(10, 7)  NOT NULL                   COMMENT '签到中心点经度',
    location_radius    INT             NOT NULL                   COMMENT '允许签到范围半径(米)',
    session_status     VARCHAR(20)     NOT NULL                   COMMENT '会话状态:ongoing/closed',
    CONSTRAINT fk_session_class FOREIGN KEY (class_id) REFERENCES teaching_class(class_id),
    KEY idx_session_class (class_id, session_date)
) COMMENT = '考勤签到会话表';

-- 考勤记录表(每位学生本次签到的明细)
CREATE TABLE IF NOT EXISTS attendance_record (
    record_id         INT            PRIMARY KEY AUTO_INCREMENT COMMENT '签到记录ID',
    session_id        INT            NOT NULL                   COMMENT '关联考勤会话ID',
    student_id        VARCHAR(20)    NOT NULL                   COMMENT '学号',
    scan_time         DATETIME       NOT NULL                   COMMENT '扫码签到时间',
    attendance_status VARCHAR(20)    NOT NULL                   COMMENT '考勤状态:present/late/absent/invalid/leave',
    latitude          DECIMAL(10, 7) NOT NULL                   COMMENT '学生签到纬度',
    longitude         DECIMAL(10, 7) NOT NULL                   COMMENT '学生签到经度',
    is_valid          VARCHAR(10)    NOT NULL                   COMMENT '签到是否有效:valid/invalid',
    remark            VARCHAR(255)             DEFAULT NULL     COMMENT '备注说明',
    CONSTRAINT fk_record_session FOREIGN KEY (session_id) REFERENCES attendance_session(session_id),
    CONSTRAINT fk_record_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    KEY idx_record_session_student (session_id, student_id),
    KEY idx_record_student        (student_id)
) COMMENT = '学生考勤签到记录表';

-- 请假申请表
CREATE TABLE IF NOT EXISTS leave_request (
    request_id     INT          PRIMARY KEY AUTO_INCREMENT COMMENT '请假申请ID',
    student_id     VARCHAR(20)  NOT NULL COMMENT '申请学生学号',
    session_id     INT          NOT NULL COMMENT '请假对应签到场次',
    class_id       VARCHAR(20)  NOT NULL COMMENT '对应教学班',
    reason         VARCHAR(500) NOT NULL COMMENT '请假原因',
    status         VARCHAR(20)  NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected',
    submit_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '提交时间',
    review_time    DATETIME              DEFAULT NULL COMMENT '审批时间',
    reviewer_id    VARCHAR(20)           DEFAULT NULL COMMENT '审批教师工号',
    review_remark  VARCHAR(255)          DEFAULT NULL COMMENT '审批备注',
    CONSTRAINT fk_leave_student FOREIGN KEY (student_id) REFERENCES student(student_id),
    CONSTRAINT fk_leave_session FOREIGN KEY (session_id) REFERENCES attendance_session(session_id),
    CONSTRAINT fk_leave_class FOREIGN KEY (class_id) REFERENCES teaching_class(class_id),
    CONSTRAINT fk_leave_reviewer FOREIGN KEY (reviewer_id) REFERENCES teacher(teacher_id),
    UNIQUE KEY uk_leave_student_session (student_id, session_id),
    KEY idx_leave_teacher_status (class_id, status, submit_time),
    KEY idx_leave_student_time (student_id, submit_time)
) COMMENT = '学生请假申请表';

