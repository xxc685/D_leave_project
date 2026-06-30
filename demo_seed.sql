USE attendance_system;

-- 固定演示教师
INSERT INTO teacher (teacher_id, name, department)
VALUES ('T-DEMO-01', '演示教师', '计算机学院')
ON DUPLICATE KEY UPDATE
    name=VALUES(name), department=VALUES(department);

-- 固定演示课程
INSERT INTO course (course_id, course_name, department, credit)
VALUES ('C-DEMO-01', '数据库系统演示课', '计算机学院', 3)
ON DUPLICATE KEY UPDATE
    course_name=VALUES(course_name),
    department=VALUES(department),
    credit=VALUES(credit);

-- 固定演示教学班
INSERT INTO teaching_class
    (class_id, semester, location, max_students, teacher_id, course_id)
VALUES
    ('CL-DEMO-01', '2025-2026-2', 'H6112', 60, 'T-DEMO-01', 'C-DEMO-01')
ON DUPLICATE KEY UPDATE
    semester=VALUES(semester),
    location=VALUES(location),
    max_students=VALUES(max_students),
    teacher_id=VALUES(teacher_id),
    course_id=VALUES(course_id);

-- S1 用于正常签到，S2 用于申请请假
INSERT INTO student
    (student_id, name, department, major, class_name)
VALUES
    ('S-DEMO-01', '签到学生', '计算机学院', '计算机科学与技术', '演示班'),
    ('S-DEMO-02', '请假学生', '计算机学院', '计算机科学与技术', '演示班')
ON DUPLICATE KEY UPDATE
    name=VALUES(name),
    department=VALUES(department),
    major=VALUES(major),
    class_name=VALUES(class_name);

-- 两名学生均选修演示教学班
INSERT INTO enrollment
    (student_id, class_id, enroll_date, enroll_status)
VALUES
    ('S-DEMO-01', 'CL-DEMO-01', CURRENT_DATE, 'enrolled'),
    ('S-DEMO-02', 'CL-DEMO-01', CURRENT_DATE, 'enrolled')
ON DUPLICATE KEY UPDATE
    enroll_date=VALUES(enroll_date),
    enroll_status='enrolled';

-- 执行完成后应返回 1 名教师、1 个教学班、2 名在选学生
SELECT teacher_id, name FROM teacher WHERE teacher_id='T-DEMO-01';
SELECT class_id, course_id, teacher_id, location
FROM teaching_class WHERE class_id='CL-DEMO-01';
SELECT student_id, class_id, enroll_status
FROM enrollment WHERE class_id='CL-DEMO-01'
ORDER BY student_id;
