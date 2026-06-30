SELECT 
    tc.class_id,
    c.course_name,
    COUNT(DISTINCT e.student_id) AS total_students,
    COUNT(DISTINCT ar.student_id) AS checked_students,
    SUM(CASE WHEN ar.attendance_status = 'absent' THEN 1 ELSE 0 END) AS absent_total,
    ROUND(
        COUNT(DISTINCT ar.student_id)/COUNT(DISTINCT e.student_id)*100,2
    ) AS attendance_rate
FROM teaching_class tc
JOIN course c ON tc.course_id = c.course_id
JOIN enrollment e ON tc.class_id = e.class_id
LEFT JOIN attendance_session ats ON tc.class_id = ats.class_id
LEFT JOIN attendance_record ar ON ats.session_id = ar.session_id
WHERE tc.class_id = '教学班id'
GROUP BY tc.class_id, c.course_name;