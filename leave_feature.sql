USE attendance_system;

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
